"""Document Management & Cryptographic Upload API"""

import io
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.document import Document, DocumentVersion, DocumentMetadata
from app.models.signature import DigitalSignature
from app.models.case import Case
from app.models.user import User, UserRole
from app.schemas.document import DocumentSummaryDTO, DocumentDetailDTO, DocumentVersionDTO, DigitalSignatureDTO, DocumentMetadataDTO, SignRequest
from app.security.abac import get_current_user, verify_case_access, verify_document_access, get_authorized_case_ids
from app.security.crypto import decrypt_document_bytes
from app.security.pki import sign_data_hash, load_private_key_pem
from app.services.doc_processor import process_and_store_document, ensure_user_pki_keys
from app.storage import get_storage_service
from app.blockchain.ledger_service import record_ledger_block
from app.audit.logger import record_audit_event
from app.services.steganography import inject_watermark_bytes, is_text_like
from app.models.approval import DualAuthRequest
from app.utils.time import utcnow

router = APIRouter(prefix="/documents", tags=["Document Lifecycle"])

_DUAL_AUTH_BYPASS_ROLES = [UserRole.SUPERVISOR, UserRole.ADMINISTRATOR]


def _resolve_unlock_token(request: Request, query_token: Optional[str] = None) -> Optional[str]:
    """Unlock token travels in the X-Unlock-Token header (preferred — query strings land in server logs); the ?unlock_token= query param is kept for backward compatibility."""
    if request is not None:
        header_token = request.headers.get("X-Unlock-Token")
        if header_token:
            return header_token.strip()
    return query_token.strip() if query_token else None


def _get_valid_dual_grant(doc: Document, user: User, db: Session,
                          token: Optional[str]):
    """Returns the live APPROVED + unexpired grant for this user+document, or None. Expired grants are treated as absent (fail closed)."""
    if not token:
        return None
    grant = db.query(DualAuthRequest).filter(
        DualAuthRequest.document_id == doc.id,
        DualAuthRequest.requester_id == user.id,
        DualAuthRequest.unlock_token == token,
        DualAuthRequest.status == "APPROVED"
    ).first()
    if not grant:
        return None
    if grant.expires_at and grant.expires_at < utcnow():
        return None
    return grant


def _enforce_dual_auth(doc: Document, user: User, db: Session,
                       request: Request, query_token: Optional[str] = None):
    """Two-Man Rule gate for viewing/downloading. Supervisors/Admins bypass. Everyone else needs a live supervisor grant (unlock token). Returns the grant (or None for bypass roles). Raises 403 with a machine-readable dict detail the UI keys off."""
    if not doc.requires_dual_auth:
        return None
    if user.role in _DUAL_AUTH_BYPASS_ROLES:
        return None
    grant = _get_valid_dual_grant(doc, user, db,
                                  _resolve_unlock_token(request, query_token))
    if grant:
        return grant
    raise HTTPException(
        status_code=403,
        detail={
            "error": "TWO_MAN_RULE_REQUIRED",
            "message": (f"Document '{doc.title}' is sealed under the Two-Man Rule. "
                        "Supervisor approval is required before viewing or download."),
            "requires_dual_auth": True,
            "document_id": doc.id,
            "document_title": doc.title,
        }
    )

