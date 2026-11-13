"""LLM answer synthesis over ABAC-filtered context."""

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger("lexsecure.llm")

_MAX_CONTEXT_CHARS = 8000

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_DEFAULTS = {
    "ollama": {"base_url": "http://localhost:11434", "model": "llama3.2"},
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "model": "gemini-3.8-flash",
    },
    "nara": {
        "base_url": "https://router.bynara.id/v1",
        "model": "agnes-2.5-flash",
    },
}

_last_error: Optional[Dict[str, Any]] = None
_active_model: Optional[str] = None
_model_cache: List[str] = []
_model_cache_at: float = 0.0
_MODEL_FAILOVER_BUDGET_SECONDS = 30
# The gateway's free tier queues heavily: measured 30-45s per answer.
_NARA_TOTAL_BUDGET_SECONDS = 150
_NARA_ATTEMPT_TIMEOUT_SECONDS = 120
_GEMINI_ATTEMPT_TIMEOUT_SECONDS = 12
_MODEL_SICK_WINDOW_SECONDS = 120
_model_failures: Dict[str, float] = {}
_quota_until: float = 0.0
_QUOTA_COOLDOWN_SECONDS = 45
_REMEMBERED_MODEL_FILE = os.path.join(
    _BACKEND_DIR, f".{(settings.LLM_PROVIDER or 'default').strip().lower()}_active_model")


def _remembered_model() -> Optional[str]:
    try:
        with open(_REMEMBERED_MODEL_FILE, encoding="utf-8") as f:
            return f.read().strip() or None
    except Exception:
        return None


def _remember_model(model: str) -> None:
    try:
        with open(_REMEMBERED_MODEL_FILE, "w", encoding="utf-8") as f:
            f.write(model)
    except OSError as exc:
        logger.debug("Could not persist the active model to %s: %s", _REMEMBERED_MODEL_FILE, exc)


def quota_state() -> Optional[Dict[str, Any]]:
    if _quota_until and time.time() < _quota_until:
        return {
            "quota_exhausted": True,
            "retry_in_seconds": int(_quota_until - time.time()),
            "message": "Provider quota exhausted — cooling down to avoid burning requests.",
        }
    if _last_error and _last_error.get("reason", "").lower().find("quota") >= 0:
        return {
            "quota_exhausted": True,
            "retry_in_seconds": 0,
            "message": _last_error.get("reason"),
        }
    return None


def allowed_models() -> List[str]:
    raw = (settings.GEMINI_MODELS or "").strip()
    if not raw:
        return []
    return [m.strip() for m in raw.split(",") if m.strip()]


def llm_last_error() -> Optional[Dict[str, Any]]:
    return dict(_last_error) if _last_error else None


def active_model() -> str:
    return _active_model or _remembered_model() or (_resolved_model() or "unknown")


def llm_configured() -> bool:
    provider = _resolved_provider()
    if provider not in _DEFAULTS:
        return False
    if provider == "gemini":
        return bool(_api_key())
    if provider == "nara":
        return bool(_nara_api_key())
    if provider == "openai":
        return bool(settings.LLM_API_KEY or settings.LLM_BASE_URL)
    return True


def llm_missing_reason() -> Optional[str]:
    provider = _resolved_provider()
    if provider not in _DEFAULTS:
        return None
    if provider == "gemini" and not _api_key():
        return (
            "Gemini selected but no API key found. Set GEMINI_API_KEY "
            "(or LLM_API_KEY) in backend/.env — get a key at "
            "https://aistudio.google.com/apikey"
        )
    if provider == "nara" and not _nara_api_key():
        return (
            "NaraRouter selected but no API key found. Set NARA_API_KEY in "
            "backend/.env — issue a key at https://router.bynara.id "
            "(keys start with 'sk-nry-')."
        )
    if provider == "openai" and not (settings.LLM_API_KEY or settings.LLM_BASE_URL):
        return "OpenAI-compatible provider selected but no LLM_API_KEY / LLM_BASE_URL set."
    return None


def _resolved_provider() -> str:
    return settings.LLM_PROVIDER.strip().lower()


def _resolved_model() -> Optional[str]:
    explicit = settings.LLM_MODEL.strip()
    if explicit:
        return explicit
    defaults = _DEFAULTS.get(_resolved_provider())
    return defaults["model"] if defaults else None


