"""Google Gemini Connectivity Checker"""

import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

from app.config import settings

BASE = (settings.LLM_BASE_URL.strip()
        or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
KEY = (settings.GEMINI_API_KEY or settings.LLM_API_KEY or "").strip()
MODEL = settings.LLM_MODEL.strip() or "gemini-3.8-flash"
EMB_MODEL = settings.EMBEDDING_MODEL.strip() or "gemini-embedding-001"
_SCAN_DELAY_SECONDS = 5


def live_models():
    """Text-chat models this key can actually use right now."""
    try:
        r = httpx.get(f"{BASE}/models", headers={"x-goog-api-key": KEY}, timeout=30)
        r.raise_for_status()
        out = []
        for m in r.json().get("models", []):
            name = (m.get("name") or "").replace("models/", "")
            if name and "generateContent" in (m.get("supportedGenerationMethods") or []):
                out.append(name)
        chat = [m for m in out if re.fullmatch(r"gemini-[\d.]+-(flash|pro)", m)]
        return chat or out
    except Exception:
        return []


def suggest_model():
    """Newest stable flash model available for this key."""
    models = live_models()
    flash = [m for m in models if m.startswith("gemini-") and m.endswith("-flash")
             and m.replace("gemini-", "").replace("-flash", "").replace(".", "").isdigit()]
    if flash:
        def ver(m):
            nums = [int(x) for x in m.replace("gemini-", "").replace("-flash", "").split(".") if x.isdigit()]
            return tuple(nums) or (0,)
        return sorted(flash, key=ver, reverse=True)[0]
    for alias in ("gemini-flash-latest", "gemini-2.5-flash", "gemini-2.5-pro"):
        if alias in models:
            return alias
    return None


def banner(text: str):
    print(f"\n=== {text} ===")


def check_key():
    banner("1. API KEY")
    if not KEY:
        print("✗ No key found.")
        print("  Expected in backend/.env (the canonical location):")
        from app.config import env_file_status
        for f in env_file_status():
            mark = "✓ found  " if f["exists"] else "· missing"
            print(f"     {mark} {f['path']}")
        print("\n  Add this to backend/.env:")
        print("     GEMINI_API_KEY=your_key_here")
        print("     LLM_PROVIDER=gemini")
        print("  Get a free key at https://aistudio.google.com/apikey")
        return False
    masked = f"{KEY[:6]}...{KEY[-4:]}" if len(KEY) > 12 else "***"
    print(f"✓ Key present ({masked})")
    print(f"  provider={settings.LLM_PROVIDER or 'none'}  model={settings.LLM_MODEL or '(default)'}")
    return True


def check_embeddings():
    banner(f"2. EMBEDDINGS ({EMB_MODEL})")
    texts = [
        "The accused transferred 45000 rupees using a spoofed UPI handle.",
        "A payment of Rs 45,000 was made through a fraudulent UPI identifier.",
        "The weather in Delhi is pleasant this week.",
    ]
    url = f"{BASE}/models/{EMB_MODEL}:batchEmbedContents"
    last_error = None
    resp = None
    for attempt in range(3):
        try:
            resp = httpx.post(
                url,
                json={"requests": [
                    {"model": f"models/{EMB_MODEL}", "content": {"parts": [{"text": t}]}}
                    for t in texts
                ]},
                headers={"x-goog-api-key": KEY, "Content-Type": "application/json"},
                timeout=45,
            )
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            resp = None
            time.sleep(1.5 * (attempt + 1))
            continue
        if resp.status_code == 200:
            break
        last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
        if resp.status_code in (429, 500, 502, 503, 504):
            print(f"  · attempt {attempt + 1}/3 failed ({resp.status_code}) — retrying")
            time.sleep(1.5 * (attempt + 1))
            continue
        break

    try:
        if resp is None:
            raise RuntimeError(last_error or "no response")
        if resp.status_code != 200:
            print(f"✗ {last_error}")
            print("  (The app falls back to offline hash vectors automatically, "
                  "so search still works — just without true semantics.)")
            return False
        t0 = time.time()
        embs = resp.json().get("embeddings") or []
        dt = (time.time() - t0) * 1000
        if len(embs) != len(texts):
            print(f"✗ Expected {len(texts)} embeddings, got {len(embs)}")
            return False
        dim = len(embs[0].get("values") or [])
        print(f"✓ {len(embs)} embeddings, dim={dim}, {dt:.0f} ms")

        def cos(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            na = sum(x * x for x in a) ** 0.5
            nb = sum(y * y for y in b) ** 0.5
            return dot / (na * nb) if na and nb else 0.0

        sim = cos(embs[0]["values"], embs[1]["values"])
        unrel = cos(embs[0]["values"], embs[2]["values"])
        print(f"  similar pair   : {sim:.4f}")
        print(f"  unrelated pair : {unrel:.4f}")
        if sim > unrel:
            print("✓ Semantic similarity behaves correctly")
        else:
            print("⚠ Similarity did not order as expected (still usable)")
        return True
    except Exception as exc:
        print(f"✗ {type(exc).__name__}: {exc}")
        return False


def check_generation():
    banner(f"3. GENERATION (configured: {MODEL})")
    system = ("You are the LexSecure Investigative Assistant. Answer using ONLY the "
              "provided context and cite sources as [Document Title vN].")
    user = ("EVIDENCE CONTEXT:\n[Forensic Report v1]: A SIM swap was registered against the "
            "complainant's number from a different telecom circle.\n\n"
            "OFFICER'S QUESTION: What was found regarding the SIM swap?")

    candidates = [MODEL] + [m for m in live_models() if m != MODEL]
    errors = []
    for model in candidates[:6]:
        url = f"{BASE}/models/{model}:generateContent"
        try:
            t0 = time.time()
            body = {
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "systemInstruction": {"parts": [{"text": system}]},
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048,
                                     "thinkingConfig": {"thinkingBudget": 0}},
            }
            resp = httpx.post(url, json=body,
                              headers={"x-goog-api-key": KEY, "Content-Type": "application/json"},
                              timeout=45)

            if resp.status_code == 400 and "thinking" in resp.text.lower():
                body["generationConfig"].pop("thinkingConfig", None)
                resp = httpx.post(url, json=body,
                                  headers={"x-goog-api-key": KEY, "Content-Type": "application/json"},
                                  timeout=45)

            dt = (time.time() - t0) * 1000
            if resp.status_code != 200:
                msg = resp.json().get("error", {}).get("message", "")[:90]
                errors.append(f"{model}: HTTP {resp.status_code} — {msg}")
                if resp.status_code == 404:
                    print(f"  · {model}: retired (404) — trying next live model")
                else:
                    print(f"  · {model}: HTTP {resp.status_code} — trying next live model")
                continue

            data = resp.json() or {}
            cands = data.get("candidates") or []
            if not cands:
                errors.append(f"{model}: no candidates")
                continue
            parts = (cands[0].get("content") or {}).get("parts") or []
            text = "".join(p.get("text", "") for p in parts)
            if not text.strip():
                errors.append(f"{model}: empty answer (finishReason={cands[0].get('finishReason')})")
                print(f"  · {model}: empty answer — trying next live model")
                continue
            print(f"✓ Answer via '{model}' in {dt:.0f} ms:\n---\n{text.strip()[:500]}\n---")
            if model != MODEL:
                print(f"\n  → Note: '{MODEL}' is unusable right now. Set LLM_MODEL={model} in backend/.env")
            return True
        except Exception as exc:
            errors.append(f"{model}: {type(exc).__name__}")
            print(f"  · {model}: {type(exc).__name__} — trying next live model")

    print("✗ No model produced an answer:")
    for e in errors:
        print(f"    - {e}")
    return False


def scan_models():
    """Test every text-chat model for this key and report which ones work."""
    banner("MODEL SCAN (free-tier availability)")
    models = live_models()
    if not models:
        print("✗ Could not list models for this key.")
        return 1
    print(f"  {len(models)} text-chat model(s) visible to this key\n")
    print("  (probing with a delay — the free tier allows only a few requests per minute)\n")
    working = []
    for m in models:
        url = f"{BASE}/models/{m}:generateContent"
        try:
            t0 = time.time()
            body = {
                "contents": [{"role": "user", "parts": [{"text": "Reply OK"}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048},
            }
            resp = httpx.post(url, json=body,
                              headers={"x-goog-api-key": KEY, "Content-Type": "application/json"},
                              timeout=40)
            dt = (time.time() - t0) * 1000
            if resp.status_code == 200:
                print(f"  ✓ {m:24s} {dt:6.0f}ms  works")
                working.append(m)
            else:
                msg = resp.json().get("error", {}).get("message", "")[:46]
                print(f"  ✗ {m:24s} {dt:6.0f}ms  HTTP {resp.status_code}: {msg}")
        except Exception as exc:
            print(f"  ✗ {m:24s} {type(exc).__name__}")
        time.sleep(_SCAN_DELAY_SECONDS)

    banner("RESULT")
    if working:
        print(f"✓ {len(working)} model(s) currently work: {', '.join(working)}")
        print("\n  Paste this into backend/.env to pin them:")
        print(f"     LLM_MODEL={working[0]}")
        print(f"     GEMINI_MODELS={','.join(working)}")
        return 0
    print("✗ No model answered right now (quota exhausted or key invalid).")
    print("  Enable billing at https://aistudio.google.com/apikey or wait for the quota window.")
    return 1


def main() -> int:
    print("LexSecure · Google Gemini connectivity check")
    if "--scan" in sys.argv:
        if not check_key():
            return 1
        return scan_models()
    if not check_key():
        print("\nRESULT: NOT CONFIGURED — the app will use the offline template engine.")
        return 1
    ok_emb = check_embeddings()
    ok_gen = check_generation()
    banner("RESULT")
    if ok_emb and ok_gen:
        print("✓ Gemini fully working. Uncomment these in backend/.env:")
        print("    LLM_PROVIDER=gemini")
        print("    LLM_MODEL=" + MODEL)
        print("    GEMINI_API_KEY=<your key>")
        print("    EMBEDDING_PROVIDER=gemini")
        print("    EMBEDDING_MODEL=" + EMB_MODEL)
        print("  then restart the backend (./start.sh).")
        return 0
    print("✗ Some checks failed — see the messages above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
