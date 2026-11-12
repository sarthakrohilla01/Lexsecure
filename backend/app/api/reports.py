"""Reports & Court Submission Package API"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.case import Case
from app.models.document import Document, DocumentVersion
from app.models.signature import DigitalSignature
from app.models.ledger import LedgerBlock
from app.models.user import User
from app.security.abac import get_current_user, verify_case_access

router = APIRouter(prefix="/reports", tags=["Reporting & Court Packages"])

@router.get("/court-package/{case_id}")
def generate_court_submission_package(
    case_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generates a formal Evidentiary Court Submission Manifest under Section 65B Indian Evidence Act / BSA. Contains document checksums, digital signature verifications, and blockchain ledger block numbers."""
    case = verify_case_access(current_user, case_id, db, request=request)

    docs = db.query(Document).filter(Document.case_id == case_id).all()
    manifest_entries = []

    for d in docs:
        versions = db.query(DocumentVersion).filter(DocumentVersion.document_id == d.id).order_by(DocumentVersion.version_number.asc()).all()
        for v in versions:
            sigs = db.query(DigitalSignature).filter(DigitalSignature.version_id == v.id).all()
            ledger_block = db.query(LedgerBlock).filter(
                LedgerBlock.document_id == d.id,
                LedgerBlock.version_number == v.version_number
            ).first()

            manifest_entries.append({
                "document_id": d.id,
                "document_title": d.title,
                "document_type": d.document_type,
                "version": f"v{v.version_number}",
                "file_name": v.file_name,
                "file_size_bytes": v.file_size,
                "sha256_hash": v.sha256_hash,
                "created_at": v.created_at.isoformat(),
                "uploaded_by": v.uploader.full_name if v.uploader else "Unknown",
                "signatures": [
                    {
                        "signer": s.signer_name,
                        "role": s.signer_role,
                        "algorithm": s.algorithm,
                        "signed_at": s.signed_at.isoformat(),
                        "is_valid": s.is_valid
                    }
                    for s in sigs
                ],
                "blockchain_notarization": {
                    "block_number": ledger_block.block_number if ledger_block else None,
                    "block_hash": ledger_block.block_hash if ledger_block else None,
                    "chaincode_tx_id": ledger_block.chaincode_tx_id if ledger_block else None
                }
            })

    return {
        "court_package_id": f"COURT-PKG-{case.id}",
        "jurisdiction": "National Crime Records Bureau / Women Safety Division, Ministry of Home Affairs",
        "case_id": case.id,
        "case_title": case.title,
        "department": case.department,
        "generated_by": current_user.full_name,
        "generated_by_role": current_user.role.value,
        "evidentiary_standard": "Section 65B Indian Evidence Act / Bharatiya Sakshya Adhiniyam (BSA) 2023 Digital Certificate",
        "total_documents": len(docs),
        "total_manifest_entries": len(manifest_entries),
        "manifest": manifest_entries
    }
