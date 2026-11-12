"""Authentication & MFA Endpoints"""

import base64
import io
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

import qrcode

from app.config import settings
from app.database.session import get_db
from app.models.login_attempt import LoginAttempt
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MfaCodeRequest,
    MfaDisableRequest,
    UserResponse,
)
from app.security.abac import get_current_user
from app.security.jwt import (
    create_access_token,
    decode_access_token,
    is_token_revoked,
    revoke_token,
    verify_password,
)
from app.security.mfa import (
    consume_backup_code,
    generate_backup_codes,
    generate_secret,
    is_valid_secret,
    load_backup_hashes,
    provisioning_uri,
    serialize_backup_hashes,
    verify_totp,
)
from app.audit.logger import record_audit_event
from app.utils.time import utcnow

router = APIRouter(prefix="/auth", tags=["Authentication"])

MAX_FAILURES = 10
LOCKOUT_SECONDS = 300


def _rate_key(request: Request, username: str) -> str:
    ip = request.client.host if request and request.client else "unknown"
    return f"{ip}|{username.lower().strip()}"


def _check_rate_limit(db: Session, request: Request, username: str) -> None:
    row = db.query(LoginAttempt).filter(LoginAttempt.key == _rate_key(request, username)).first()
    if not row:
        return
    now = utcnow()
    if row.locked_until and row.locked_until > now:
        remaining = int((row.locked_until - now).total_seconds() // 60) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Try again in {remaining} minute(s).",
        )
    if row.locked_until and row.locked_until <= now:
        db.delete(row)
        db.commit()


def _record_failure(db: Session, request: Request, username: str) -> None:
    key = _rate_key(request, username)
    row = db.query(LoginAttempt).filter(LoginAttempt.key == key).first()
    now = utcnow()
    if not row:
        row = LoginAttempt(key=key, failures=0, first_failure_at=now)
        db.add(row)
    if row.first_failure_at and (now - row.first_failure_at).total_seconds() > LOCKOUT_SECONDS:
        row.failures = 0
        row.first_failure_at = now

    row.failures = (row.failures or 0) + 1
    if row.failures >= MAX_FAILURES:
        row.locked_until = now + timedelta(seconds=LOCKOUT_SECONDS)
    db.commit()


def _clear_failures(db: Session, request: Request, username: str) -> None:
    db.query(LoginAttempt).filter(LoginAttempt.key == _rate_key(request, username)).delete()
    db.commit()


def _public_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "department": user.department,
        "badge_number": user.badge_number,
        "mfa_enabled": user.mfa_enabled,
        "mfa_enrolled": bool(user.mfa_activated_at),
    }


def _user_from_bearer(authorization: Optional[str], db: Session) -> User:
    """Accepts a normal access token or a short-lived MFA enrolment token."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
    payload = decode_access_token(authorization.split(" ", 1)[1].strip())
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")

    if is_token_revoked(db, payload):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This session has been signed out.")

    if payload.get("scope") == "mfa_enroll":
        user = db.query(User).filter(User.email == payload.get("email")).first()
    else:
        user = db.query(User).filter(User.id == int(payload.get("sub", 0))).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found or disabled.")
    return user


def _qr_data_url(uri: str) -> str:
    image = qrcode.make(uri)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _require_enrolled(user: User) -> None:
    if not user.mfa_enabled:
        return
    if not is_valid_secret(user.mfa_secret) or not user.mfa_activated_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticator enrolment is required before this action.",
        )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    _check_rate_limit(db, request, payload.username)

    user = db.query(User).filter(User.email == payload.username.lower()).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        _record_failure(db, request, payload.username)
        record_audit_event(
            db=db,
            action="LOGIN_FAILED",
            user_email=payload.username,
            details="Invalid username or password attempt",
            status="FAILURE",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is deactivated.",
        )

    if user.expires_at and user.expires_at < utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This temporary account has expired.",
        )

    if user.mfa_enabled and (not is_valid_secret(user.mfa_secret) or not user.mfa_activated_at):
        _clear_failures(db, request, payload.username)
        record_audit_event(
            db=db,
            action="MFA_ENROLLMENT_REQUIRED",
            user=user,
            details=f"Password accepted for {user.email}; authenticator enrolment pending.",
            status="PENDING",
        )
        return {
            "token_type": "bearer",
            "mfa_verified": False,
            "mfa_enrollment_required": True,
            "enrollment_token": create_access_token(
                {"sub": str(user.id), "email": user.email, "scope": "mfa_enroll"},
                expires_delta=timedelta(minutes=settings.MFA_ENROLLMENT_TOKEN_MINUTES),
            ),
            "user": _public_user(user),
        }

    mfa_valid = not user.mfa_enabled
    matched_step: Optional[int] = None

    if user.mfa_enabled:
        step = verify_totp(user.mfa_secret, payload.mfa_code)
        if step is not None and (user.mfa_last_step is None or step > user.mfa_last_step):
            mfa_valid = True
            matched_step = step
        else:
            ok, remaining = consume_backup_code(user.mfa_backup_codes, payload.mfa_code)
            if ok:
                mfa_valid = True
                user.mfa_backup_codes = remaining
                db.commit()

        if not mfa_valid:
            _record_failure(db, request, payload.username)
            submitted = (payload.mfa_code or "").strip()
            record_audit_event(
                db=db,
                action="MFA_FAILED",
                user=user,
                details=(
                    f"No authenticator code submitted by {user.email}"
                    if not submitted
                    else f"Invalid TOTP/backup code provided by {user.email}"
                ),
                status="BLOCKED",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "This account requires an authenticator code. Enter the 6-digit "
                    "code from your authenticator app."
                    if not submitted
                    else "Invalid or already-used verification code."
                ),
            )

    _clear_failures(db, request, payload.username)

    if matched_step is not None:
        user.mfa_last_step = matched_step
        db.commit()

    access_token = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "department": user.department,
            "mfa_verified": mfa_valid,
        }
    )

    record_audit_event(
        db=db,
        action="LOGIN_SUCCESS",
        user=user,
        details=(
            f"Authenticated with TOTP. Role: {user.role.value}"
            if user.mfa_enabled
            else f"Authenticated (MFA disabled by policy). Role: {user.role.value}"
        ),
        status="SUCCESS",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "mfa_verified": mfa_valid,
        "mfa_enrollment_required": False,
        "user": _public_user(user),
    }


@router.get("/mfa/status")
def mfa_status(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _user_from_bearer(authorization, db)
    return {
        "enabled": user.mfa_enabled,
        "enrolled": bool(user.mfa_activated_at),
        "activated_at": user.mfa_activated_at,
        "backup_codes_remaining": len(load_backup_hashes(user.mfa_backup_codes)),
    }


@router.post("/mfa/setup")
def mfa_setup(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Creates (or rotates) the TOTP seed for the authenticated account and returns a scannable QR code. The seed is not active until /mfa/activate proves the authenticator produces a valid code."""
    user = _user_from_bearer(authorization, db)
    if user.mfa_activated_at and user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticator already active. Disable it first to re-enrol.",
        )

    if not is_valid_secret(user.mfa_secret):
        user.mfa_secret = generate_secret()
        user.mfa_activated_at = None
        user.mfa_last_step = None
        db.commit()

    uri = provisioning_uri(user.mfa_secret, user.email)
    return {
        "secret": user.mfa_secret,
        "otpauth_uri": uri,
        "qr_data_url": _qr_data_url(uri),
        "issuer": settings.MFA_ISSUER,
        "account": user.email,
        "digits": 6,
        "period_seconds": 30,
    }


