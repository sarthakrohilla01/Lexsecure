"""Tests for the Google Gemini integration:"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database.session import Base
from app.models.user import User, UserRole
from app.models.case import Case, CaseAssignment
from app.models.document import Document
import app.models.document, app.models.ledger, app.models.embedding, app.models.audit  # noqa
from app.security.jwt import hash_password
from app.ai import llm as llm_module
from app.ai import embeddings as emb_module
from app.ai import vector_store as vs


def make_db():
    tmp = tempfile.mkstemp(suffix=".db")[1]
    engine = create_engine(f"sqlite:///{tmp}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


class SettingsOverride:
    """Temporarily overrides settings and restores them afterwards. Also isolates the Gemini allowlist and the on-disk "remembered model", so tests never inherit the developer's local .env configuration."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.kwargs.setdefault("GEMINI_MODELS", "")
        self._old = {}
        self._old_remembered = None

    def __enter__(self):
        for k, v in self.kwargs.items():
            self._old[k] = getattr(settings, k)
            setattr(settings, k, v)
        self._old_remembered = llm_module._remembered_model
        self._old_remember_write = llm_module._remember_model
        self._old_failures = dict(llm_module._model_failures)
        llm_module._model_failures.clear()
        llm_module._remembered_model = lambda: None
        llm_module._remember_model = lambda model: None
        return self

    def __exit__(self, *exc):
        for k, v in self._old.items():
            setattr(settings, k, v)
        llm_module._remembered_model = self._old_remembered
        llm_module._remember_model = self._old_remember_write
        llm_module._model_failures.clear()
        llm_module._model_failures.update(self._old_failures)
        return False


def test_status_endpoint_works_with_no_provider_configured():
    """Regression: provider 'none' must not raise (KeyError on unknown provider)."""
    from app.api.ai import get_ai_status
    with SettingsOverride(LLM_PROVIDER="none", LLM_MODEL="", LLM_BASE_URL="",
                          GEMINI_API_KEY="", LLM_API_KEY="",
                          EMBEDDING_PROVIDER="local"):
        status = get_ai_status()
    assert status["generation_mode"] == "deterministic-template"
    assert status["llm_ready"] is False
    assert status["embedding_provider"] == "local"


def test_gemini_requires_api_key():
    with SettingsOverride(LLM_PROVIDER="gemini", GEMINI_API_KEY="", LLM_API_KEY=""):
        assert llm_module.llm_configured() is False
        reason = llm_module.llm_missing_reason()
        assert reason and "GEMINI_API_KEY" in reason
        assert llm_module.generate_answer("q", ["some context"]) is None


def test_gemini_generation_uses_generate_content_endpoint():
    captured = {}

    class PostResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": [{"content": {"parts": [
                {"text": "A SIM swap was registered [Forensic Report v1]."}]}}]}

    class GetResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"models": [
                {"name": "models/gemini-2.0-flash",
                 "supportedGenerationMethods": ["generateContent"]}]}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return PostResponse()

    def fake_get(url, headers=None, timeout=None):
        return GetResponse()

    with SettingsOverride(LLM_PROVIDER="gemini", GEMINI_API_KEY="test-key",
                          LLM_MODEL="gemini-2.0-flash", LLM_BASE_URL=""):
        original_post, original_get = llm_module.httpx.post, llm_module.httpx.get
        llm_module.httpx.post = fake_post
        llm_module.httpx.get = fake_get
        llm_module._model_cache = []
        llm_module._model_cache_at = 0
        llm_module._model_failures.clear()
        try:
            assert llm_module.llm_configured() is True
            answer = llm_module.generate_answer("What about the SIM swap?",
                                                ["[Forensic Report v1]: A SIM swap was registered."])
        finally:
            llm_module.httpx.post = original_post
            llm_module.httpx.get = original_get
            llm_module._model_cache = []
            llm_module._model_cache_at = 0

    assert answer is not None
    assert "SIM swap" in answer
    assert captured["url"].endswith("/models/gemini-2.0-flash:generateContent")
    assert captured["headers"]["x-goog-api-key"] == "test-key"
    assert "systemInstruction" in captured["json"]


