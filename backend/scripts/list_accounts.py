"""Print every account with its login state and a live TOTP code when applicable."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyotp

from app.database.session import SessionLocal
from app.models.case import CaseAssignment
from app.models.user import User

DEMO_PASSWORD = "Demo@LexSecure2026"
SEED_PASSWORD = "LexSecure@2026"


def main() -> int:
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.id).all()
        print(f"{'EMAIL':<34}{'ROLE':<16}{'STATE':<14}{'PASSWORD':<20}{'TOTP'}")
        print("-" * 100)
        for u in users:
            assignments = db.query(CaseAssignment).filter(
                CaseAssignment.user_id == u.id).all()
            cases = ", ".join(sorted(a.case_id for a in assignments)) or "all (by role)"

            if u.email.startswith("demo.") or u.email == "demo@lexsecure.local":
                password = DEMO_PASSWORD
            elif u.email in ("investigator@lexsecure.local", "forensic@lexsecure.local",
                             "legal@lexsecure.local", "supervisor@lexsecure.local",
                             "admin@lexsecure.local"):
                password = SEED_PASSWORD
            else:
                password = "—"

            if not u.is_active:
                state = "deactivated"
            elif u.mfa_enabled and not u.mfa_activated_at:
                state = "enrolling"
            elif u.mfa_enabled:
                state = "MFA active"
            else:
                state = "password only"

            code = ""
            if u.mfa_enabled and u.mfa_secret:
                code = pyotp.TOTP(u.mfa_secret).now()

            print(f"{u.email:<34}{u.role.value:<16}{state:<14}{password:<20}{code or '-'}")
            print(f"{'':<34}cases: {cases}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
