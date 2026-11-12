"""MFA Utilities — TOTP (RFC 6238) and single-use backup codes."""

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import pyotp

from app.config import settings

BACKUP_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_secret() -> str:
    """A fresh 160-bit base32 TOTP seed."""
    return pyotp.random_base32(length=32)


def is_valid_secret(secret: Optional[str]) -> bool:
    """False for legacy placeholders such as '123456' or 'LEXSECURE2026MFA'."""
    if not secret:
        return False
    cleaned = secret.strip().upper()
    if len(cleaned) < 16:
        return False
    padded = cleaned + "=" * (-len(cleaned) % 8)
    try:
        raw = base64.b32decode(padded, casefold=True)
    except Exception:
        return False
    return len(raw) >= 10


def provisioning_uri(secret: str, email: str, issuer: Optional[str] = None) -> str:
    return pyotp.TOTP(secret).provisioning_uri(
        name=email,
        issuer_name=issuer or settings.MFA_ISSUER,
    )


def _normalize_code(code: Optional[str]) -> str:
    return "".join(ch for ch in (code or "") if ch.isdigit())


def verify_totp(secret: str, code: Optional[str], window: Optional[int] = None) -> Optional[int]:
    """Verifies a 6-digit TOTP code. Returns the matched time step (for replay protection) or None. A code that was already used for a previous login is rejected even inside the window."""
    normalized = _normalize_code(code)
    if not secret or len(normalized) != 6:
        return None

    totp = pyotp.TOTP(secret)
    drift = settings.MFA_TOTP_WINDOW if window is None else window
    now = int(datetime.now(timezone.utc).timestamp())
    current_step = now // totp.interval

    for offset in range(-drift, drift + 1):
        step = current_step + offset
        for_time = step * totp.interval
        if hmac.compare_digest(totp.at(for_time), normalized):
            return step
    return None


def _hash_backup_code(code: str) -> str:
    normalized = code.replace("-", "").replace(" ", "").upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_backup_codes(count: Optional[int] = None) -> Tuple[List[str], List[str]]:
    """Returns (plaintext codes shown once, hashes stored in the database)."""
    total = count or settings.MFA_BACKUP_CODE_COUNT
    plain: List[str] = []
    for _ in range(total):
        raw = "".join(secrets.choice(BACKUP_CODE_ALPHABET) for _ in range(8))
        plain.append(f"{raw[:4]}-{raw[4:]}")
    return plain, [_hash_backup_code(c) for c in plain]


def serialize_backup_hashes(hashes: List[str]) -> str:
    return json.dumps(hashes)


def load_backup_hashes(stored: Optional[str]) -> List[str]:
    if not stored:
        return []
    try:
        value = json.loads(stored)
        return value if isinstance(value, list) else []
    except Exception:
        return []


def consume_backup_code(stored: Optional[str], code: Optional[str]) -> Tuple[bool, str]:
    """One-time use: on success returns the remaining hashes so the caller can persist them, which makes every code truly single-use."""
    hashes = load_backup_hashes(stored)
    if not code or not hashes:
        return False, stored or ""
    target = _hash_backup_code(code)
    for idx, candidate in enumerate(hashes):
        if hmac.compare_digest(candidate, target):
            remaining = hashes[:idx] + hashes[idx + 1:]
            return True, serialize_backup_hashes(remaining)
    return False, stored or ""
