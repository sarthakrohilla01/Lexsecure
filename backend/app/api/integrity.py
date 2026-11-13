"""Integrity & Tamper Detection API"""

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.audit.logger import record_audit_event
from app.blockchain.ledger_service import verify_ledger_chain_integrity
from app.database.session import get_db
from app.models.document import DocumentVersion
from app.models.ledger import LedgerBlock
from app.models.user import User, UserRole
from app.schemas.document import IntegrityReportDTO
from app.security.abac import get_current_user, verify_document_access, get_authorized_case_ids
from app.services.steganography import extract_watermark_bytes
from app.services.tamper_service import (
    verify_version_integrity,
    run_integrity_drill,
    restore_document_version
)

router = APIRouter(prefix="/integrity", tags=["Integrity & Blockchain"])

@router.post("/verify/{version_id}", response_model=IntegrityReportDTO)
def verify_document(
    version_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Verifies document integrity across AES decryption, SHA-256 hash comparison, PKI digital signature verification, and blockchain ledger block matching."""
    version = db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")

    verify_document_access(current_user, version.document, db, request=request)
    return verify_version_integrity(version_id, db)

@router.post("/tamper-test/{version_id}", response_model=IntegrityReportDTO)
def execute_tamper_test(
    version_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.user import UserRole

    if current_user.role not in (UserRole.SUPERVISOR, UserRole.ADMINISTRATOR):
        raise HTTPException(status_code=403, detail="Only Supervisors/Admins may run integrity drills.")

    version = db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")

    verify_document_access(current_user, version.document, db, request=request)

    from app.audit.logger import record_audit_event
    record_audit_event(
        db=db,
        action="INTEGRITY_DRILL_STARTED",
        target_type="DOCUMENT",
        target_id=str(version.document_id),
        details=f"Integrity drill initiated on version {version_id} by {current_user.email}",
        user=current_user,
        status="WARNING",
    )
    return run_integrity_drill(version_id, current_user, db)

@router.post("/restore/{version_id}", response_model=IntegrityReportDTO)
def restore_tampered_document(
    version_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Restores the clean original encrypted payload after an integrity drill."""
    version = db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")

    verify_document_access(current_user, version.document, db, request=request)
    return restore_document_version(version_id, current_user, db)

@router.get("/ledger")
def get_ledger_blocks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Queries blocks in the permissioned blockchain ledger. ABAC-enforced: results are filtered to cases the requesting officer is assigned to. Supervisors/Admins see the full chain. The SYSTEM genesis block (no case data) is always included for chain anchoring."""
    authorized_case_ids = set(get_authorized_case_ids(current_user, db))
    authorized_case_ids.add("SYSTEM")

    blocks = (
        db.query(LedgerBlock)
        .filter(LedgerBlock.case_id.in_(authorized_case_ids))
        .order_by(LedgerBlock.block_number.asc())
        .all()
    )
    return [
        {
            "block_number": b.block_number,
            "timestamp": b.timestamp,
            "document_id": b.document_id,
            "case_id": b.case_id,
            "version_number": b.version_number,
            "document_hash": b.document_hash,
            "event_type": b.event_type,
            "user_email": b.user_email,
            "user_role": b.user_role,
            "previous_hash": b.previous_hash,
            "block_hash": b.block_hash,
            "chaincode_tx_id": b.chaincode_tx_id
        }
        for b in blocks
    ]

@router.get("/monitor")
def integrity_monitor_state(
    current_user: User = Depends(get_current_user),
):
    """Continuous monitoring status: interval, last sweep, failures found."""
    from app.services.integrity_monitor import monitor_status
    return monitor_status()


@router.post("/sweep")
def run_integrity_sweep_now(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Runs an on-demand integrity sweep across every stored version."""
    from app.models.user import UserRole
    from app.services.integrity_monitor import run_integrity_sweep

    if current_user.role not in (UserRole.SUPERVISOR, UserRole.ADMINISTRATOR):
        raise HTTPException(status_code=403, detail="Only Supervisors/Admins may trigger a sweep.")
    return run_integrity_sweep()


@router.get("/verify-chain")
def verify_blockchain_chain(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cryptographically verifies the continuity and block hashes of the entire ledger chain."""
    return verify_ledger_chain_integrity(db)

@router.post("/extract-watermark")
async def extract_watermark_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """LEAK INVESTIGATOR — Supervisors/Admins only. Analyzes an uploaded file for zero-width steganographic watermarks to identify which officer's download was leaked. Every extraction attempt is audit-logged (investigating the investigators)."""
    if current_user.role not in [UserRole.SUPERVISOR, UserRole.ADMINISTRATOR]:
        raise HTTPException(
            status_code=403,
            detail="Only Supervisors/Admins may run leak investigations."
        )
    content = await file.read()
    result = extract_watermark_bytes(content)
    record_audit_event(
        db=db,
        action="WATERMARK_EXTRACTED" if result.get("is_valid") else "WATERMARK_SCAN_EMPTY",
        target_type="FILE",
        target_id=file.filename or "upload",
        details=(f"Leak investigation on '{file.filename}': "
                 + (f"traced to {result.get('email')} (uid {result.get('user_id')}) "
                    f"via doc #{result.get('document_id')} download at {result.get('timestamp')}"
                    if result.get("is_valid") else f"no verifiable watermark ({result.get('error')})")),
        user=current_user,
        status="SUCCESS" if result.get("is_valid") else "WARNING"
    )
    return result