@router.get("", response_model=List[DocumentSummaryDTO])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists documents across all authorized cases. Documents from unauthorized cases are filtered out at the SQL query level."""
    auth_case_ids = get_authorized_case_ids(current_user, db)
    if not auth_case_ids:
        return []

    docs = db.query(Document).filter(Document.case_id.in_(auth_case_ids)).order_by(Document.updated_at.desc()).all()
    results = []
    for d in docs:
        latest_ver = db.query(DocumentVersion).filter(
            DocumentVersion.document_id == d.id,
            DocumentVersion.version_number == d.current_version
        ).first()

        results.append({
            "id": d.id,
            "case_id": d.case_id,
            "title": d.title,
            "document_type": d.document_type,
            "classification": d.classification,
            "current_version": d.current_version,
            "status": d.status,
            "uploaded_by_name": d.uploader.full_name if d.uploader else "Unknown",
            "created_at": d.created_at,
            "latest_hash": latest_ver.sha256_hash if latest_ver else None,
            "is_tampered": latest_ver.is_tampered if latest_ver else False,
            "requires_dual_auth": d.requires_dual_auth
        })
    return results

@router.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    case_id: str = Form(...),
    title: Optional[str] = Form(None),
    document_type: Optional[str] = Form(None),
    classification: Optional[str] = Form("RESTRICTED"),
    change_reason: Optional[str] = Form("Initial case filing"),
    requires_dual_auth: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Executes real cryptographic document ingestion pipeline: Malware Scan -> OCR -> Classification -> AES-256 -> SHA-256 -> Sign -> Object Store -> Blockchain Ledger -> Vector Index. Only Supervisors/Admins may seal an upload under the Two-Man Rule at ingest."""
    verify_case_access(current_user, case_id, db, request=request, action="DOCUMENT_UPLOAD")

    if requires_dual_auth and current_user.role not in [UserRole.SUPERVISOR, UserRole.ADMINISTRATOR]:
        raise HTTPException(
            status_code=403,
            detail="Only Supervisors/Admins can seal a document under the Two-Man Rule."
        )

    file_bytes = await file.read()
    result = process_and_store_document(
        db=db,
        user=current_user,
        case_id=case_id,
        file_name=file.filename,
        file_bytes=file_bytes,
        mime_type=file.content_type or "application/octet-stream",
        title=title,
        document_type_override=document_type,
        classification=classification,
        change_reason=change_reason,
        requires_dual_auth=requires_dual_auth
    )
    return result

@router.get("/{document_id}", response_model=DocumentDetailDTO)
def get_document_details(
    document_id: int,
    request: Request,
    unlock_token: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns full document details, version history, signatures, and cryptographic metadata. Enforces ABAC check plus the Two-Man Rule gate for sealed documents (supervisor bypass, otherwise a live unlock token is required)."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    verify_document_access(current_user, doc, db, request=request)
    grant = _enforce_dual_auth(doc, current_user, db, request, unlock_token)

    versions = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc.id
    ).order_by(DocumentVersion.version_number.desc()).all()

    version_dtos = []
    for v in versions:
        sigs = db.query(DigitalSignature).filter(DigitalSignature.version_id == v.id).all()
        sig_dtos = [
            DigitalSignatureDTO(
                signer_name=s.signer_name,
                signer_role=s.signer_role,
                signature_hex=s.signature_hex,
                algorithm=s.algorithm,
                signed_at=s.signed_at,
                is_valid=s.is_valid,
                certificate_serial=s.certificate_serial
            ) for s in sigs
        ]

        meta_dto = None
        if v.metadata_record:
            m = v.metadata_record
            meta_dto = DocumentMetadataDTO(
                page_count=m.page_count,
                ocr_applied=m.ocr_applied,
                malware_scanned=m.malware_scanned,
                scan_clean=m.scan_clean,
                ai_classification=m.ai_classification,
                ai_confidence=m.ai_confidence,
                extracted_keywords=m.extracted_keywords,
                summary=m.summary
            )

        version_dtos.append(
            DocumentVersionDTO(
                id=v.id,
                version_number=v.version_number,
                file_name=v.file_name,
                file_size=v.file_size,
                mime_type=v.mime_type,
                sha256_hash=v.sha256_hash,
                change_reason=v.change_reason,
                created_at=v.created_at,
                uploader_name=v.uploader.full_name if v.uploader else "Unknown",
                is_tampered=v.is_tampered,
                metadata=meta_dto,
                signatures=sig_dtos
            )
        )

    record_audit_event(
        db=db,
        action="DOCUMENT_VIEWED",
        target_type="DOCUMENT",
        target_id=str(doc.id),
        details=f"Viewed document {doc.title} (v{doc.current_version})",
        user=current_user,
        status="SUCCESS"
    )

    latest_hash = version_dtos[0].sha256_hash if version_dtos else None
    is_tampered = version_dtos[0].is_tampered if version_dtos else False

    can_sign = current_user.role in [UserRole.FORENSIC_EXPERT, UserRole.INVESTIGATOR, UserRole.LEGAL_OFFICER, UserRole.SUPERVISOR]
    can_approve = current_user.role in [UserRole.SUPERVISOR, UserRole.LEGAL_OFFICER, UserRole.ADMINISTRATOR]
    signed_by_me = False
    if version_dtos:
        current_version_id = version_dtos[0].id
        signed_by_me = db.query(DigitalSignature).filter(
            DigitalSignature.version_id == current_version_id,
            DigitalSignature.signer_id == current_user.id
        ).first() is not None

    return {
        "id": doc.id,
        "case_id": doc.case_id,
        "title": doc.title,
        "document_type": doc.document_type,
        "classification": doc.classification,
        "current_version": doc.current_version,
        "status": doc.status,
        "uploaded_by_name": doc.uploader.full_name if doc.uploader else "Unknown",
        "created_at": doc.created_at,
        "latest_hash": latest_hash,
        "is_tampered": is_tampered,
        "requires_dual_auth": doc.requires_dual_auth,
        "dual_auth_granted": grant is not None,
        "dual_auth_expires_at": grant.expires_at if grant else None,
        "versions": version_dtos,
        "can_edit": True,
        "can_sign": can_sign,
        "can_approve": can_approve,
        "signed_by_me": signed_by_me
    }

