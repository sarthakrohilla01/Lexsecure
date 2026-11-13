"""NaraRouter Connectivity Checker"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

from app.config import settings

BASE = (settings.NARA_BASE_URL or "https://router.bynara.id/v1").rstrip("/")
KEY = (settings.NARA_API_KEY or settings.LLM_API_KEY or "").strip()
MODEL = settings.LLM_MODEL.strip() or "agnes-2.5-flash"
FAILOVER = [m.strip() for m in (settings.NARA_MODELS or "").split(",") if m.strip()]

FREE_MODELS = [
    "agnes-2.5-flash",
]

HEADERS = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

LAST_ERROR = {"detail": ""}


def banner(text: str):
    print(f"\n=== {text} ===")


def router_error(resp) -> str:
    """Reads the router's error envelope: {"error": {"type","message"}}."""
    try:
        err = (resp.json() or {}).get("error") or {}
        return f"{err.get('type', 'error')}: {err.get('message', '')}".strip()
    except Exception:
        return resp.text[:160]


def check_key():
    banner("1. API KEY")
    if not KEY:
        print("✗ No key found. Set NARA_API_KEY in backend/.env")
        print("  Issue a key at https://router.bynara.id (keys start with 'sk-nry-')")
        print("  and bind your Telegram account at https://router.bynara.id/settings")
        return False
    masked = f"{KEY[:9]}...{KEY[-4:]}" if len(KEY) > 14 else "***"
    print(f"✓ Key present ({masked})")
    print(f"  base URL: {BASE}")
    print(f"  model   : {MODEL}")
    return True

def list_models():
    """GET /v1/models (authenticated)."""
    try:
        r = httpx.get(f"{BASE}/models", headers=HEADERS, timeout=30)
    except Exception as exc:
        print(f"✗ {type(exc).__name__}: {exc}")
        return None
    if r.status_code != 200:
        print(f"✗ HTTP {r.status_code}: {router_error(r)}")
        return None
    data = r.json() or {}
    rows = data.get("data") or []
    models = [m.get("id") for m in rows if isinstance(m, dict) and m.get("id")]
    print(f"✓ {len(models)} model(s) available to this key")
    return models


def check_models_listed():
    banner("2. MODEL CATALOG")
    models = list_models()
    if models is None:
        return False
    for m in models[:40]:
        mark = "→" if m in (FAILOVER + [MODEL]) else " "
        print(f"  {mark} {m}")
    missing = [m for m in (FAILOVER + [MODEL]) if m and m not in models]
    if missing:
        print(f"\n  ⚠ configured but not visible to this key: {', '.join(missing)}")
        print("    (they may still work — the catalog only lists live models)")
    return True


def check_free_models() -> bool:
    """Quick probe of every free-tier model; prints the first one that works."""
    banner("2b. FREE-TIER MODELS")
    working = []
    for m in FREE_MODELS:
        try:
            r = httpx.post(
                f"{BASE}/chat/completions",
                json={"model": m,
                      "messages": [{"role": "user", "content": "Reply with the single word: OK"}],
                      "max_tokens": 8, "stream": False},
                headers=HEADERS, timeout=45)
            if r.status_code == 200:
                print(f"  ✓ {m}")
                working.append(m)
            else:
                print(f"  ✗ {m} — HTTP {r.status_code}: {router_error(r)[:90]}")
        except Exception as exc:
            print(f"  ✗ {m} — {type(exc).__name__}")
    if working:
        print(f"\n  → use LLM_MODEL={working[0]}")
    return bool(working)


def check_chat(model: str = None) -> bool:
    banner(f"3. CHAT COMPLETION ({model or MODEL})")
    target = model or MODEL
    LAST_ERROR["detail"] = ""
    body = {
        "model": target,
        "messages": [
            {"role": "system", "content": "Answer concisely and only from the provided context."},
            {"role": "user", "content": "EVIDENCE CONTEXT: A SIM swap was registered against the "
                                        "complainant's number from a different telecom circle.\n\n"
                                        "QUESTION: What was found? Cite the source."},
        ],
        "max_tokens": 256,
        "temperature": 0.2,
        "stream": False,
    }
    try:
        t0 = time.time()
        r = httpx.post(f"{BASE}/chat/completions", json=body, headers=HEADERS, timeout=60)
        dt = (time.time() - t0) * 1000
        if r.status_code != 200:
            detail = router_error(r)
            LAST_ERROR["detail"] = detail
            print(f"✗ HTTP {r.status_code}: {detail}")
            if "telegram" in detail.lower():
                if "group" in detail.lower() or "channel" in detail.lower() or "relink" in detail.lower():
                    print("\n  → ACTION NEEDED: your Telegram link is incomplete.")
                    print("    1. Join the required Telegram group/channel (link is shown")
                    print("       on your NaraRouter dashboard).")
                    print("    2. Relink your account at https://router.bynara.id/settings")
                else:
                    print("\n  → ACTION NEEDED: bind your Telegram account at")
                    print("    https://router.bynara.id/settings")
                print("    Then re-run this check.")
            return False
        data = r.json() or {}
        choices = data.get("choices") or []
        if not choices:
            print(f"✗ No choices: {str(data)[:200]}")
            return False
        text = (choices[0].get("message") or {}).get("content") or ""
        usage = data.get("usage") or {}
        print(f"✓ Answer via '{target}' in {dt:.0f} ms")
        if usage:
            print(f"  tokens: prompt={usage.get('prompt_tokens')} completion={usage.get('completion_tokens')}")
        print(f"---\n{text.strip()[:500]}\n---")
        return True
    except Exception as exc:
        print(f"✗ {type(exc).__name__}: {exc}")
        return False


def main() -> int:
    print("LexSecure · NaraRouter connectivity check")
    if not check_key():
        print("\nRESULT: NOT CONFIGURED — the app will use the offline template engine.")
        return 1

    if "--models" in sys.argv:
        check_models_listed()
        return 0

    ok_models = check_models_listed()

    candidates = []
    for c in [MODEL] + FAILOVER:
        if c and c not in candidates:
            candidates.append(c)

    ok_chat = False
    gated = False
    for candidate in candidates:
        if check_chat(candidate):
            ok_chat = True
            break
        if "telegram" in LAST_ERROR["detail"].lower():
            gated = True
            print("\n  · every model is blocked by the same account gate — stopping.")
            break
        print(f"  · '{candidate}' unavailable — trying the next configured model")

    if not ok_chat and gated:
        check_free_models()

    banner("RESULT")
    if ok_chat and ok_models:
        print("✓ NaraRouter fully working. Configure in backend/.env:")
        print("    LLM_PROVIDER=nara")
        print(f"    LLM_MODEL={MODEL}")
        print("    NARA_API_KEY=sk-nry-...")
        print("    NARA_BASE_URL=https://router.bynara.id/v1")
        print("  then restart the backend (./start.sh).")
        return 0
    if gated:
        print("✗ Blocked by NaraRouter onboarding, not by our code.")
        print("  Complete the Telegram steps above (join the group/channel + relink),")
        print("  then re-run: backend/venv/bin/python backend/scripts/check_nara.py")
        return 1
    print("✗ NaraRouter is not usable yet — see the messages above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
