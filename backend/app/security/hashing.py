"""Cryptographic Hashing Utilities"""

import hashlib
import hmac

def calculate_sha256(data: bytes) -> str:
    """Computes SHA-256 hexadecimal digest for raw bytes."""
    hasher = hashlib.sha256()
    hasher.update(data)
    return hasher.hexdigest()

def verify_sha256(data: bytes, expected_hash: str) -> bool:
    """Performs constant-time comparison of calculated hash against expected hash."""
    current_hash = calculate_sha256(data)
    return hmac.compare_digest(current_hash.lower(), expected_hash.lower())