def _resolved_base_url() -> Optional[str]:
    if _resolved_provider() == "nara":
        explicit = settings.NARA_BASE_URL.strip()
        if explicit:
            return explicit.rstrip("/")
    explicit = settings.LLM_BASE_URL.strip()
    if explicit:
        return explicit.rstrip("/")
    defaults = _DEFAULTS.get(_resolved_provider())
    return defaults["base_url"].rstrip("/") if defaults else None


def _api_key() -> str:
    return (settings.GEMINI_API_KEY or settings.LLM_API_KEY or "").strip()


def _nara_api_key() -> str:
    return (settings.NARA_API_KEY or settings.LLM_API_KEY or "").strip()


def _nara_base_url() -> str:
    return (settings.NARA_BASE_URL or "https://router.bynara.id/v1").rstrip("/")


def nara_models() -> List[str]:
    raw = (settings.NARA_MODELS or "").strip()
    if not raw:
        return []
    return [m.strip() for m in raw.split(",") if m.strip()]


def _build_messages(question: str, context_passages: List[str]):
    context = "\n\n".join(context_passages)[:_MAX_CONTEXT_CHARS]
    system = (
        "You are the LexSecure Investigative Assistant for a law-enforcement "
        "evidence platform. Answer the officer's question using ONLY the "
        "EVIDENCE CONTEXT provided.\n\n"
        "CONTENT RULES:\n"
        "1. Cite sources inline as [Document Title vN] for every factual claim.\n"
        "2. If the answer is not contained in the context, say exactly that and "
        "do not invent details.\n"
        "3. Never mention or guess about documents outside the context.\n"
        "4. Be precise, professional, and concise (police-briefing style).\n\n"
        "FORMATTING RULES (the interface renders Markdown — use it):\n"
        "- Start with a one-sentence direct answer, then the supporting detail.\n"
        "- Use short paragraphs (1-3 sentences), never one giant block of text.\n"
        "- For multi-part findings use a '- ' bullet list.\n"
        "- Use **bold** for the key fact that begins a bullet (e.g. **Chain of "
        "custody:** hashes matched).\n"
        "- Use a numbered list only for sequences of events or procedural steps.\n"
        "- Separate distinct sections with a blank line.\n"
        "- Use `inline code` for identifiers such as hashes, IMEIs, IPs or file names.\n"
        "- Do not use tables, headings (#), or HTML. Keep it under ~200 words."
    )
    user = f"EVIDENCE CONTEXT:\n{context}\n\nOFFICER'S QUESTION: {question}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


