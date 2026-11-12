"""AES-256-GCM Encryption & Decryption Engine"""

import os
from typing import Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import settings

def get_encryption_key() -> bytes:
    """Derives 32-byte AES key from settings. In production, this must interface with a Hardware Security Module (HSM) or KMS."""
    key_hex = settings.DOCUMENT_ENCRYPTION_KEY
    try:
        raw_key = bytes.fromhex(key_hex)
        if len(raw_key) == 32:
            return raw_key
    except Exception:
        pass
    import hashlib
    import logging
    logging.getLogger("lexsecure.crypto").warning(
        "DOCUMENT_ENCRYPTION_KEY is not a valid 32-byte hex value; "
        "falling back to SHA-256(password) derivation. Provide a KMS-sourced key."
    )
    return hashlib.sha256(key_hex.encode()).digest()

def encrypt_document_bytes(plaintext: bytes) -> Tuple[bytes, str, str]:
    """Encrypts plaintext bytes using AES-256-GCM. Returns: (ciphertext_with_tag, iv_hex, tag_hex)"""
    key = get_encryption_key()
    aesgcm = AESGCM(key)
    iv = os.urandom(12)
    encrypted_payload = aesgcm.encrypt(iv, plaintext, None)
    
    ciphertext = encrypted_payload[:-16]
    tag = encrypted_payload[-16:]
    
    return encrypted_payload, iv.hex(), tag.hex()

def decrypt_document_bytes(encrypted_payload: bytes, iv_hex: str) -> bytes:
    """Decrypts AES-256-GCM encrypted payload using the provided IV. Raises InvalidTag if tampered or corrupt."""
    key = get_encryption_key()
    aesgcm = AESGCM(key)
    iv = bytes.fromhex(iv_hex)
    return aesgcm.decrypt(iv, encrypted_payload, None)


SECRET_BOX_PREFIX = "lsenc:v1:"

def encrypt_secret(plaintext: str) -> str:
    """Encrypts a sensitive string (e.g. an RSA private key PEM) with the master AES-256-GCM key for at-rest storage in the database. Returns a versioned, self-describing token: lsenc:v1:<iv_hex>:<payload_hex>"""
    key = get_encryption_key()
    aesgcm = AESGCM(key)
    iv = os.urandom(12)
    payload = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    return f"{SECRET_BOX_PREFIX}{iv.hex()}:{payload.hex()}"

def decrypt_secret(stored: str) -> str:
    """Reverses encrypt_secret(). Values without the lsenc:v1: prefix are treated as legacy plaintext (records created before at-rest encryption existed) and returned unchanged."""
    if not stored or not stored.startswith(SECRET_BOX_PREFIX):
        return stored
    body = stored[len(SECRET_BOX_PREFIX):]
    iv_hex, payload_hex = body.split(":", 1)
    key = get_encryption_key()
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(bytes.fromhex(iv_hex), bytes.fromhex(payload_hex), None)
    return plaintext.decode("utf-8")