@router.post("/mfa/activate")
def mfa_activate(
    payload: MfaCodeRequest,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _user_from_bearer(authorization, db)
    if not is_valid_secret(user.mfa_secret):
        raise HTTPException(status_code=400, detail="Call /auth/mfa/setup first.")

    step = verify_totp(user.mfa_secret, payload.code)
    if step is None:
        raise HTTPException(status_code=400, detail="Code did not match. Check the device clock and retry.")

    plain_codes, hashes = generate_backup_codes()
    user.mfa_enabled = True
    user.mfa_activated_at = utcnow()
    user.mfa_last_step = step
    user.mfa_backup_codes = serialize_backup_hashes(hashes)
    db.commit()

    record_audit_event(
        db=db,
        action="MFA_ENROLLED",
        user=user,
        details=f"TOTP authenticator activated for {user.email}",
        status="SUCCESS",
    )
    access_token = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "department": user.department,
            "mfa_verified": True,
        }
    )
    return {
        "activated": True,
        "backup_codes": plain_codes,
        "message": "Store these backup codes offline. Each can be used once.",
        "access_token": access_token,
        "token_type": "bearer",
        "user": _public_user(user),
    }


@router.post("/mfa/disable")
def mfa_disable(
    payload: MfaDisableRequest,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _user_from_bearer(authorization, db)
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Password is incorrect.")

    step = verify_totp(user.mfa_secret, payload.code)
    if user.mfa_enabled and step is None:
        raise HTTPException(status_code=401, detail="A valid authenticator code is required.")

    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_activated_at = None
    user.mfa_last_step = None
    user.mfa_backup_codes = None
    db.commit()

    record_audit_event(
        db=db,
        action="MFA_DISABLED",
        user=user,
        details=f"TOTP disabled for {user.email}",
        status="WARNING",
    )
    return {"enabled": False}


@router.post("/mfa/backup-codes")
def mfa_backup_codes(
    payload: MfaCodeRequest,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _user_from_bearer(authorization, db)
    _require_enrolled(user)

    step = verify_totp(user.mfa_secret, payload.code)
    if step is None or (user.mfa_last_step is not None and step <= user.mfa_last_step):
        raise HTTPException(status_code=401, detail="A fresh, unused authenticator code is required.")

    plain_codes, hashes = generate_backup_codes()
    user.mfa_backup_codes = serialize_backup_hashes(hashes)
    user.mfa_last_step = step
    db.commit()

    record_audit_event(
        db=db,
        action="MFA_BACKUP_CODES_ROTATED",
        user=user,
        details=f"Backup codes regenerated for {user.email}",
        status="SUCCESS",
    )
    return {"backup_codes": plain_codes}


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Returns profile and public key information for the active user session."""
    return current_user


@router.post("/logout")
def logout(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Blacklists the presented access token so it cannot be replayed."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")

    payload = decode_access_token(authorization.split(" ", 1)[1].strip())
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")

    revoke_token(db, payload)
    return {"status": "SUCCESS", "message": "Session ended."}