@router.patch("/{document_id}/dual-auth")
def set_dual_auth(
    document_id: int,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Seal or unseal a document under the Two-Man Rule. Supervisors/Admins only. Body: {"requires_dual_auth": true/false}. Sealing is audit-logged; outstanding grants keep working until expiry."""
    if current_user.role not in [UserRole.SUPERVISOR, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only Supervisors/Admins can change the Two-Man Rule seal.")
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    verify_document_access(current_user, doc, db, request=request)
    sealed = bool(payload.get("requires_dual_auth", True))
    doc.requires_dual_auth = sealed
    db.commit()
    record_audit_event(
        db=db,
        action="DUAL_AUTH_SEALED" if sealed else "DUAL_AUTH_UNSEALED",
        target_type="DOCUMENT",
        target_id=str(doc.id),
        details=f"Two-Man Rule {'SEALED on' if sealed else 'lifted from'} '{doc.title}' by {current_user.full_name}",
        user=current_user,
        status="WARNING" if sealed else "SUCCESS"
    )
    return {"status": "SUCCESS", "document_id": doc.id, "requires_dual_auth": sealed}

@router.post("/{document_id}/versions")
async def create_new_version(
    document_id: int,
    request: Request,
    file: UploadFile = File(...),
    change_reason: str = Form("Updated document version"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Uploads an incremented version (v2, v3, ...) for an existing document. Calculates distinct SHA-256 hash and appends new blockchain block."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    verify_document_access(current_user, doc, db, request=request)

    file_bytes = await file.read()
    result = process_and_store_document(
        db=db,
        user=current_user,
        case_id=doc.case_id,
        file_name=file.filename,
        file_bytes=file_bytes,
        mime_type=file.content_type or "application/octet-stream",
        title=doc.title,
        document_type_override=doc.document_type,
        classification=doc.classification,
        change_reason=change_reason,
        existing_document_id=doc.id
    )
    return result

@router.post("/{document_id}/sign")
def sign_document(
    document_id: int,
    payload: SignRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Digitally signs the current version of the document using the officer's private RSA key. Records signature and appends SIGNED event block to Blockchain Ledger."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    verify_document_access(current_user, doc, db, request=request)

    version = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc.id,
        DocumentVersion.version_number == doc.current_version
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")

    user = ensure_user_pki_keys(current_user, db)
    signature_hex = sign_data_hash(load_private_key_pem(user.private_key_pem), version.sha256_hash)

    sig = DigitalSignature(
        version_id=version.id,
        signer_id=user.id,
        signer_name=user.full_name,
        signer_role=user.role.value,
        signature_hex=signature_hex,
        algorithm="SHA256withRSA-2048",
        is_valid=True,
        certificate_serial=f"NCRB-SIG-{version.id:04d}-{user.id}"
    )
    db.add(sig)
    doc.status = "SIGNED"
    db.commit()

    ledger_block = record_ledger_block(
        db=db,
        document_id=doc.id,
        case_id=doc.case_id,
        version_number=version.version_number,
        document_hash=version.sha256_hash,
        event_type="SIGNED",
        user_id=user.id,
        user_email=user.email,
        user_role=user.role.value
    )

    record_audit_event(
        db=db,
        action="DOCUMENT_SIGNED",
        target_type="DOCUMENT",
        target_id=str(doc.id),
        details=f"Digitally signed v{version.version_number} by {user.full_name} ({user.role.value}). Ledger Block #{ledger_block.block_number}",
        user=user,
        status="SUCCESS"
    )

    return {
        "status": "SUCCESS",
        "message": "Document digitally signed successfully",
        "signature_hex": signature_hex,
        "ledger_block_number": ledger_block.block_number
    }

@router.delete("/{document_id}/sign")
def unsign_document(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    signer_id: Optional[int] = None
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    verify_document_access(current_user, doc, db, request=request)

    version = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc.id,
        DocumentVersion.version_number == doc.current_version
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")

    if signer_id is not None:
        if current_user.role not in [UserRole.SUPERVISOR, UserRole.ADMINISTRATOR]:
            raise HTTPException(status_code=403, detail="Only Supervisors/Admins can revoke another officer's signature.")
        target_signer = signer_id
    else:
        target_signer = current_user.id

    signatures = db.query(DigitalSignature).filter(
        DigitalSignature.version_id == version.id,
        DigitalSignature.signer_id == target_signer
    ).all()
    if not signatures:
        raise HTTPException(
            status_code=404,
            detail="No removable signature found on the current version for that account."
        )

    removed = [f"{s.signer_name} ({s.signer_role})" for s in signatures]
    for s in signatures:
        db.delete(s)
    db.flush()

    remaining = db.query(DigitalSignature).filter(DigitalSignature.version_id == version.id).count()
    if remaining == 0 and doc.status == "SIGNED":
        doc.status = "UNDER_REVIEW"
    db.commit()

    ledger_block = record_ledger_block(
        db=db,
        document_id=doc.id,
        case_id=doc.case_id,
        version_number=version.version_number,
        document_hash=version.sha256_hash,
        event_type="SIGNATURE_REVOKED",
        user_id=current_user.id,
        user_email=current_user.email,
        user_role=current_user.role.value
    )

    record_audit_event(
        db=db,
        action="SIGNATURE_REVOKED",
        target_type="DOCUMENT",
        target_id=str(doc.id),
        details=f"Signature(s) revoked on v{version.version_number} by {current_user.full_name}: {', '.join(removed)}. Ledger Block #{ledger_block.block_number}",
        user=current_user,
        status="WARNING"
    )

    return {
        "status": "SUCCESS",
        "message": "Signature revoked successfully",
        "revoked": removed,
        "document_status": doc.status,
        "ledger_block_number": ledger_block.block_number
    }

@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    request: Request,
    version: Optional[int] = None,
    unlock_token: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Secure retrieval: Fetches encrypted ciphertext from object storage, decrypts it via AES-256-GCM using system key, and streams original plaintext."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    verify_document_access(current_user, doc, db, request=request)

    grant = _enforce_dual_auth(doc, current_user, db, request, unlock_token)

    target_version_num = version or doc.current_version
    doc_ver = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc.id,
        DocumentVersion.version_number == target_version_num
    ).first()
    if not doc_ver:
        raise HTTPException(status_code=404, detail="Requested version not found")

    storage_service = get_storage_service()
    try:
        encrypted_bytes = storage_service.get_file(doc_ver.object_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Stored evidence payload not found in vault.")

    if doc_ver.is_tampered:
        raise HTTPException(
            status_code=409,
            detail="Document payload is in a TAMPERED state. "
                   "Restore the clean version before downloading."
        )

    try:
        decrypted_bytes = decrypt_document_bytes(encrypted_bytes, doc_ver.encryption_iv)
    except Exception:
        raise HTTPException(
            status_code=409,
            detail="Decryption failed: stored payload does not match its cryptographic seal. "
                   "The evidence may have been altered outside the system."
        )

    watermarked = False
    download_bytes = decrypted_bytes
    if is_text_like(decrypted_bytes):
        download_bytes = inject_watermark_bytes(
            decrypted_bytes,
            current_user.email,
            current_user.id,
            doc.id,
            doc_ver.version_number,
            utcnow().isoformat()
        )
        watermarked = True

    record_audit_event(
        db=db,
        action="DOCUMENT_DOWNLOADED",
        target_type="DOCUMENT",
        target_id=str(doc.id),
        details=(f"Downloaded and decrypted {doc_ver.file_name} (v{doc_ver.version_number})"
                 + (" with invisible leak-tracker watermark" if watermarked else "")
                 + (f" under Two-Man Rule grant by supervisor (req #{grant.id})" if grant else "")),
        user=current_user,
        status="SUCCESS"
    )

    return StreamingResponse(
        io.BytesIO(download_bytes),
        media_type=doc_ver.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{doc_ver.file_name}"'}
    )
