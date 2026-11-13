"""Vector Embedding Engine"""

import hashlib
import logging
import threading
from collections import OrderedDict
from typing import List, Optional, Sequence

import httpx

from app.config import settings

logger = logging.getLogger("lexsecure.embeddings")

EMBEDDING_DIM = 128
LOCAL_SPACE_ID = "local-hash-v1"

_CACHE_MAX = 2048
_cache: "OrderedDict[str, List[float]]" = OrderedDict()
_cache_lock = threading.Lock()


def _cache_key(space: str, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"{space}:{digest}"


def _cache_get(space: str, text: str) -> Optional[List[float]]:
    key = _cache_key(space, text)
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    return None


def _cache_put(space: str, text: str, vector: List[float]) -> None:
    key = _cache_key(space, text)
    with _cache_lock:
        _cache[key] = vector
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def local_text_embedding(text: str) -> List[float]:
    """Deterministic 128-dimensional dense unit vector from text. Combines n-gram subword hashing and position weighting."""
    import numpy as np

    words = text.lower().split()
    if not words:
        return [0.0] * EMBEDDING_DIM

    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    for i, word in enumerate(words):
        h = int(hashlib.md5(word.encode("utf-8"), usedforsecurity=False).hexdigest(), 16)
        idx1 = h % EMBEDDING_DIM
        idx2 = (h >> 7) % EMBEDDING_DIM
        sign = 1.0 if (h & 1) else -1.0
        weight = 1.0 / (1.0 + 0.05 * min(i, 20))
        vec[idx1] += sign * weight
        vec[idx2] += sign * 0.5 * weight

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm

    return [round(float(x), 6) for x in vec]


def _gemini_api_key() -> str:
    return (settings.GEMINI_API_KEY or settings.LLM_API_KEY or "").strip()


def _gemini_base_url() -> str:
    return (settings.LLM_BASE_URL.strip()
            or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")


def gemini_embedding_space_id() -> str:
    return f"gemini:{settings.EMBEDDING_MODEL.strip() or 'gemini-embedding-001'}"


def _gemini_batch_embed(texts: Sequence[str]) -> Optional[List[List[float]]]:
    """Calls the Gemini batchEmbedContents endpoint (one HTTP request for many texts). Returns None on any failure so callers can fall back to local."""
    if not texts:
        return []
    key = _gemini_api_key()
    if not key:
        logger.warning("Gemini embeddings requested but no GEMINI_API_KEY is set.")
        return None

    model = settings.EMBEDDING_MODEL.strip() or "gemini-embedding-001"
    url = f"{_gemini_base_url()}/models/{model}:batchEmbedContents"
    requests = [
        {"model": f"models/{model}", "content": {"parts": [{"text": t}]}}
        for t in texts
    ]
    try:
        resp = httpx.post(
            url,
            json={"requests": requests},
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        payload = resp.json() or {}
        embeddings = payload.get("embeddings") or []
        if len(embeddings) != len(texts):
            raise ValueError(
                f"Gemini returned {len(embeddings)} embeddings for {len(texts)} texts")
        return [[float(x) for x in (e.get("values") or [])] for e in embeddings]
    except Exception as exc:
        logger.warning("Gemini embedding call failed (%s); using local space.", exc)
        return None


def embedding_space_id() -> str:
    """Identifier of the embedding space currently in use. Stored alongside each chunk vector so vectors from different spaces are never compared."""
    provider = settings.EMBEDDING_PROVIDER.strip().lower()
    if provider == "gemini" and _gemini_api_key():
        return gemini_embedding_space_id()
    if provider == "nara" and settings.NARA_EMBEDDING_MODEL.strip() and _nara_api_key():
        return f"nara:{settings.NARA_EMBEDDING_MODEL.strip()}"
    return LOCAL_SPACE_ID


def _nara_api_key() -> str:
    return (settings.NARA_API_KEY or settings.LLM_API_KEY or "").strip()


def _nara_base_url() -> str:
    return (settings.NARA_BASE_URL or "https://router.bynara.id/v1").rstrip("/")


def _nara_batch_embed(texts: Sequence[str]) -> Optional[List[List[float]]]:
    """NaraRouter embeddings (OpenAI-compatible: /v1/embeddings)."""
    model = settings.NARA_EMBEDDING_MODEL.strip()
    if not model or not texts:
        return None
    key = _nara_api_key()
    if not key:
        return None
    try:
        resp = httpx.post(
            f"{_nara_base_url()}/embeddings",
            json={"model": model, "input": list(texts)},
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json() or {}
        rows = data.get("data") or []
        if len(rows) != len(texts):
            raise ValueError(f"expected {len(texts)} embeddings, got {len(rows)}")
        return [[float(x) for x in (r.get("embedding") or [])] for r in rows]
    except Exception as exc:
        logger.warning("NaraRouter embedding call failed (%s); using local space.", exc)
        return None


def generate_text_embeddings(texts: List[str]) -> List[List[float]]:
    """Batched embedding generation. Uses the Gemini space when configured and available, otherwise the offline local space. Results are cached."""
    if not texts:
        return []

    space = embedding_space_id()
    results: List[Optional[List[float]]] = [None] * len(texts)
    missing_idx: List[int] = []
    missing_texts: List[str] = []

    for i, t in enumerate(texts):
        cached = _cache_get(space, t)
        if cached is not None:
            results[i] = cached
        else:
            missing_idx.append(i)
            missing_texts.append(t)

    if missing_texts:
        vectors: Optional[List[List[float]]] = None
        if space.startswith("gemini:"):
            vectors = _gemini_batch_embed(missing_texts)
        elif space.startswith("nara:"):
            vectors = _nara_batch_embed(missing_texts)
        if vectors is None:
            vectors = [local_text_embedding(t) for t in missing_texts]
        for idx, text, vec in zip(missing_idx, missing_texts, vectors):
            _cache_put(space, text, vec)
            results[idx] = vec

    return [r if r is not None else local_text_embedding(t) for r, t in zip(results, texts)]


def generate_text_embedding(text: str) -> List[float]:
    """Single-text convenience wrapper around the batched generator."""
    return generate_text_embeddings([text])[0]


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Computes cosine similarity between two vector representations."""
    import numpy as np

    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    if a.shape != b.shape:
        return 0.0
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
