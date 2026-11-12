"""Wow-factor features: zero-width leak tracker + two-man rule."""
import io
import os
import sys
import tempfile
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base
from app.models.user import User, UserRole
from app.models.case import Case, CaseAssignment
from app.models.document import Document
import app.models.document, app.models.ledger, app.models.embedding, app.models.audit, app.models.signature, app.models.workflow, app.models.approval  # noqa
from app.security.jwt import hash_password
from app.security.pki import generate_key_pair
from app.services.doc_processor import process_and_store_document
from app.services.steganography import (
    generate_watermark_string, inject_watermark_bytes, extract_watermark_bytes,
    is_text_like, BIT_0, BIT_1, START_MARKER, END_MARKER,
)
from app.blockchain.ledger_service import ensure_genesis_block
from app.utils.time import utcnow


def make_db():
    tmp = tempfile.mktemp(suffix=".db")
    engine = create_engine(f"sqlite:///{tmp}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def make_user(db, email="w@local", role=UserRole.INVESTIGATOR):
    priv, pub = generate_key_pair()
    u = User(email=email, full_name="Wow Officer", role=role,
             department="CYBER_CRIME", hashed_password=hash_password("x"),
             public_key_pem=pub, private_key_pem=priv)
    db.add(u)
    db.commit()
    return u


def test_watermark_invisible_and_byte_aligned():
    frame = generate_watermark_string("a@b.c", 7, 42, 3, "2026-01-01T00:00:00")
    stripped = frame.replace(START_MARKER, '').replace(END_MARKER, '').replace(BIT_0, '').replace(BIT_1, '')
    assert stripped == "", "watermark must be fully invisible (zero-width only)"
    res = extract_watermark_bytes(("report body\n" + frame).encode('utf-8'))
    assert res["is_valid"] is True
    assert res["email"] == "a@b.c"
    assert res["user_id"] == 7
    assert res["document_id"] == 42
    assert res["version"] == 3


def test_watermark_survives_visible_edits_but_not_tampering():
    raw = b"first line\nsecond line"
    marked = inject_watermark_bytes(raw, "leak@x.local", 9, 1, 1, "2026-05-05T05:05:05")
    rendered = marked.decode('utf-8')
    for m in (START_MARKER, END_MARKER, BIT_0, BIT_1):
        rendered = rendered.replace(m, '')
    assert rendered == "first line\nsecond line"
    res = extract_watermark_bytes(b"FWD: see this\n" + marked + b"\n-- sent from my phone")
    assert res["is_valid"] is True and res["email"] == "leak@x.local"
    bad = marked.replace(BIT_1.encode('utf-8'), BIT_0.encode('utf-8'), 5)
    res2 = extract_watermark_bytes(bad)
    assert res2["is_valid"] is False


def test_plain_file_has_no_watermark():
    res = extract_watermark_bytes(b"just a normal boring file\nnothing hidden here")
    assert res["is_valid"] is False and "No watermark" in res["error"]


def test_is_text_like_guards_binaries():
    assert is_text_like(b"plain text evidence") is True
    assert is_text_like(bytes([0x89, 0x50, 0x4E, 0x47, 0x00, 0x01])) is False
    assert is_text_like(b"%PDF-1.4 binary \xff\xfe\x00garbage") is False


def _seed_dual_doc(db, user):
    db.add(Case(id="CASE-W-001", title="W", department="CYBER_CRIME"))
    db.commit()
    db.add(CaseAssignment(case_id="CASE-W-001", user_id=user.id, assignment_role="LEAD"))
    db.commit()
    res = process_and_store_document(db, user, "CASE-W-001", "secret.txt",
                                     b"top secret contents", "text/plain",
                                     title="Sealed Doc", requires_dual_auth=True)
    return res["document_id"]


def test_two_man_rule_blocks_then_grants_then_expires():
    from fastapi import HTTPException
    from app.api.documents import _enforce_dual_auth
    from app.models.approval import DualAuthRequest
    db = make_db()
    ensure_genesis_block(db)
    inv = make_user(db, "inv@local", UserRole.INVESTIGATOR)
    sup = make_user(db, "sup@local", UserRole.SUPERVISOR)
    did = _seed_dual_doc(db, sup)
    doc = db.query(Document).filter(Document.id == did).first()
    assert doc.requires_dual_auth is True

    try:
        _enforce_dual_auth(doc, inv, db, None, None)
        assert False, "expected 403"
    except HTTPException as e:
        assert e.status_code == 403
        assert e.detail["error"] == "TWO_MAN_RULE_REQUIRED"

    assert _enforce_dual_auth(doc, sup, db, None, None) is None

    grant = DualAuthRequest(document_id=did, requester_id=inv.id, status="APPROVED",
                            unlock_token="tok-live", expires_at=utcnow() + timedelta(hours=2))
    db.add(grant)
    db.commit()
    assert _enforce_dual_auth(doc, inv, db, None, "tok-live") is not None

    grant.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    try:
        _enforce_dual_auth(doc, inv, db, None, "tok-live")
        assert False, "expected 403 for expired grant"
    except HTTPException as e:
        assert e.status_code == 403
