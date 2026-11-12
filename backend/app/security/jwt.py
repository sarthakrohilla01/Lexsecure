"""JWT Authentication & Password Security"""

import uuid
from datetime import timedelta
from typing import Optional, Dict, Any

import bcrypt
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.revoked_token import RevokedToken
from app.utils.time import utcnow


def hash_password(password: str) -> str:
    """Hashes password using bcrypt with salt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the stored bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Encodes JWT token with claims and expiration."""
    to_encode = data.copy()
    expire = utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))

    to_encode.update({
        "exp": expire,
        "iat": utcnow(),
        "jti": uuid.uuid4().hex,
    })
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates JWT token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def revoke_token(db: Session, payload: Dict[str, Any]) -> bool:
    """Blacklists a token id until its natural expiry."""
    jti = payload.get("jti")
    if not jti:
        return False

    expires_at = payload.get("exp")
    if isinstance(expires_at, (int, float)):
        expires_at = utcnow() + timedelta(seconds=max(0, int(expires_at - utcnow().timestamp())))

    already = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
    if already:
        return False

    db.add(RevokedToken(
        jti=jti,
        user_id=int(payload.get("sub", 0)) or None,
        expires_at=expires_at,
        revoked_at=utcnow(),
    ))
    db.commit()
    return True


def is_token_revoked(db: Session, payload: Dict[str, Any]) -> bool:
    """True when the token was signed off by an explicit logout."""
    jti = payload.get("jti")
    if not jti:
        return False
    return db.query(RevokedToken).filter(RevokedToken.jti == jti).first() is not None