def test_gemini_quota_error_is_reported_and_triggers_cooldown():
    """A 429 (key-level quota) must be reported and must not be retried."""
    calls = []

    class Resp:
        status_code = 429

        def raise_for_status(self):
            raise llm_module.LLMCallError("HTTP 429", status_code=429)

        def json(self):
            return {"error": {"code": 429, "message": "You exceeded your current quota"}}

    with SettingsOverride(LLM_PROVIDER="gemini", GEMINI_API_KEY="test-key"):
        original_post, original_get = llm_module.httpx.post, llm_module.httpx.get
        llm_module.httpx.post = lambda *a, **k: (calls.append(a[0]), Resp())[1]
        llm_module.httpx.get = lambda *a, **k: Resp()
        llm_module._model_cache = []
        llm_module._model_cache_at = 0
        llm_module._model_failures.clear()
        llm_module._active_model = None
        llm_module._quota_until = 0.0
        try:
            assert llm_module.generate_answer("q", ["ctx"]) is None
            err = llm_module.llm_last_error()
            calls.clear()
            assert llm_module.generate_answer("q", ["ctx"]) is None
            assert calls == [], "quota cooldown did not short-circuit the HTTP call"
        finally:
            llm_module.httpx.post = original_post
            llm_module.httpx.get = original_get
            llm_module._model_cache = []
            llm_module._model_cache_at = 0
            llm_module._model_failures.clear()
            llm_module._quota_until = 0.0

    assert err is not None
    assert "quota" in err["reason"].lower()


def test_gemini_fails_over_to_a_live_model_when_configured_one_is_retired():
    """A retired model (404) must not break the request."""
    posted = []

    class Resp:
        def __init__(self, code, payload):
            self.status_code = code
            self._payload = payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise llm_module.LLMCallError(
                    f"HTTP {self.status_code}", status_code=self.status_code)
            return None

        def json(self):
            return self._payload

    def fake_post(url, json=None, headers=None, timeout=None):
        posted.append(url)
        if "gemini-old-flash" in url:
            return Resp(404, {"error": {"code": 404, "message": "no longer available"}})
        return Resp(200, {"candidates": [{"content": {"parts": [{"text": "live answer"}]}}]})

    def fake_get(url, headers=None, timeout=None):
        return Resp(200, {"models": [
            {"name": "models/gemini-old-flash",
             "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-3.6-flash",
             "supportedGenerationMethods": ["generateContent"]},
        ]})

    with SettingsOverride(LLM_PROVIDER="gemini", GEMINI_API_KEY="test-key",
                          LLM_MODEL="gemini-old-flash", LLM_BASE_URL=""):
        original_post, original_get = llm_module.httpx.post, llm_module.httpx.get
        llm_module.httpx.post = fake_post
        llm_module.httpx.get = fake_get
        llm_module._model_cache = []
        llm_module._model_cache_at = 0
        llm_module._model_failures.clear()
        llm_module._active_model = None
        try:
            answer = llm_module.generate_answer("q", ["ctx"])
        finally:
            llm_module.httpx.post = original_post
            llm_module.httpx.get = original_get
            llm_module._model_cache = []
            llm_module._model_cache_at = 0
            llm_module._model_failures.clear()

    assert answer == "live answer"
    assert any("gemini-3.6-flash" in u for u in posted)


