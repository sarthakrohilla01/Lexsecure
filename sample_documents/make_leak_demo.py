"""Leak Investigator Demo Builder"""

import base64
import hashlib
import hmac
import os
import struct
import sys
import time

import httpx

BASE = os.environ.get("LEXSECURE_URL", "http://localhost:8000/api")
DEMO_DIR = os.path.expanduser("~/Desktop/leak_demo")
SAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "Leak_Demo_Witness_Statement.txt")

INVESTIGATOR = ("investigator@lexsecure.local", "LexSecure@2026",
                os.environ.get("LEXSECURE_INVESTIGATOR_TOTP", ""))
SUPERVISOR = ("supervisor@lexsecure.local", "LexSecure@2026",
              os.environ.get("LEXSECURE_SUPERVISOR_TOTP", ""))


def totp(secret: str) -> str:
    """RFC 6238 TOTP (SHA-1, 6 digits, 30s) using only the standard library."""
    if not secret:
        return ""
    padded = secret.strip().upper() + "=" * (-len(secret.strip()) % 8)
    key = base64.b32decode(padded)
    counter = int(time.time()) // 30
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


def login(client: httpx.Client, creds) -> dict:
    email, password, secret = creds
    if not secret:
        print(f"[✗] No TOTP secret for {email}. Set LEXSECURE_*_TOTP "
              f"(see backend/scripts/provision_mfa.py).")
        raise SystemExit(1)
    r = client.post("/auth/login", json={
        "username": email, "password": password, "mfa_code": totp(secret)})
    if r.status_code != 200:
        print(f"[✗] Login failed for {email}: HTTP {r.status_code} — {r.text[:200]}")
        raise SystemExit(1)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def must(resp: httpx.Response, step: str) -> httpx.Response:
    if resp.is_error:
        try:
            detail = resp.json().get("detail", resp.text[:200])
        except Exception:
            detail = resp.text[:200]
        print(f"[✗] {step} failed: HTTP {resp.status_code} — {detail}")
        raise SystemExit(1)
    return resp


def main() -> int:
    if not os.path.exists(SAMPLE):
        print(f"[✗] Sample file not found: {SAMPLE}")
        return 1

    root = BASE[:-len("/api")] if BASE.endswith("/api") else BASE
    with httpx.Client(base_url=BASE, timeout=60.0) as client:
        try:
            health = httpx.get(f"{root}/health", timeout=5)
            health.raise_for_status()
        except Exception as exc:
            print(f"[✗] Backend not reachable at {BASE} ({exc}). Start it with ./start.sh first.")
            return 1

        inv_headers = login(client, INVESTIGATOR)
        with open(SAMPLE, "rb") as f:
            up = client.post("/documents/upload", headers=inv_headers, files={
                "file": ("Leak_Demo_Witness_Statement.txt", f, "text/plain"),
            }, data={
                "case_id": "CASE-2026-001",
                "title": "Witness Statement (Leak Demo)",
                "classification": "RESTRICTED",
                "document_type": "WITNESS_STATEMENT",
                "change_reason": "Leak tracker demonstration",
            })
        must(up, "Upload")
        doc = up.json()
        doc_id = doc["document_id"]
        print(f"[1/6] Uploaded as document #{doc_id} "
              f"(v{doc['version_number']}, ledger block #{doc['ledger_block_number']})")

        dl = client.get(f"/documents/{doc_id}/download", headers=inv_headers)
        must(dl, "Download")
        watermarked = dl.content
        with open(SAMPLE, "rb") as handle:
            original = handle.read()
        if watermarked == original:
            print("[✗] Download was NOT watermarked — is this a .txt file?")
            return 1
        print(f"[2/6] Downloaded {len(watermarked)} bytes — "
              f"zero-width watermark injected ({len(watermarked) - os.path.getsize(SAMPLE)} invisible chars)")

        forwarded = (
            "---------- Forwarded message ----------\n"
            "From: investigator@lexsecure.local\n"
            "Subject: FW: Witness statement (internal use only)\n"
            "Sharing this with my personal email for safekeeping.\n\n"
            + watermarked.decode("utf-8")
            + "\n\n-- \nSent from my personal device\n"
        ).encode("utf-8")

        os.makedirs(DEMO_DIR, exist_ok=True)
        original_path = os.path.join(DEMO_DIR, "01_original_clean_copy.txt")
        leaked_path = os.path.join(DEMO_DIR, "02_LEAKED_forwarded_copy.txt")
        with open(original_path, "wb") as f:
            f.write(watermarked)
        with open(leaked_path, "wb") as f:
            f.write(forwarded)
        print(f"[3/6] Saved clean download  -> {original_path}")
        print(f"[4/6] Saved leaked copy     -> {leaked_path}")

        sup_headers = login(client, SUPERVISOR)
        trace = client.post("/integrity/extract-watermark", headers=sup_headers,
                            files={"file": ("02_LEAKED_forwarded_copy.txt",
                                            forwarded, "text/plain")})
        must(trace, "Watermark extraction")
        result = trace.json()
        print("[5/6] Supervisor leak-investigation result:")
        if result.get("is_valid"):
            print(f"      ✔ TRACED TO : {result['email']} (user id {result['user_id']})")
            print(f"      ✔ DOCUMENT  : #{result['document_id']} v{result['version']}")
            print(f"      ✔ DOWNLOADED: {result['timestamp']}")
        else:
            print(f"      ✗ {result.get('error')}")
            return 1

        clean = client.post("/integrity/extract-watermark", headers=sup_headers,
                            files={"file": ("clean.txt", b"Just a clean file.", "text/plain")})
        print(f"[6/6] Control file (no watermark): is_valid={clean.json().get('is_valid')} "
              f"— '{clean.json().get('error')}'")

    print("""
==========================================================
 READY — run the demo in the browser:
 1. Login as Investigator, open ~/Desktop/leak_demo/01_original_clean_copy.txt
    (it looks identical to the original — the watermark is invisible)
 2. Use 02_LEAKED_forwarded_copy.txt as the "leaked" file
 3. Login as Supervisor  ->  Leak Investigator  ->  upload
    02_LEAKED_forwarded_copy.txt
 4. The trace reveals: investigator@lexsecure.local, doc #DOC, timestamp
==========================================================""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
