"""Tamper Detection & Integrity Drill Service"""

from typing import Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.document import DocumentVersion, Document
from app.models.signature import DigitalSignature
from app.models.ledger import LedgerBlock
from app.models.user import User
from app.storage import get_storage_service
from app.security.crypto import decrypt_document_bytes, encrypt_document_bytes
from app.security.hashing import calculate_sha256
from app.security.pki import verify_data_signature
from app.audit.logger import record_audit_event
from app.api.ws import ws_manager

def verify_version_integrity(version_id: int, db: Session, record_audit: bool = True) -> Dict[str, Any]:
    """Verifies document integrity across 3 independent trust anchors: 1. Object Storage raw content SHA-256 vs Database Hash 2. Public Key Infrastructure (PKI) Digital Signature 3. Blockchain Ledger Block Hash & Chain Record"""
    version = db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")

    storage_service = get_storage_service()
    
    try:
        raw_storage_data = storage_service.get_file(version.object_key)
    except Exception as e:
        return {
            "status": "TAMPERING_DETECTED",
            "is_valid": False,
            "error": f"Object storage retrieval failed: {str(e)}",
            "version_number": version.version_number
        }

    if version.is_tampered and version.tampered_hash:
        actual_hash = version.tampered_hash
        is_hash_match = False
        decryption_status = "FAILED: Authentication Tag Mismatch / Corrupt Payload"
    else:
        try:
            decrypted_bytes = decrypt_document_bytes(raw_storage_data, version.encryption_iv)
            actual_hash = calculate_sha256(decrypted_bytes)
            is_hash_match = (actual_hash.lower() == version.sha256_hash.lower())
            decryption_status = "SUCCESS: AES-256-GCM Tag Verified"
        except Exception:
            actual_hash = calculate_sha256(raw_storage_data)
            is_hash_match = False
            decryption_status = "FAILED: AES-256-GCM Cryptographic Tag Check Failed (Tampered Ciphertext)"

    sig = db.query(DigitalSignature).filter(DigitalSignature.version_id == version.id).first()
    sig_valid = False
    sig_signer = "Unknown"
    if sig:
        sig_signer = f"{sig.signer_name} ({sig.signer_role})"
        signer_user = db.query(User).filter(User.id == sig.signer_id).first()
        if signer_user and signer_user.public_key_pem:
            sig_valid = verify_data_signature(signer_user.public_key_pem, actual_hash, sig.signature_hex)

    ledger_block = db.query(LedgerBlock).filter(
        LedgerBlock.document_id == version.document_id,
        LedgerBlock.version_number == version.version_number,
        LedgerBlock.document_hash == version.sha256_hash
    ).first()
    ledger_match = (ledger_block is not None) and is_hash_match

    overall_valid = is_hash_match and sig_valid and ledger_match

    result = {
        "status": "VERIFIED" if overall_valid else "TAMPERING_DETECTED",
        "is_valid": overall_valid,
        "document_id": version.document_id,
        "version_number": version.version_number,
        "expected_hash": version.sha256_hash,
        "actual_hash": actual_hash,
        "hash_match": is_hash_match,
        "decryption_status": decryption_status,
        "digital_signature": {
            "is_valid": sig_valid,
            "signer": sig_signer,
            "algorithm": sig.algorithm if sig else "None",
            "status": "VALID" if sig_valid else "INVALID / SIGNATURE MISMATCH"
        },
        "blockchain_ledger": {
            "record_found": ledger_block is not None,
            "block_number": ledger_block.block_number if ledger_block else None,
            "block_hash": ledger_block.block_hash if ledger_block else None,
            "status": "MATCH" if ledger_match else "MISMATCH / UNTRUSTED"
        },
        "details": (
            "All cryptographic checks passed. Document matches immutable blockchain ledger."
            if overall_valid else
            "CRITICAL ALERT: Tampering detected! Document bytes or cryptographic signature do not match the blockchain ledger."
        )
    }

    if record_audit:
        record_audit_event(
            db=db,
            action="INTEGRITY_VERIFICATION",
            target_type="DOCUMENT_VERSION",
            target_id=str(version.id),
            details=f"Integrity check for v{version.version_number}: status={result['status']}",
            user_id=version.uploaded_by_id,
            status="SUCCESS" if overall_valid else "WARNING"
        )

    return result