class LLMCallError(Exception):
    """Raised when the provider call fails, carrying the HTTP status if known."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def _list_gemini_models(force: bool = False) -> List[str]:
    """Models this key can call with generateContent, cached for 5 minutes."""
    global _model_cache, _model_cache_at
    now = time.time()
    if (not force and _model_cache and now - _model_cache_at < 300):
        return _model_cache
    try:
        resp = httpx.get(
            f"{_resolved_base_url()}/models",
            headers={"x-goog-api-key": _api_key()},
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        available: List[str] = []
        for m in (resp.json() or {}).get("models", []):
            name = (m.get("name") or "").replace("models/", "")
            methods = m.get("supportedGenerationMethods") or []
            if name and "generateContent" in methods:
                available.append(name)
        _model_cache = available
        _model_cache_at = now
        return available
    except Exception as exc:
        logger.warning("Could not list Gemini models: %s", exc)
        return _model_cache or []


def _text_chat_models(available: List[str]) -> List[str]:
    return [m for m in available if re.fullmatch(r"gemini-[\d.]+-(flash|pro)", m)]


def _model_preference(available: List[str]) -> List[str]:
    """Newest flash first, then newest pro; TTS/image/gemma are excluded."""
    def version_key(name: str):
        nums = re.findall(r"\d+", name)
        return tuple(int(n) for n in nums) or (0,)

    text_chat = [m for m in available if re.fullmatch(r"gemini-[\d.]+-(flash|pro)", m)]
    flash = sorted([m for m in text_chat if m.endswith("-flash")], key=version_key, reverse=True)
    pro = sorted([m for m in text_chat if m.endswith("-pro")], key=version_key, reverse=True)
    others = [m for m in available if m not in text_chat]
    return flash + pro + others


def _pick_available_model(available: List[str], preferred: str) -> Optional[str]:
    """Google retires model names with a 404, so fall back to the newest live one."""
    if not available:
        return None
    if preferred in available:
        return preferred
    ordered = _model_preference(available)
    return ordered[0] if ordered else None


def _gemini_payload(messages, include_thinking: bool = True) -> Dict[str, Any]:
    system_text = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_text = next((m["content"] for m in messages if m["role"] == "user"), "")
    generation_config: Dict[str, Any] = {
        "temperature": 0.2,
        "maxOutputTokens": 2048,
    }
    if include_thinking and settings.LLM_THINKING_BUDGET is not None:
        generation_config["thinkingConfig"] = {"thinkingBudget": settings.LLM_THINKING_BUDGET}
    return {
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "systemInstruction": {"parts": [{"text": system_text}]},
        "generationConfig": generation_config,
    }


def _gemini_post(url: str, payload: Dict[str, Any], headers: Dict[str, str],
                 attempts: int = 1) -> httpx.Response:
    """POST with a short timeout so an overloaded model fails over quickly."""
    response: Optional[httpx.Response] = None
    timeout = min(settings.LLM_TIMEOUT_SECONDS, _GEMINI_ATTEMPT_TIMEOUT_SECONDS)
    for attempt in range(attempts):
        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=timeout)
        except Exception:
            if attempt < attempts - 1:
                time.sleep(1.0 * (2 ** attempt))
                continue
            raise
        if response.status_code not in (429, 500, 502, 503, 504):
            return response
        if attempt < attempts - 1:
            delay = 1.0 * (2 ** attempt)
            logger.warning("Gemini HTTP %s — retrying in %.1fs (attempt %d/%d)",
                           response.status_code, delay, attempt + 1, attempts)
            time.sleep(delay)
    return response


def _model_is_sick(model: str) -> bool:
    ts = _model_failures.get(model)
    return bool(ts) and (time.time() - ts) < _MODEL_SICK_WINDOW_SECONDS


def _generate_gemini(messages) -> Optional[str]:
    """Gemini generateContent with failover across live models. A 429 is key-level on the free tier, so it stops the chain instead of retrying other models."""
    global _active_model, _quota_until

    _check_quota_cooldown()

    payload = _gemini_payload(messages)
    headers = {"x-goog-api-key": _api_key(), "Content-Type": "application/json"}

    preferred = _resolved_model()
    available = _list_gemini_models()
    allow = allowed_models()

    if allow:
        candidates = [m for m in allow if m in available] or allow
        ordered = _model_preference(candidates)
    else:
        healthy = [m for m in available if not _model_is_sick(m)]
        ordered = _model_preference(healthy or available)
        chat = _text_chat_models(ordered)
        if chat:
            ordered = chat

    chain: List[str] = []
    remembered = _remembered_model()
    for m in [remembered, _active_model, preferred] + ordered:
        if not m or m in chain:
            continue
        if allow and m not in allow:
            continue
        if _model_is_sick(m) and ordered:
            continue
        chain.append(m)
    if not chain:
        chain = [m for m in [remembered, preferred] + ordered if m and (not allow or m in allow)]
    chain = chain[:5]

    deadline = time.time() + _MODEL_FAILOVER_BUDGET_SECONDS
    last_error: Optional[Exception] = None
    preferred_error: Optional[Exception] = None
    quota_error: Optional[Exception] = None
    quota_models: List[str] = []
    other_error = False

    for model in chain:
        if time.time() > deadline and last_error is not None:
            break
        url = f"{_resolved_base_url()}/models/{model}:generateContent"
        try:
            resp = _gemini_post(url, payload, headers)
        except Exception as exc:
            last_error = exc
            if model == preferred:
                preferred_error = exc
            _model_failures[model] = time.time()
            logger.warning("Gemini model '%s' failed/timeout (%s); failing over.",
                           model, type(exc).__name__)
            continue

        if resp.status_code == 400 and _mentions_thinking(resp):
            logger.warning("Model '%s' rejects thinkingConfig; retrying without it.", model)
            try:
                resp = _gemini_post(url, _gemini_payload(messages, include_thinking=False), headers)
            except Exception as exc:
                last_error = exc
                if model == preferred:
                    preferred_error = exc
                _model_failures[model] = time.time()
                continue

        if resp.status_code == 429:
            quota_models.append(model)
            _model_failures[model] = time.time()
            quota_error = LLMCallError(
                f"Gemini quota exceeded for this API key (all available models are "
                f"rate-limited: {', '.join(quota_models)}). Check your quota and "
                f"billing at https://aistudio.google.com/apikey",
                status_code=429)
            last_error = quota_error
            logger.warning("Gemini quota exceeded for model %s; trying the next model.", model)
            continue

        if resp.status_code == 404:
            err = LLMCallError(f"model {model} is no longer available", status_code=404)
            last_error = err
            other_error = True
            if model == preferred:
                preferred_error = err
            _model_failures[model] = time.time()
            logger.warning("Configured Gemini model '%s' is retired; trying next live model.", model)
            continue

        if resp.status_code in (500, 502, 503, 504):
            err = LLMCallError(f"Gemini returned {resp.status_code}", status_code=resp.status_code)
            last_error = err
            other_error = True
            if model == preferred:
                preferred_error = err
            _model_failures[model] = time.time()
            logger.warning("Gemini model '%s' unavailable (%s); failing over.",
                           model, resp.status_code)
            continue

        resp.raise_for_status()
        _active_model = model
        _remember_model(model)
        _model_failures.pop(model, None)
        data = resp.json() or {}
        candidates = data.get("candidates") or []
        if not candidates:
            raise ValueError(f"Gemini returned no candidates: {str(data)[:200]}")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            feedback = candidates[0].get("finishReason") or data.get("promptFeedback")
            raise ValueError(f"Gemini returned an empty answer (finishReason={feedback})")
        return text

    if quota_error is not None and preferred_error is None:
        preferred_error = quota_error
    if quota_error is not None and not other_error:
        _quota_until = time.time() + _QUOTA_COOLDOWN_SECONDS
    for candidate in (quota_error, preferred_error, last_error):
        if candidate is not None:
            raise candidate
    return None


def _nara_error_message(resp) -> Optional[str]:
    """Decode NaraRouter's {"error": {"type", "message"}} envelope."""
    try:
        payload = resp.json()
    except Exception:
        return None
    err = payload.get("error")
    if not isinstance(err, dict):
        return None
    etype = (err.get("type") or "").strip()
    msg = (err.get("message") or "").strip()
    lowered = msg.lower()
    if "telegram" in lowered:
        if "group" in lowered or "channel" in lowered or "relink" in lowered:
            return ("NaraRouter: Telegram verification incomplete — join the required "
                    "Telegram group/channel, then relink your account at "
                    "https://router.bynara.id/settings.")
        return ("NaraRouter: this API key is not activated yet — bind your Telegram account "
                "at https://router.bynara.id/settings, then retry.")
    if etype == "forbidden":
        return f"NaraRouter: access forbidden — {msg or 'check your key and plan'}."
    if etype in ("rate_limited", "quota_exceeded", "insufficient_quota"):
        detail = msg or "rate/quota limit reached for this key"
        return f"NaraRouter: {etype.replace('_', ' ')} — {detail}."
    return f"NaraRouter error [{etype or 'unknown'}]: {msg}" if msg else None


