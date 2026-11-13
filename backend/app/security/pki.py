"""PKI & Digital Signature Engine"""

from typing import Tuple
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from app.security.crypto import decrypt_secret

def load_private_key_pem(stored_pem: str) -> str:
    """Returns a usable PEM from a stored private key field. Keys are encrypted at rest (lsenc:v1: prefix); legacy plaintext records are passed through unchanged by decrypt_secret()."""
    return decrypt_secret(stored_pem)

def generate_key_pair() -> Tuple[str, str]:
    """Generates an RSA 2048-bit key pair. Returns: (private_key_pem_str, public_key_pem_str)"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode("utf-8")

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")

    return private_pem, public_pem

def sign_data_hash(private_key_pem: str, data_hash: str) -> str:
    """Digitally signs a document's SHA-256 hash using the user's private key. Returns signature in hex format."""
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"),
        password=None
    )

    signature = private_key.sign(
        data_hash.encode("utf-8"),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return signature.hex()

def verify_data_signature(public_key_pem: str, data_hash: str, signature_hex: str) -> bool:
    """Verifies a digital signature against the document's SHA-256 hash using the public key."""
    try:
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode("utf-8")
        )
        signature = bytes.fromhex(signature_hex)
        public_key.verify(
            signature,
            data_hash.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False
