#!/usr/bin/env python
"""Provision TOTP authenticators for local accounts."""

import argparse
import base64
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyotp
import qrcode

from app.database.session import SessionLocal
from app.models.user import User
from app.security.mfa import generate_secret, is_valid_secret, provisioning_uri
from app.utils.time import utcnow


def _qr_data_url(uri: str) -> str:
    image = qrcode.make(uri)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision TOTP authenticators.")
    parser.add_argument("--rotate", action="store_true", help="Replace existing secrets (invalidates old devices).")
    parser.add_argument("--user", help="Only provision this email address.")
    parser.add_argument(
        "--output",
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mfa_enrollment.html"),
        help="Where to write the QR sheet.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    rows = []
    try:
        query = db.query(User).filter(
            User.is_active.is_(True),
            User.email.notlike("demo.%"),
        )
        if args.user:
            query = query.filter(User.email == args.user.lower())
        users = query.order_by(User.id).all()

        if not users:
            print("No matching active users.")
            return 1

        for user in users:
            if args.rotate or not is_valid_secret(user.mfa_secret):
                user.mfa_secret = generate_secret()
                user.mfa_activated_at = None
                user.mfa_last_step = None
                user.mfa_backup_codes = None
                print(f"[+] New TOTP secret for {user.email}")
            else:
                print(f"[=] Keeping existing secret for {user.email}")

            uri = provisioning_uri(user.mfa_secret, user.email)
            rows.append({
                "email": user.email,
                "name": user.full_name,
                "role": user.role.value,
                "secret": user.mfa_secret,
                "uri": uri,
                "qr": _qr_data_url(uri),
                "code": pyotp.TOTP(user.mfa_secret).now(),
            })

        db.commit()
    finally:
        db.close()

    html_rows = "\n".join(
        f"""
        <section>
          <h2>{r['name']} <small>{r['role']}</small></h2>
          <p class="email">{r['email']}</p>
          <img src="{r['qr']}" alt="QR code for {r['email']}" width="220" height="220" />
          <p>Secret: <code>{r['secret']}</code></p>
          <p class="muted">Scan with Google Authenticator / 1Password / Authy.
          Current code at generation time: <strong>{r['code']}</strong></p>
        </section>
        """
        for r in rows
    )

    html = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>LexSecure — MFA enrolment</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, sans-serif; background:#f8fafc; color:#0f172a; margin:2rem; }}
  h1 {{ font-size:1.4rem; }}
  .warn {{ background:#fef3c7; border:1px solid #f59e0b; padding:.75rem 1rem; border-radius:.5rem; }}
  grid {{ display:grid; gap:1.5rem; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); }}
  section {{ background:#fff; border:1px solid #e2e8f0; border-radius:.75rem; padding:1.25rem; }}
  h2 {{ font-size:1rem; margin:0 0 .25rem; }}
  h2 small {{ color:#64748b; font-weight:500; }}
  .email {{ color:#475569; margin:0 0 .75rem; font-family:ui-monospace,monospace; font-size:.85rem; }}
  code {{ background:#f1f5f9; padding:.15rem .35rem; border-radius:.25rem; }}
  .muted {{ color:#64748b; font-size:.8rem; }}
</style>
<h1>LexSecure — authenticator enrolment</h1>
<p class="warn"><strong>Sensitive file.</strong> These QR codes and secrets grant sign-in access.
Scan them, then delete this file. Generated {utcnow().isoformat()}Z.</p>
<grid>{html_rows}</grid>
</html>
"""
    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(html)
    os.chmod(args.output, 0o600)

    print("\nAccount                          Secret                            Current code")
    print("-" * 86)
    for r in rows:
        print(f"{r['email']:<32} {r['secret']:<33} {r['code']}")
    print(f"\nQR sheet: {args.output}")
    print("Scan a QR code with an authenticator app, then sign in with the 6-digit code.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