def _check_quota_cooldown():
    if _quota_until and time.time() < _quota_until:
        remaining = int(_quota_until - time.time())
        raise LLMCallError(
            f"Provider quota exhausted for this API key — retrying in ~{remaining}s "
            f"(check quota/billing for your provider)",
            status_code=429)


def _generate_nara(messages) -> Optional[str]:
    """NaraRouter chat completion (OpenAI-compatible: /v1/chat/completions)."""
    global _active_model, _quota_until

    _check_quota_cooldown()

    preferred = _resolved_model()
    chain: List[str] = []
    for m in [preferred] + nara_models():
        if m and m not in chain:
            chain.append(m)
    chain = chain[:5]

    healthy = [m for m in chain if not _model_is_sick(m)]
    if healthy:
        chain = healthy

    deadline = time.time() + _NARA_TOTAL_BUDGET_SECONDS

    last_error: Optional[Exception] = None
    for model in chain:
        remaining = deadline - time.time()
        if remaining <= 1:
            logger.warning("NaraRouter failover budget exhausted; stopping.")
            break
        payload = {
            "model": model,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
            "temperature": 0.2,
            "max_tokens": settings.LLM_MAX_OUTPUT_TOKENS,
            "stream": False,
        }
        try:
            resp = httpx.post(
                f"{_nara_base_url()}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {_nara_api_key()}",
                    "Content-Type": "application/json",
                },
                timeout=min(remaining, _NARA_ATTEMPT_TIMEOUT_SECONDS),
            )
        except Exception as exc:
            last_error = exc
            _model_failures[model] = time.time()
            logger.warning("NaraRouter model '%s' failed (%s); trying next model.",
                           model, type(exc).__name__)
            continue

        if resp.status_code >= 400:
            detail = _nara_error_message(resp)
            err = LLMCallError(
                detail or f"NaraRouter returned HTTP {resp.status_code}",
                status_code=resp.status_code)
            last_error = err
            if resp.status_code in (401, 403):
                logger.warning("NaraRouter rejected the key: %s", detail)
                break
            if resp.status_code == 429:
                _quota_until = time.time() + _QUOTA_COOLDOWN_SECONDS
                logger.warning("NaraRouter rate limit reached — cooling down %ds.",
                               _QUOTA_COOLDOWN_SECONDS)
                break
            _model_failures[model] = time.time()
            logger.warning("NaraRouter model '%s' returned HTTP %s; trying next model.",
                           model, resp.status_code)
            continue

        data = resp.json() or {}
        choices = data.get("choices") or []
        if not choices:
            raise ValueError(f"NaraRouter returned no choices: {str(data)[:200]}")
        message = choices[0].get("message") or {}
        text = (message.get("content") or "").strip()
        if not text:
            raise ValueError(
                f"NaraRouter returned an empty answer (finish_reason="
                f"{choices[0].get('finish_reason')})")
        _active_model = model
        _model_failures.pop(model, None)
        _remember_model(model)
        return text

    if last_error is not None:
        raise last_error
    return None


