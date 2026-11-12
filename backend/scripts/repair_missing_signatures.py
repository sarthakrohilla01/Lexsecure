#!/usr/bin/env python
"""Detect document versions with no RSA-PSS signature and sign them with the"""

import argparse
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.audit.logger import record_audit_event
from app.database.session import SessionLocal
from app.models.document import DocumentVersion
from app.models.signature import DigitalSignature
from app.models.user import User
from app.security.pki import load_private_key_pem, sign_data_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report only, change nothing.")
    args = parser.parse_args()

    db = SessionLocal()
    repaired = 0
    skipped = 0
    try:
        signed_ids = {row.version_id for row in db.query(DigitalSignature.version_id).all()}
        for version in db.query(DocumentVersion).order_by(DocumentVersion.id).all():
            if version.id in signed_ids:
                continue

            uploader = db.query(User).filter(User.id == version.uploaded_by_id).first()
            document = version.document
            label = f"{document.title if document else 'document'} v{version.version_number}"

            if not uploader or not uploader.private_key_pem:
                print(f"[!] {label}: uploader has no PKI key — skipped")
                skipped += 1
                continue

            print(f"[+] {label}: signing with {uploader.email}")
            if args.dry_run:
                repaired += 1
                continue

            private_pem = load_private_key_pem(uploader.private_key_pem)
            signature_hex = sign_data_hash(private_pem, version.sha256_hash)
            db.add(
                DigitalSignature(
                    version_id=version.id,
                    signer_id=uploader.id,
                    signer_name=uploader.full_name,
                    signer_role=uploader.role.value,
                    signature_hex=signature_hex,
                    algorithm="SHA256withRSA-2048",
                    is_valid=True,
                    certificate_serial=f"NCRB-CERT-{uuid.uuid4().hex[:8].upper()}",
                )
            )
            db.commit()
            record_audit_event(
                db=db,
                action="SIGNATURE_BACKFILLED",
                target_type="DOCUMENT_VERSION",
                target_id=str(version.id),
                details=f"Missing digital signature created for {label} by {uploader.email}",
                user=uploader,
                status="SUCCESS",
            )
            repaired += 1
    finally:
        db.close()

    print(f"\nSigned: {repaired} · skipped: {skipped}")
    return 0 if skipped == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
