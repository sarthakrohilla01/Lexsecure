"""LexSecure backend smoke tests: crypto, hashing, ABAC-free pipeline, ledger chain."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base
from app.models.user import User, UserRole
from app.models.case import Case, CaseAssignment
from app.models.document import Document, DocumentVersion
from app.models.signature import DigitalSignature
import app.models.document, app.models.ledger, app.models.embedding, app.models.audit, app.models.signature, app.models.workflow  # noqa
from app.security.crypto import encrypt_document_bytes, decrypt_document_bytes
from app.security.hashing import calculate_sha256
from app.security.pki import generate_key_pair, sign_data_hash, verify_data_signature as verify_signature
from app.security.jwt import hash_password, verify_password, create_access_token, decode_access_token as decode_token
from app.services.doc_processor import process_and_store_document
from app.blockchain.ledger_service import ensure_genesis_block, verify_ledger_chain_integrity
from app.services.tamper_service import verify_version_integrity


def make_db():
    tmp = tempfile.mkstemp(suffix=".db")[1]
    engine = create_engine(f"sqlite:///{tmp}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_aes_roundtrip():
    plaintext = b"evidentiary payload 123"
    enc, iv, tag = encrypt_document_bytes(plaintext)
    assert enc != plaintext
    assert decrypt_document_bytes(enc, iv) == plaintext


def test_sha256_stable():
    assert calculate_sha256(b"abc") == calculate_sha256(b"abc")
    assert len(calculate_sha256(b"abc")) == 64


def test_pki_sign_verify():
    priv, pub = generate_key_pair()
    h = calculate_sha256(b"doc")
    sig = sign_data_hash(priv, h)
    assert verify_signature(pub, h, sig) is True
    assert verify_signature(pub, "00" * 32, sig) is False


def test_password_jwt():
    hp = hash_password("LexSecure@2026")
    assert verify_password("LexSecure@2026", hp)
    tok = create_access_token({"sub": "1"})
    assert decode_token(tok)["sub"] == "1"


def test_ocr_fallback_for_text_labeled_pdf():
    from app.services.ocr import extract_text_from_file
    text, _, ocr = extract_text_from_file(
        b"FIRST INFORMATION REPORT plain text payload",
        "FIR_CASE_001.pdf", "application/pdf")
    assert "FIRST INFORMATION REPORT" in text
    assert ocr is True


def test_sign_unsign_roundtrip_restores_review_status():
    from app.api.documents import sign_document, unsign_document
    from app.schemas.document import SignRequest
    db = make_db()
    ensure_genesis_block(db)
    priv, pub = generate_key_pair()
    user = User(email="s@local", full_name="Sign Officer", role=UserRole.FORENSIC_EXPERT,
                department="FORENSIC_LAB", hashed_password=hash_password("x"),
                public_key_pem=pub, private_key_pem=priv)
    db.add(user)
    db.add(Case(id="CASE-S-001", title="S", department="FORENSIC_LAB"))
    db.commit()
    db.add(CaseAssignment(case_id="CASE-S-001", user_id=user.id, assignment_role="FORENSIC_EXPERT"))
    db.commit()
    res = process_and_store_document(db, user, "CASE-S-001", "note.txt", b"sign me content", "text/plain", title="Sign Doc")
    did = res["document_id"]
    sign_document(did, SignRequest(), None, db, user)
    assert db.query(Document).filter(Document.id == did).first().status == "SIGNED"
    out = unsign_document(did, None, db, user)
    assert out["status"] == "SUCCESS"
    assert db.query(Document).filter(Document.id == did).first().status == "UNDER_REVIEW"
    assert db.query(DigitalSignature).join(
        DocumentVersion, DigitalSignature.version_id == DocumentVersion.id
    ).filter(DocumentVersion.document_id == did).count() == 0


def test_restore_is_idempotent_and_honest_about_missing_backup():
    from fastapi import HTTPException
    from app.services.tamper_service import (
        run_integrity_drill, restore_document_version,
    )
    db = make_db()
    ensure_genesis_block(db)
    priv, pub = generate_key_pair()
    user = User(email="r@local", full_name="Restore Officer", role=UserRole.INVESTIGATOR,
                department="CYBER_CRIME", hashed_password=hash_password("x"),
                public_key_pem=pub, private_key_pem=priv)
    db.add(user)
    db.add(Case(id="CASE-R-001", title="R", department="CYBER_CRIME"))
    db.commit()
    db.add(CaseAssignment(case_id="CASE-R-001", user_id=user.id, assignment_role="LEAD"))
    db.commit()
    res = process_and_store_document(db, user, "CASE-R-001", "r.txt", b"restore me", "text/plain", title="R Doc")
    vid = res["version_id"]

    assert restore_document_version(vid, user, db)["is_valid"] is True

    assert run_integrity_drill(vid, user, db)["is_valid"] is False
    assert restore_document_version(vid, user, db)["is_valid"] is True

    run_integrity_drill(vid, user, db)
    from app.storage import get_storage_service
    store = get_storage_service()
    v = db.query(DocumentVersion).filter(DocumentVersion.id == vid).first()
    store.delete_file(v.object_key + ".original_backup")
    try:
        restore_document_version(vid, user, db)
        assert False, "expected HTTPException"
    except HTTPException as e:
        assert e.status_code == 409


def test_chatbot_small_talk_never_cites_evidence():
    from app.ai.rag_engine import generate_rag_response
    db = make_db()
    ensure_genesis_block(db)
    priv, pub = generate_key_pair()
    user = User(email="c@local", full_name="Chat Officer", role=UserRole.INVESTIGATOR,
                department="CYBER_CRIME", hashed_password=hash_password("x"),
                public_key_pem=pub, private_key_pem=priv)
    db.add(user)
    db.commit()
    for msg in ["hi", "Hello!", "who are you?", "help", "thanks", "bye"]:
        res = generate_rag_response(db, user, msg)
        assert res["sources"] == []
        assert res["status"] == "SUCCESS"
        assert "According to the authorized documents" not in res["answer"]


def test_full_pipeline_and_ledger():
    db = make_db()
    ensure_genesis_block(db)
    priv, pub = generate_key_pair()
    user = User(email="t@local", full_name="T Officer", role=UserRole.INVESTIGATOR,
                department="CYBER_CRIME", hashed_password=hash_password("x"),
                public_key_pem=pub, private_key_pem=priv)
    db.add(user)
    case = Case(id="CASE-T-001", title="T", department="CYBER_CRIME")
    db.add(case)
    db.commit()
    db.add(CaseAssignment(case_id="CASE-T-001", user_id=user.id, assignment_role="LEAD"))
    db.commit()
    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\nfirst report content here"
    )
    res = process_and_store_document(db, user, "CASE-T-001", "FIR_T.pdf", pdf_bytes, "application/pdf", title="T Doc")
    assert res["sha256_hash"] == calculate_sha256(pdf_bytes)
    chain = verify_ledger_chain_integrity(db)
    assert chain["is_valid"] is True
    report = verify_version_integrity(res["version_id"], db)
    assert report["is_valid"] is True
