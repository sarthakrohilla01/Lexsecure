#!/usr/bin/env python
"""Create an expiring test account."""

import argparse
import base64
import io
import os
import secrets
import sys
import time
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import qrcode
import pyotp

from app.audit.logger import record_audit_event
from app.database.session import SessionLocal
from app.models.case import Case, CaseAssignment
from app.models.user import Department, User, UserRole
from app.security.crypto import encrypt_secret
from app.security.jwt import hash_password
from app.security.mfa import (
    generate_backup_codes,
    generate_secret,
    provisioning_uri,
    serialize_backup_hashes,
)
from app.security.pki import generate_key_pair
from app.utils.time import utcnow

DEPARTMENTS = {
    UserRole.INVESTIGATOR: Department.CYBER_CRIME.value,
    UserRole.FORENSIC_EXPERT: Department.FORENSIC_LAB.value,
    UserRole.LEGAL_OFFICER: Department.PROSECUTION.value,
    UserRole.SUPERVISOR: Department.SPECIAL_INVESTIGATION.value,
    UserRole.ADMINISTRATOR: Department.ADMINISTRATION.value,
}


def _qr_data_url(uri: str) -> str:
    image = qrcode.make(uri)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def purge_expired(db) -> int:
    now = utcnow()
    expired = (
        db.query(User)
        .filter(User.is_temporary.is_(True), User.expires_at.is_not(None), User.expires_at < now)
        .all()
    )
    for user in expired:
        user.is_active = False
    db.commit()
    return len(expired)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an expiring test account.")
    parser.add_argument("--role", default="SUPERVISOR", choices=[r.name for r in UserRole])
    parser.add_argument("--hours", type=float, default=24)
    parser.add_argument("--email", help="Defaults to temp.<role>.<random>@lexsecure.local")
    parser.add_argument("--password", help="Defaults to a generated strong password")
    parser.add_argument("--name", help="Display name")
    parser.add_argument("--purge-expired", action="store_true", help="Deactivate expired temp accounts and exit.")
    parser.add_argument(
        "--no-mfa",
        action="store_true",
        help="Create a password-only account (no TOTP). Temporary accounts only.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.purge_expired:
            count = purge_expired(db)
            print(f"Deactivated {count} expired temporary account(s).")
            return 0

        role = UserRole[args.role]
        email = (args.email or f"temp.{role.name.lower()}.{secrets.token_hex(3)}@lexsecure.local").lower()
        password = args.password or f"Tmp-{secrets.token_urlsafe(9)}"
        expires_at = utcnow() + timedelta(hours=args.hours)

        if db.query(User).filter(User.email == email).first():
            print(f"ERROR: {email} already exists.")
            return 1

        private_pem, public_pem = generate_key_pair()
        if args.no_mfa:
            secret = None
            backup_plain: list[str] = []
            backup_hashes: list[str] = []
        else:
            secret = generate_secret()
            backup_plain, backup_hashes = generate_backup_codes()

        user = User(
            email=email,
            full_name=args.name or f"Temporary {role.name.replace('_', ' ').title()}",
            role=role,
            department=DEPARTMENTS[role],
            hashed_password=hash_password(password),
            badge_number=f"TMP-{secrets.token_hex(3).upper()}",
            mfa_enabled=not args.no_mfa,
            mfa_secret=secret,
            mfa_activated_at=None if args.no_mfa else utcnow(),
            mfa_last_step=None,
            mfa_backup_codes=None if args.no_mfa else serialize_backup_hashes(backup_hashes),
            public_key_pem=public_pem,
            private_key_pem=encrypt_secret(private_pem),
            is_active=True,
            is_temporary=True,
            expires_at=expires_at,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assigned = []
        if role not in (UserRole.SUPERVISOR, UserRole.ADMINISTRATOR):
            for case in db.query(Case).all():
                db.add(
                    CaseAssignment(
                        case_id=case.id,
                        user_id=user.id,
                        assignment_role="TEST_ACCOUNT",
                        can_upload=True,
                        can_approve=False,
                    )
                )
                assigned.append(case.id)
            db.commit()

        record_audit_event(
            db=db,
            action="TEMPORARY_ACCOUNT_CREATED",
            target_type="USER",
            target_id=str(user.id),
            details=(
                f"Temporary {role.name} account {email} created; expires "
                f"{expires_at.isoformat()}Z"
            ),
            user=user,
            status="SUCCESS",
        )

        uri = provisioning_uri(secret, email) if secret else None
        html_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp_account.html")
        with open(html_path, "w", encoding="utf-8") as handle:
            handle.write(
                "<!doctype html><meta charset='utf-8'>"
                "<title>LexSecure temporary account</title>"
                "<body style=\"font-family:-apple-system,Segoe UI,sans-serif;background:#f8fafc;padding:2rem\">"
                "<h1 style='font-size:1.3rem'>LexSecure — temporary test account</h1>"
                "<p style='background:#fef3c7;border:1px solid #f59e0b;padding:.75rem 1rem;border-radius:.5rem'>"
                "<strong>Sensitive.</strong> Scan, use, then delete this file.</p>"
                f"<p><strong>{email}</strong><br>Expires {expires_at.isoformat()}Z</p>"
                + (
                    f"<img src='{_qr_data_url(uri)}' width='220' height='220' alt='QR code'>"
                    f"<p>Secret: <code>{secret}</code></p>"
                    if uri
                    else "<p>MFA disabled for this account — email + password only.</p>"
                )
                + "</body>"
            )
        try:
            os.chmod(html_path, 0o600)
        except OSError:
            pass

        print("=" * 64)
        print(
            "TEMPORARY TEST ACCOUNT (password only, MFA disabled)"
            if args.no_mfa
            else "TEMPORARY TEST ACCOUNT (real TOTP MFA)"
        )
        print("=" * 64)
        print(f"  Email       : {email}")
        print(f"  Password    : {password}")
        print(f"  Role        : {role.name}")
        print(f"  Expires     : {expires_at.isoformat()}Z  ({args.hours:g}h)")
        if args.no_mfa:
            print("  MFA         : disabled — login needs only email + password")
        else:
            code = pyotp.TOTP(secret).now()
            print(f"  MFA secret  : {secret}")
            print(f"  Current code: {code}  (valid ~{30 - int(time.time()) % 30}s)")
            print(f"  Backup codes: {', '.join(backup_plain)}")
        if assigned:
            print(f"  Cases       : {', '.join(assigned)}")
        print(f"  Sheet       : {html_path}")
        print("=" * 64)
        if not args.no_mfa:
            print("Get a fresh code anytime:")
            print(f"  backend/venv/bin/python backend/scripts/totp_code.py --email {email}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
