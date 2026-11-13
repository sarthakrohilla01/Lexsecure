"""Tests for the Audit Trail export feature:"""
import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.database.session import Base
from app.models.user import User, UserRole
from app.security.jwt import hash_password
from app.audit.logger import record_audit_event
from app.api.audit import export_audit_logs, list_audit_logs


def make_db():
    tmp = tempfile.mkstemp(suffix=".db")[1]
    engine = create_engine(f"sqlite:///{tmp}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def make_users(db):
    inv = User(email="inv@local", full_name="Investigator", role=UserRole.INVESTIGATOR,
               department="Cyber Crime Division", hashed_password=hash_password("x"))
    sup = User(email="sup@local", full_name="Supervisor", role=UserRole.SUPERVISOR,
               department="Administration", hashed_password=hash_password("x"))
    db.add_all([inv, sup])
    db.commit()
    db.refresh(inv), db.refresh(sup)
    return inv, sup


def seed_events(db, inv, sup):
    record_audit_event(db=db, action="LOGIN_SUCCESS", details="inv in", user=inv)
    record_audit_event(db=db, action="DOCUMENT_VIEWED", details="inv viewed doc", user=inv)
    record_audit_event(db=db, action="LOGIN_SUCCESS", details="sup in", user=sup)
    record_audit_event(db=db, action="CASE_ACCESS_DENIED", details="blocked", user=inv, status="BLOCKED")


def test_csv_export_scopes_to_own_events_for_investigator():
    db = make_db()
    inv, sup = make_users(db)
    seed_events(db, inv, sup)

    resp = export_audit_logs(format="csv", db=db, current_user=inv)
    body = resp.body.decode("utf-8-sig")
    lines = [entry for entry in body.splitlines() if entry.strip()]

    assert lines[0].startswith("id,timestamp,user_id,user_email,user_role")
    assert "inv@local" in body
    assert "sup@local" not in body, "investigator export leaked another user's events"
    assert len(lines) == 1 + 3


def test_supervisor_export_sees_all_events():
    db = make_db()
    inv, sup = make_users(db)
    seed_events(db, inv, sup)

    resp = export_audit_logs(format="csv", db=db, current_user=sup)
    body = resp.body.decode("utf-8-sig")
    assert "inv@local" in body and "sup@local" in body
    assert int(resp.headers["X-Export-Count"]) == 4


def test_export_headers_contain_filename_and_matching_sha256():
    db = make_db()
    inv, sup = make_users(db)
    seed_events(db, inv, sup)

    resp = export_audit_logs(format="csv", db=db, current_user=sup)
    digest = hashlib.sha256(resp.body).hexdigest()
    assert resp.headers["X-Export-SHA256"] == digest
    assert 'attachment; filename="lexsecure_audit_trail_' in resp.headers["Content-Disposition"]
    assert resp.headers["Content-Disposition"].endswith('.csv"')
    assert resp.media_type.startswith("text/csv")


def test_json_export_shape_and_scope_field():
    db = make_db()
    inv, sup = make_users(db)
    seed_events(db, inv, sup)

    resp = export_audit_logs(format="json", db=db, current_user=inv)
    payload = json.loads(resp.body)
    assert payload["export"]["count"] == len(payload["events"]) == 3
    assert payload["export"]["scope"] == "USER_EVENTS_ONLY:inv@local"
    assert all(e["user_email"] == "inv@local" for e in payload["events"])
    assert payload["export"]["generated_by"] == "inv@local"


def test_export_is_recorded_in_the_audit_trail():
    db = make_db()
    inv, sup = make_users(db)
    seed_events(db, inv, sup)

    resp = export_audit_logs(format="csv", action="LOGIN_SUCCESS", db=db, current_user=sup)
    digest = resp.headers["X-Export-SHA256"]

    events = list_audit_logs(action="AUDIT_EXPORTED", limit=50, db=db, current_user=sup)
    assert len(events) == 1
    assert events[0]["user_email"] == "sup@local"
    assert digest[:16] in events[0]["details"]


def test_invalid_format_rejected():
    db = make_db()
    inv, sup = make_users(db)
    try:
        export_audit_logs(format="pdf", db=db, current_user=inv)
        raise AssertionError("invalid format should raise 422")
    except HTTPException as e:
        assert e.status_code == 422


def test_export_filters_match_list_view():
    db = make_db()
    inv, sup = make_users(db)
    seed_events(db, inv, sup)

    listed = list_audit_logs(action="LOGIN_SUCCESS", limit=50, db=db, current_user=sup)
    resp = export_audit_logs(format="csv", action="LOGIN_SUCCESS", db=db, current_user=sup)
    body = resp.body.decode("utf-8-sig")
    assert int(resp.headers["X-Export-Count"]) == len(listed) == 2
    assert "DOCUMENT_VIEWED" not in body