def _generate_openai(messages) -> Optional[str]:
    headers = {"Content-Type": "application/json"}
    if settings.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"
    resp = httpx.post(
        f"{_resolved_base_url()}/chat/completions",
        json={
            "model": _resolved_model(),
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
            "temperature": 0.2,
        },
        headers=headers,
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    payload = resp.json() or {}
    return payload["choices"][0]["message"]["content"]


def _generate_ollama(messages) -> Optional[str]:
    resp = httpx.post(
        f"{_resolved_base_url()}/api/chat",
        json={
            "model": _resolved_model(),
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
            "stream": False,
            "options": {"temperature": 0.2},
        },
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return (resp.json() or {}).get("message", {}).get("content")


def generate_answer(question: str, context_passages: List[str]) -> Optional[str]:
    """Synthesize an answer, or return None so the caller uses the template."""
    global _last_error

    if not llm_configured() or not context_passages:
        return None

    provider = _resolved_provider()
    model = _resolved_model()
    messages = _build_messages(question, context_passages)

    try:
        if provider == "gemini":
            content = _generate_gemini(messages)
        elif provider == "nara":
            content = _generate_nara(messages)
        elif provider == "ollama":
            content = _generate_ollama(messages)
        else:
            content = _generate_openai(messages)

        if isinstance(content, str) and content.strip():
            _last_error = None
            return content.strip()

        _last_error = {
            "provider": provider,
            "model": model,
            "reason": ("The model returned an empty response — it may be temporarily "
                       "unavailable for this API key."),
        }
        logger.warning("LLM returned an empty response (provider=%s, model=%s)", provider, model)
        return None
    except Exception as exc:
        _last_error = {
            "provider": provider,
            "model": model,
            "reason": _friendly_error(exc),
        }
        logger.warning(
            "LLM generation failed, using template "
            "(provider=%s, model=%s, error=%s)", provider, model, exc
        )
        return None


def _mentions_thinking(resp) -> bool:
    try:
        message = (resp.json().get("error") or {}).get("message", "")
    except Exception:
        return False
    return "thinking" in message.lower()


def _friendly_error(exc: Exception) -> str:
    if isinstance(exc, LLMCallError) and str(exc).strip():
        return str(exc).strip()
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if status == 404:
        return ("The configured model is no longer available. "
                "Update LLM_MODEL in backend/.env (or let auto-recovery pick a live model).")
    if status == 401:
        return "Gemini rejected the API key. Check GEMINI_API_KEY in backend/.env."
    if status == 403:
        return "The API key is not allowed to use this model."
    if status == 429:
        return ("Gemini quota/rate limit reached for this API key (all usable models were "
                "busy). Check your quota at https://aistudio.google.com/apikey and retry shortly.")
    if status == 503:
        return "Gemini is under heavy load right now (all fallback models were busy) — please retry in a moment."
    if status is not None:
        return f"The AI provider returned HTTP {status}."
    return f"Could not reach the AI provider ({type(exc).__name__})."
