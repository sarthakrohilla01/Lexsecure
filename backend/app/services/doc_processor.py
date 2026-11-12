"""Document ingestion pipeline: scan, extract, encrypt, sign, ledger, index."""

import os
import uuid
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, UploadFile

from app.models.user import User
from app.models.case import Case
from app.models.document import Document, DocumentVersion, DocumentMetadata
from app.models.signature import DigitalSignature
from app.storage import get_storage_service
from app.security.crypto import encrypt_document_bytes, encrypt_secret
from app.security.hashing import calculate_sha256
from app.security.pki import generate_key_pair, sign_data_hash, load_private_key_pem
from app.blockchain.ledger_service import record_ledger_block
from app.services.ocr import extract_text_from_file
from app.services.classifier import classify_document
from app.services.malware import scan_upload
from app.ai.vector_store import index_document_chunks
from app.audit.logger import record_audit_event
from app.api.ws import ws_manager

ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt", "jpg", "jpeg", "png"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

def validate_file(file_name: str, file_size: int):
    ext = file_name.lower().split(".")[-1] if "." in file_name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File extension '.{ext}' is not supported. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum limit of {MAX_FILE_SIZE_BYTES // (1024*1024)}MB."
        )

def ensure_user_pki_keys(user: User, db: Session) -> User:
    """Private key is encrypted at rest before it is stored."""
    if not user.private_key_pem or not user.public_key_pem:
        priv_pem, pub_pem = generate_key_pair()
        user.private_key_pem = encrypt_secret(priv_pem)
        user.public_key_pem = pub_pem
        db.commit()
        db.refresh(user)
    return user

def process_and_store_document(
    db: Session,
    user: User,
    case_id: str,
    file_name: str,
    file_bytes: bytes,
    mime_type: str,
    title: Optional[str] = None,
    document_type_override: Optional[str] = None,
    classification: str = "RESTRICTED",
    requires_dual_auth: bool = False,
    change_reason: str = "Initial upload",
    existing_document_id: Optional[int] = None
) -> Dict[str, Any]:
    file_size = len(file_bytes)
    validate_file(file_name, file_size)

    scan = scan_upload(file_bytes, file_name, mime_type)
    if not scan.clean:
        record_audit_event(
            db=db,
            action="MALWARE_DETECTED",
            target_type="FILE",
            target_id=file_name,
            details=(
                f"Upload blocked by {scan.engine} scanner for {user.email}. "
                f"Signature: {scan.signature}"
            ),
            user=user,
            status="BLOCKED",
        )
        raise HTTPException(
            status_code=400,
            detail=f"Security Alert: malware detected ({scan.signature}). Upload blocked.",
        )

    extracted_text, page_count, ocr_applied = extract_text_from_file(file_bytes, file_name, mime_type)

    if document_type_override:
        doc_type, confidence = document_type_override, 1.0
    else:
        doc_type, confidence = classify_document(file_name, extracted_text)

    sha256_hash = calculate_sha256(file_bytes)

    user = ensure_user_pki_keys(user, db)
    signature_hex = sign_data_hash(load_private_key_pem(user.private_key_pem), sha256_hash)

    encrypted_bytes, iv_hex, tag_hex = encrypt_document_bytes(file_bytes)

    storage_service = get_storage_service()
    object_key = f"{case_id}/{uuid.uuid4().hex}_{file_name}.enc"
    storage_service.save_file(object_key, encrypted_bytes)

    if existing_document_id:
        doc = db.query(Document).filter(Document.id == existing_document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Parent document not found for versioning")
        new_version_num = doc.current_version + 1
        doc.current_version = new_version_num
        doc.status = "UNDER_REVIEW"
        event_type = "VERSION_ADDED"
    else:
        doc = Document(
            case_id=case_id,
            title=title or file_name.rsplit(".", 1)[0].replace("_", " "),
            document_type=doc_type,
            classification=classification,
            requires_dual_auth=requires_dual_auth,
            current_version=1,
            status="UNDER_REVIEW",
            uploaded_by_id=user.id
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        new_version_num = 1
        event_type = "CREATED"

    doc_version = DocumentVersion(
        document_id=doc.id,
        version_number=new_version_num,
        object_key=object_key,
        file_name=file_name,
        file_size=file_size,
        mime_type=mime_type or "application/octet-stream",
        sha256_hash=sha256_hash,
        encryption_iv=iv_hex,
        encryption_tag=tag_hex,
        change_reason=change_reason,
        uploaded_by_id=user.id
    )
    db.add(doc_version)
    db.commit()
    db.refresh(doc_version)

    keywords = [w.strip() for w in extracted_text.split() if len(w) > 5][:10]
    metadata_record = DocumentMetadata(
        version_id=doc_version.id,
        extracted_text=extracted_text,
        page_count=page_count,
        ocr_applied=ocr_applied,
        malware_scanned=True,
        scan_clean=True,
        ai_classification=doc_type,
        ai_confidence=confidence,
        extracted_keywords=", ".join(set(keywords)),
        summary=extracted_text[:280] + ("..." if len(extracted_text) > 280 else ""),
        scan_engine=scan.engine,
        scan_signature=scan.signature,
    )
    db.add(metadata_record)

    sig_record = DigitalSignature(
        version_id=doc_version.id,
        signer_id=user.id,
        signer_name=user.full_name,
        signer_role=user.role.value,
        signature_hex=signature_hex,
        algorithm="SHA256withRSA-2048",
        is_valid=True,
        certificate_serial=f"NCRB-CERT-{uuid.uuid4().hex[:8].upper()}"
    )
    db.add(sig_record)
    db.commit()

    ledger_block = record_ledger_block(
        db=db,
        document_id=doc.id,
        case_id=case_id,
        version_number=new_version_num,
        document_hash=sha256_hash,
        event_type=event_type,
        user_id=user.id,
        user_email=user.email,
        user_role=user.role.value
    )

    index_document_chunks(
        db=db,
        document_id=doc.id,
        version_number=new_version_num,
        case_id=case_id,
        text=f"{doc.title}\n{doc_type}\n{extracted_text}"
    )

    record_audit_event(
        db=db,
        action=f"DOCUMENT_{event_type}",
        target_type="DOCUMENT",
        target_id=str(doc.id),
        details=f"Uploaded {file_name} (v{new_version_num}) into {case_id}. Hash: {sha256_hash[:16]}... Ledger Block #{ledger_block.block_number}",
        user=user,
        status="SUCCESS"
    )

    ws_manager.broadcast_sync("DOCUMENT_UPLOADED", {
        "severity": "INFO",
        "document_id": doc.id,
        "document_title": doc.title,
        "case_id": case_id,
        "version_number": new_version_num,
        "classification": classification,
        "uploaded_by": user.email,
        "ledger_block_number": ledger_block.block_number,
        "message": f"'{doc.title}' (v{new_version_num}) secured into {case_id} — hash anchored in ledger block #{ledger_block.block_number}.",
    })

    return {
        "document_id": doc.id,
        "version_id": doc_version.id,
        "version_number": new_version_num,
        "title": doc.title,
        "document_type": doc_type,
        "classification": classification,
        "file_name": file_name,
        "file_size": file_size,
        "sha256_hash": sha256_hash,
        "signature_hex": signature_hex,
        "encryption": "AES-256-GCM",
        "ocr_applied": ocr_applied,
        "ledger_block_number": ledger_block.block_number,
        "status": doc.status
    }
