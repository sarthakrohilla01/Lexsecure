#!/usr/bin/env python
"""Print the current TOTP code for an account (test/operations helper)."""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyotp

from app.database.session import SessionLocal
from app.models.user import User


def main() -> int:
    parser = argparse.ArgumentParser(description="Print an account's current TOTP code.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--secret", action="store_true", help="Also print the base32 secret.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == args.email.lower()).first()
        if not user or not user.mfa_secret:
            print(f"No TOTP secret for {args.email}")
            return 1

        totp = pyotp.TOTP(user.mfa_secret)
        remaining = 30 - (int(time.time()) % 30)
        print(f"Account : {user.email}")
        if args.secret:
            print(f"Secret  : {user.mfa_secret}")
        print(f"Code    : {totp.now()}  (valid ~{remaining}s)")
        if user.expires_at:
            print(f"Expires : {user.expires_at.isoformat()}Z")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