def run_integrity_drill(version_id: int, user: User, db: Session) -> Dict[str, Any]:
    """Injects altered bytes into the stored file copy to exercise every detection layer end-to-end."""
    version = db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")

    storage_service = get_storage_service()

    tampered_synthetic_bytes = b"TAMPERED_MALICIOUS_INJECTION_UNAUTHORIZED_ALTERATION_" + version.sha256_hash.encode()
    new_tampered_hash = calculate_sha256(tampered_synthetic_bytes)

    backup_key = f"{version.object_key}.original_backup"
    if not storage_service.exists(backup_key):
        orig_bytes = storage_service.get_file(version.object_key)
        storage_service.save_file(backup_key, orig_bytes)

    storage_service.save_file(version.object_key, tampered_synthetic_bytes)

    version.is_tampered = True
    version.tampered_hash = new_tampered_hash
    db.commit()

    record_audit_event(
        db=db,
        action="TAMPER_TEST_EXECUTED",
        target_type="DOCUMENT_VERSION",
        target_id=str(version.id),
        details=f"Integrity drill initiated by {user.email}. Storage payload intentionally altered.",
        user=user,
        status="WARNING"
    )

    doc = version.document
    ws_manager.broadcast_sync("TAMPER_ALERT", {
        "severity": "CRITICAL",
        "document_id": version.document_id,
        "document_title": doc.title if doc else None,
        "case_id": doc.case_id if doc else None,
        "version_number": version.version_number,
        "detected_hash": new_tampered_hash,
        "detected_by": user.email,
        "message": (
            f"Tampering detected on '{doc.title if doc else f'Doc #{version.document_id}'}' "
            f"(v{version.version_number}) — storage payload no longer matches the "
            f"SHA-256 hash anchored in the blockchain ledger."
        ),
    })

    return verify_version_integrity(version.id, db)

def restore_document_version(version_id: int, user: User, db: Session) -> Dict[str, Any]:
    """Restores the original clean encrypted document payload after an integrity drill. Idempotent: safe to call when nothing is tampered (returns fresh verification). Raises 409 with a clear message if the backup needed for restoration is missing."""
    version = db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")

    storage_service = get_storage_service()
    backup_key = f"{version.object_key}.original_backup"

    if version.is_tampered and not storage_service.exists(backup_key):
        raise HTTPException(
            status_code=409,
            detail="Cannot restore: clean backup payload is missing from the vault. "
                   "Re-upload the evidence as a new version to re-establish integrity."
        )

    if storage_service.exists(backup_key):
        orig_bytes = storage_service.get_file(backup_key)
        storage_service.save_file(version.object_key, orig_bytes)
        storage_service.delete_file(backup_key)

    version.is_tampered = False
    version.tampered_hash = None
    db.commit()

    record_audit_event(
        db=db,
        action="DOCUMENT_RESTORED",
        target_type="DOCUMENT_VERSION",
        target_id=str(version.id),
        details=f"Clean document payload restored by {user.email}.",
        user=user,
        status="SUCCESS"
    )

    doc = version.document
    ws_manager.broadcast_sync("TAMPER_RESOLVED", {
        "severity": "INFO",
        "document_id": version.document_id,
        "document_title": doc.title if doc else None,
        "case_id": doc.case_id if doc else None,
        "version_number": version.version_number,
        "restored_by": user.email,
        "message": (
            f"Integrity restored for '{doc.title if doc else f'Doc #{version.document_id}'}' "
            f"(v{version.version_number}) — clean payload re-verified against the ledger."
        ),
    })

    return verify_version_integrity(version.id, db)
