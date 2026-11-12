"""Security control tests: CORS lockdown, security headers, login rate limiting."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.models.user import User
from app.security.mfa import generate_secret
from app.utils.time import utcnow


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def mfa_account():
    from app.database.session import SessionLocal
    from app.security.jwt import hash_password

    email = "mfa_probe@lexsecure.local"
    secret = generate_secret()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(
                email=email,
                full_name="MFA Probe",
                role="INVESTIGATOR",
                department="Cyber Crime Division",
                hashed_password=hash_password("Probe@Pass2026"),
                mfa_enabled=True,
                mfa_secret=secret,
                mfa_activated_at=utcnow(),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        user.mfa_enabled = True
        user.mfa_secret = secret
        user.mfa_activated_at = utcnow()
        user.mfa_last_step = None
        db.commit()
        return email, secret
    finally:
        db.close()


def test_cors_has_no_wildcard():
    assert "*" not in settings.CORS_ORIGINS
    assert "http://localhost:5173" in settings.CORS_ORIGINS


def test_security_headers_present(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "no-referrer"


def test_missing_mfa_code_says_so_explicitly(client, mfa_account):
    email, _ = mfa_account
    res = client.post("/api/auth/login", json={
        "username": email,
        "password": "Probe@Pass2026",
        "mfa_code": None,
    })
    assert res.status_code == 401
    detail = res.json()["detail"]
    assert "requires an authenticator code" in detail
    assert "already-used" not in detail


def test_wrong_mfa_code_reports_invalid_code(client, mfa_account):
    email, _ = mfa_account
    res = client.post("/api/auth/login", json={
        "username": email,
        "password": "Probe@Pass2026",
        "mfa_code": "000000",
    })
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid or already-used verification code."


def test_valid_mfa_code_signs_in(client, mfa_account):
    import pyotp

    email, secret = mfa_account
    res = client.post("/api/auth/login", json={
        "username": email,
        "password": "Probe@Pass2026",
        "mfa_code": pyotp.TOTP(secret).now(),
    })
    assert res.status_code == 200
    assert res.json()["mfa_verified"] is True


def test_login_rate_limit_locks_out(client):
    last_status = None
    for _ in range(11):
        res = client.post("/api/auth/login", json={
            "username": "bruteforce_probe@lexsecure.local",
            "password": "wrong-password",
            "mfa_code": "000000",
        })
        last_status = res.status_code
    assert last_status == 429
