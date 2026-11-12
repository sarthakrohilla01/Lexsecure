"""Create or refresh the demo account roster."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.session import SessionLocal
from app.models.case import Case, CaseAssignment
from app.models.user import Department, User, UserRole
from app.security.crypto import encrypt_secret
from app.security.jwt import hash_password
from app.security.pki import generate_key_pair

PASSWORD = "Demo@LexSecure2026"

ROSTER = [
    ("demo@lexsecure.local", "Demo Administrator", UserRole.ADMINISTRATOR,
     Department.ADMINISTRATION, "DEMO-ADM-0001", []),
    ("demo.admin@lexsecure.local", "Demo Administrator", UserRole.ADMINISTRATOR,
     Department.ADMINISTRATION, "DEMO-ADM-0001", []),
    ("demo.supervisor@lexsecure.local", "Demo Supervisor", UserRole.SUPERVISOR,
     Department.SPECIAL_INVESTIGATION, "DEMO-SUP-0002", []),
    ("demo.investigator@lexsecure.local", "Demo Investigator", UserRole.INVESTIGATOR,
     Department.CYBER_CRIME, "DEMO-INV-0003", ["CASE-2026-001"]),
    ("demo.forensic@lexsecure.local", "Demo Forensic Expert", UserRole.FORENSIC_EXPERT,
     Department.FORENSIC_LAB, "DEMO-FOR-0004", ["CASE-2026-001", "CASE-2026-002"]),
    ("demo.legal@lexsecure.local", "Demo Legal Officer", UserRole.LEGAL_OFFICER,
     Department.PROSECUTION, "DEMO-LEG-0005", ["CASE-2026-002", "CASE-2026-003"]),
]


def main() -> int:
    db = SessionLocal()
    try:
        for email, name, role, dept, badge, cases in ROSTER:
            user = db.query(User).filter(User.email == email).first()
            if user is None:
                private_pem, public_pem = generate_key_pair()
                user = User(
                    email=email,
                    full_name=name,
                    role=role,
                    department=dept.value,
                    hashed_password=hash_password(PASSWORD),
                    badge_number=badge,
                    mfa_enabled=False,
                    public_key_pem=public_pem,
                    private_key_pem=encrypt_secret(private_pem),
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                print(f"created  {email}")
            else:
                print(f"updated  {email}")

            user.hashed_password = hash_password(PASSWORD)
            user.is_active = True
            user.is_temporary = False
            user.expires_at = None
            user.mfa_enabled = False
            user.mfa_secret = None
            user.mfa_activated_at = None
            user.mfa_backup_codes = None
            db.commit()
            db.refresh(user)

            wanted = set(cases)
            current = {
                a.case_id for a in db.query(CaseAssignment)
                .filter(CaseAssignment.user_id == user.id).all()
            }
            for case_id in wanted - current:
                db.add(CaseAssignment(
                    case_id=case_id,
                    user_id=user.id,
                    assignment_role="LEAD_INVESTIGATOR",
                    can_upload=True,
                    can_approve=role in (UserRole.SUPERVISOR, UserRole.ADMINISTRATOR),
                ))
            for case_id in current - wanted:
                row = db.query(CaseAssignment).filter(
                    CaseAssignment.user_id == user.id,
                    CaseAssignment.case_id == case_id,
                ).first()
                if row:
                    db.delete(row)
            db.commit()

        print("\ndemo roster ready")
        print(f"password for every demo account: {PASSWORD}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
