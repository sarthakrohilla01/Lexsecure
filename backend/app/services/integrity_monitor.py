"""Continuous Integrity Monitoring"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict

from app.api.ws import ws_manager
from app.audit.logger import record_audit_event
from app.config import settings
from app.database.session import SessionLocal
from app.models.document import DocumentVersion
from app.services.tamper_service import verify_version_integrity
from app.utils.time import utcnow

logger = logging.getLogger("lexsecure.integrity")

_ALERT_COOLDOWN = timedelta(minutes=30)
_last_alert: Dict[int, datetime] = {}
_state = {"last_run": None, "checked": 0, "failed": 0}


def run_integrity_sweep() -> dict:
    """Verifies every stored version. Safe to call from a thread or CLI."""
    db = SessionLocal()
    checked = 0
    failed = 0
    try:
        versions = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.is_tampered.is_(False))
            .all()
        )
        for version in versions:
            report = verify_version_integrity(version.id, db, record_audit=False)
            checked += 1
            if report.get("is_valid"):
                continue

            failed += 1
            now = utcnow()
            previous = _last_alert.get(version.id)
            if previous and now - previous < _ALERT_COOLDOWN:
                continue
            _last_alert[version.id] = now

            document = version.document
            record_audit_event(
                db=db,
                action="INTEGRITY_FAILURE",
                target_type="DOCUMENT",
                target_id=str(version.document_id),
                details=(
                    f"Background verification failed for '{document.title}' "
                    f"v{version.version_number} — {report.get('error') or 'hash/signature/ledger mismatch'}"
                ),
                status="BLOCKED",
            )
            ws_manager.broadcast_sync(
                "TAMPER_ALERT",
                {
                    "severity": "CRITICAL",
                    "document_id": version.document_id,
                    "document_title": document.title,
                    "case_id": document.case_id,
                    "version_number": version.version_number,
                    "detected_by": "continuous-integrity-monitor",
                    "message": (
                        f"Integrity failure detected in '{document.title}' "
                        f"(v{version.version_number}, {document.case_id})"
                    ),
                },
            )
    finally:
        db.close()

    _state.update(last_run=utcnow().isoformat(), checked=checked, failed=failed)
    return dict(_state)


def monitor_status() -> dict:
    return {
        "enabled": settings.INTEGRITY_CHECK_INTERVAL_SECONDS > 0,
        "interval_seconds": settings.INTEGRITY_CHECK_INTERVAL_SECONDS,
        **_state,
    }


async def integrity_monitor_loop(stop_event: asyncio.Event) -> None:
    interval = settings.INTEGRITY_CHECK_INTERVAL_SECONDS
    if interval <= 0:
        logger.info("Continuous integrity monitoring disabled (interval=0).")
        return

    await asyncio.sleep(10)
    while not stop_event.is_set():
        try:
            result = await asyncio.to_thread(run_integrity_sweep)
            logger.info(
                "Integrity sweep complete: %s checked, %s failed",
                result["checked"],
                result["failed"],
            )
        except Exception as exc:
            logger.warning("Integrity sweep failed: %s", exc)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue
