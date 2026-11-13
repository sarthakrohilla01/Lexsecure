"""Audit Trail API Endpoints"""

import csv
import hashlib
import io
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.security.abac import get_current_user
from app.audit.logger import record_audit_event
from app.utils.time import utcnow

router = APIRouter(prefix="/audit", tags=["Audit & Compliance"])

_EXPORT_COLUMNS = [
    "id", "timestamp", "user_id", "user_email", "user_role",
    "ip_address", "action", "target_type", "target_id", "details", "status",
]


def _serialize(entry: AuditLog) -> dict:
    return {
        "id": entry.id,
        "timestamp": entry.timestamp,
        "user_id": entry.user_id,
        "user_email": entry.user_email,
        "user_role": entry.user_role,
        "ip_address": entry.ip_address,
        "action": entry.action,
        "target_type": entry.target_type,
        "target_id": entry.target_id,
        "details": entry.details,
        "status": entry.status,
    }


def _scoped_query(
    db: Session,
    current_user: User,
    action: Optional[str],
    status: Optional[str],
):
    """Shared ABAC scoping for list & export: non-supervisors only ever see their own actions; Supervisors/Admins see all."""
    query = db.query(AuditLog)
    if current_user.role not in [UserRole.ADMINISTRATOR, UserRole.SUPERVISOR]:
        query = query.filter(AuditLog.user_id == current_user.id)
    if action:
        query = query.filter(AuditLog.action == action)
    if status:
        query = query.filter(AuditLog.status == status)
    return query


@router.get("")
def list_audit_logs(
    action: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves chronological audit events. Enforces that non-supervisors only see their own actions, whereas Supervisors/Admins see all events."""
    logs = (
        _scoped_query(db, current_user, action, status)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [_serialize(entry) for entry in logs]


@router.get("/export")
def export_audit_logs(
    format: str = "csv",
    action: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    fmt = format.lower().strip()
    if fmt not in ("csv", "json"):
        raise HTTPException(status_code=422, detail="format must be 'csv' or 'json'")

    logs = (
        _scoped_query(db, current_user, action, status)
        .order_by(AuditLog.timestamp.desc())
        .all()
    )
    rows = [_serialize(entry) for entry in logs]
    exported_at = utcnow()

    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(_EXPORT_COLUMNS)
        for r in rows:
            writer.writerow([
                r["id"],
                r["timestamp"].isoformat() if r["timestamp"] else "",
                r["user_id"],
                r["user_email"],
                r["user_role"],
                r["ip_address"],
                r["action"],
                r["target_type"],
                r["target_id"],
                r["details"],
                r["status"],
            ])
        content = ("\ufeff" + buf.getvalue()).encode("utf-8")
        media_type = "text/csv; charset=utf-8"
    else:
        payload = {
            "export": {
                "system": "LEXSECURE",
                "generated_at": exported_at.isoformat() + "Z",
                "generated_by": current_user.email,
                "scope": (
                    "ALL_EVENTS" if current_user.role in [UserRole.ADMINISTRATOR, UserRole.SUPERVISOR]
                    else f"USER_EVENTS_ONLY:{current_user.email}"
                ),
                "filters": {"action": action or None, "status": status or None},
                "count": len(rows),
            },
            "events": [
                {**r, "timestamp": r["timestamp"].isoformat() if r["timestamp"] else None}
                for r in rows
            ],
        }
        content = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
        media_type = "application/json"

    digest = hashlib.sha256(content).hexdigest()
    filename = f"lexsecure_audit_trail_{exported_at.strftime('%Y%m%d_%H%M%S')}.{fmt}"

    record_audit_event(
        db=db,
        action="AUDIT_EXPORTED",
        target_type="AUDIT_TRAIL",
        target_id=fmt.upper(),
        details=(
            f"Exported {len(rows)} audit events as {fmt.upper()} "
            f"(filters: action={action or 'none'}, status={status or 'none'}). "
            f"SHA-256: {digest}"
        ),
        user=current_user,
        status="SUCCESS"
    )

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Export-SHA256": digest,
            "X-Export-Count": str(len(rows)),
            "Cache-Control": "no-store",
        },
    )


@router.get("/document/{document_id}")
def get_document_audit_trail(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns lifecycle audit history for a specific document."""
    logs = db.query(AuditLog).filter(
        AuditLog.target_type == "DOCUMENT",
        AuditLog.target_id == str(document_id)
    ).order_by(AuditLog.timestamp.asc()).all()

    return [
        {
            "id": entry.id,
            "timestamp": entry.timestamp,
            "user_email": entry.user_email,
            "user_role": entry.user_role,
            "action": entry.action,
            "details": entry.details,
            "status": entry.status
        }
        for entry in logs
    ]
