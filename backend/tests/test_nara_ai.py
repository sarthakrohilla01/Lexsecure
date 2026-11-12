"""Tests for the NaraRouter provider:"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.ai import llm as llm_module


class SettingsOverride:
    """Temporarily overrides settings and restores them afterwards."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.kwargs.setdefault("NARA_API_KEY", "sk-nry-test")
        self.kwargs.setdefault("NARA_MODELS", "")
        self.kwargs.setdefault("LLM_BASE_URL", "")
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


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise llm_module.LLMCallError(
                f"HTTP {self.status_code}", status_code=self.status_code)
        return None

    def json(self):
        return self._payload


def test_nara_chat_uses_openai_compatible_endpoint():
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return FakeResponse(200, {"choices": [{"message": {"content": "A SIM swap was registered [Forensic Report v1]."}}]})

    with SettingsOverride(LLM_PROVIDER="nara", LLM_MODEL="qwen3.8-flash"):
        original = llm_module.httpx.post
        llm_module.httpx.post = fake_post
        llm_module._active_model = None
        try:
            answer = llm_module.generate_answer("What was found?", ["[Forensic Report v1]: SIM swap"])
        finally:
            llm_module.httpx.post = original

    assert answer == "A SIM swap was registered [Forensic Report v1]."
    assert captured["url"] == "https://router.bynara.id/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-nry-test"
    assert captured["json"]["model"] == "qwen3.8-flash"
    assert captured["json"]["messages"][0]["role"] == "system"
    assert captured["json"]["stream"] is False


def test_nara_telegram_activation_error_is_actionable():
    """The router's 403 envelope must produce a clear, actionable message."""

    def fake_post(url, json=None, headers=None, timeout=None):
        return FakeResponse(403, {"error": {
            "type": "forbidden",
            "message": "telegram_required: Please bind your Telegram account at /settings to continue.",
        }})

    with SettingsOverride(LLM_PROVIDER="nara", LLM_MODEL="qwen3.8-flash"):
        original = llm_module.httpx.post
        llm_module.httpx.post = fake_post
        llm_module._active_model = None
        try:
            assert llm_module.generate_answer("q", ["ctx"]) is None
            err = llm_module.llm_last_error()
        finally:
            llm_module.httpx.post = original

    assert err is not None
    assert "Telegram" in err["reason"]
    assert "router.bynara.id/settings" in err["reason"]


def test_nara_fails_over_to_the_next_configured_model():
    posted = []

    def fake_post(url, json=None, headers=None, timeout=None):
        posted.append(json["model"])
        if json["model"] == "model-a":
            return FakeResponse(500, {"error": {"type": "server_error", "message": "boom"}})
        return FakeResponse(200, {"choices": [{"message": {"content": "ok from " + json["model"]}}]})

    with SettingsOverride(LLM_PROVIDER="nara", LLM_MODEL="model-a",
                          NARA_MODELS="model-a,model-b"):
        original = llm_module.httpx.post
        llm_module.httpx.post = fake_post
        llm_module._active_model = None
        try:
            answer = llm_module.generate_answer("q", ["ctx"])
        finally:
            llm_module.httpx.post = original

    assert answer == "ok from model-b"
    assert posted == ["model-a", "model-b"]


def test_nara_rate_limit_triggers_cooldown_and_stops_failover():
    """A 429 is a plan-level limit: no further model attempts, no more requests."""
    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append(json["model"])
        return FakeResponse(429, {"error": {"type": "rate_limited", "message": "slow down"}})

    with SettingsOverride(LLM_PROVIDER="nara", LLM_MODEL="model-a",
                          NARA_MODELS="model-a,model-b"):
        original = llm_module.httpx.post
        llm_module.httpx.post = fake_post
        llm_module._active_model = None
        llm_module._quota_until = 0.0
        try:
            assert llm_module.generate_answer("q", ["ctx"]) is None
            err = llm_module.llm_last_error()
            calls.clear()
            assert llm_module.generate_answer("q", ["ctx"]) is None
            assert calls == [], "cooldown did not short-circuit the HTTP call"
        finally:
            llm_module.httpx.post = original
            llm_module._quota_until = 0.0

    assert err is not None
    assert "rate" in err["reason"].lower() or "limit" in err["reason"].lower()


def test_nara_missing_key_is_reported():
    with SettingsOverride(LLM_PROVIDER="nara", NARA_API_KEY="", LLM_API_KEY=""):
        assert llm_module.llm_configured() is False
        reason = llm_module.llm_missing_reason()
        assert reason and "NARA_API_KEY" in reason
        assert llm_module.generate_answer("q", ["ctx"]) is None