def test_gemini_failure_is_recorded_for_the_ui():
    """A failed LLM call must be reported (never silently masked)."""
    class Resp:
        status_code = 500

        def raise_for_status(self):
            raise llm_module.LLMCallError("HTTP 500", status_code=500)

        def json(self):
            return {}

    with SettingsOverride(LLM_PROVIDER="gemini", GEMINI_API_KEY="test-key"):
        original_post, original_get = llm_module.httpx.post, llm_module.httpx.get
        llm_module.httpx.post = lambda *a, **k: Resp()
        llm_module.httpx.get = lambda *a, **k: Resp()
        llm_module._model_cache = []
        llm_module._model_cache_at = 0
        llm_module._model_failures.clear()
        llm_module._active_model = None
        try:
            assert llm_module.generate_answer("q", ["ctx"]) is None
            err = llm_module.llm_last_error()
        finally:
            llm_module.httpx.post = original_post
            llm_module.httpx.get = original_get
            llm_module._model_cache = []
            llm_module._model_cache_at = 0
            llm_module._model_failures.clear()

    assert err is not None
    assert err["provider"] == "gemini"
    assert err["reason"]


def test_gemini_failure_falls_back_to_template():
    class FakeResponse:
        status_code = 500

        def raise_for_status(self):
            raise httpx_error()

    def httpx_error():
        import httpx
        return httpx.HTTPStatusError("boom", request=None, response=None)

    with SettingsOverride(LLM_PROVIDER="gemini", GEMINI_API_KEY="test-key"):
        original = llm_module.httpx.post
        llm_module.httpx.post = lambda *a, **k: FakeResponse()
        try:
            assert llm_module.generate_answer("q", ["ctx"]) is None
        finally:
            llm_module.httpx.post = original


def test_gemini_embeddings_space_and_dimensions():
    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"embeddings": [
                {"values": [0.1] * 8},
                {"values": [0.2] * 8},
            ]}

    with SettingsOverride(EMBEDDING_PROVIDER="gemini", EMBEDDING_MODEL="gemini-embedding-001",
                          GEMINI_API_KEY="test-key", LLM_BASE_URL=""):
        emb_module.clear_cache()
        original = emb_module.httpx.post
        emb_module.httpx.post = lambda *a, **k: FakeResponse()
        try:
            assert emb_module.embedding_space_id() == "gemini:gemini-embedding-001"
            vecs = emb_module.generate_text_embeddings(["a", "b"])
        finally:
            emb_module.httpx.post = original
            emb_module.clear_cache()

    assert len(vecs) == 2
    assert len(vecs[0]) == 8


def test_vector_store_reembeds_chunks_from_a_different_space():
    """A chunk indexed in the local space must be re-embedded (not compared) when the active space is Gemini."""
    db = make_db()
    user = User(email="i@local", full_name="Inv", role=UserRole.INVESTIGATOR,
                department="Cyber Crime Division", hashed_password=hash_password("x"))
    db.add(user)
    db.commit()
    db.refresh(user)

    case = Case(id="CASE-T1", title="Test Case", department="Cyber Crime Division",
                status="UNDER_INVESTIGATION", classification="RESTRICTED", created_by_id=user.id)
    db.add(case)
    db.commit()

    db.add(CaseAssignment(case_id="CASE-T1", user_id=user.id,
                          assignment_role="LEAD_INVESTIGATOR"))
    db.commit()

    doc = Document(case_id="CASE-T1", title="SIM Swap Report", document_type="FIR",
                   classification="RESTRICTED", current_version=1, status="UNDER_REVIEW",
                   uploaded_by_id=user.id)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    with SettingsOverride(EMBEDDING_PROVIDER="local"):
        emb_module.clear_cache()
        vs.index_document_chunks(db, doc.id, 1, "CASE-T1",
                                 "The accused spoofed a SIM card in Delhi.\n\nA SIM swap was registered.")

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"embeddings": [{"values": [0.5, 0.5, 0.5, 0.5]}]}

    with SettingsOverride(EMBEDDING_PROVIDER="gemini", GEMINI_API_KEY="k", LLM_BASE_URL=""):
        emb_module.clear_cache()
        original = emb_module.httpx.post
        emb_module.httpx.post = lambda *a, **k: FakeResponse()
        try:
            results = vs.search_authorized_chunks(db, user, "SIM swap", limit=5)
        finally:
            emb_module.httpx.post = original
            emb_module.clear_cache()

    assert len(results) >= 1
    assert results[0]["document_id"] == doc.id
    assert results[0]["score"] > 0
