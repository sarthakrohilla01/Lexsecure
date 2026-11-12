"""Permission-aware chunk search."""

import json
import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.embedding import DocumentChunk
from app.models.document import Document
from app.models.user import User
from app.security.abac import get_authorized_case_ids
from app.ai.embeddings import (
    LOCAL_SPACE_ID,
    embedding_space_id,
    generate_text_embedding,
    generate_text_embeddings,
    cosine_similarity,
)


def _encode_vector(vector: List[float], space: str) -> str:
    return json.dumps({"space": space, "vector": vector})


def _decode_vector(raw_json: str) -> Tuple[str, List[float]]:
    """Legacy rows hold a bare list and are treated as local space."""
    try:
        raw = json.loads(raw_json)
    except Exception:
        return LOCAL_SPACE_ID, []
    if isinstance(raw, dict) and "vector" in raw:
        return raw.get("space") or LOCAL_SPACE_ID, raw.get("vector") or []
    if isinstance(raw, list):
        return LOCAL_SPACE_ID, raw
    return LOCAL_SPACE_ID, []


def index_document_chunks(
    db: Session,
    document_id: int,
    version_number: int,
    case_id: str,
    text: str
) -> int:
    db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id,
        DocumentChunk.version_number == version_number
    ).delete()

    paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 20]
    if not paragraphs:
        paragraphs = [text.strip()] if text.strip() else ["No text content."]

    paragraphs = paragraphs[:30]

    space = embedding_space_id()
    vectors = generate_text_embeddings(paragraphs)

    count = 0
    for idx, (para, vec) in enumerate(zip(paragraphs, vectors)):
        chunk = DocumentChunk(
            document_id=document_id,
            version_number=version_number,
            case_id=case_id,
            chunk_index=idx,
            content=para,
            vector_json=_encode_vector(vec, space)
        )
        db.add(chunk)
        count += 1

    db.commit()
    return count


def _stem(word: str) -> str:
    """Very small suffix stripper, enough to match plural/inflected forms."""
    w = word
    if w.endswith("ies") and len(w) > 4:
        w = w[:-3] + "y"
    elif w.endswith("s") and not w.endswith("ss") and len(w) > 4:
        w = w[:-1]
    if w.endswith("ing") and len(w) > 6:
        w = w[:-3]
    elif w.endswith("ed") and len(w) > 5:
        w = w[:-2]
    return w


def _terms(text: str) -> List[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower())]


_QUERY_STOPWORDS = {
    "what", "when", "where", "which", "who", "whom", "whose", "why", "how",
    "was", "were", "been", "being", "did", "does", "done", "has", "have",
    "had", "the", "and", "for", "with", "from", "into", "about", "that",
    "this", "these", "those", "there", "their", "them", "then", "than",
    "are", "our", "you", "your", "his", "her", "its", "not", "any", "all",
    "can", "could", "should", "would", "will", "shall", "may", "might",
    "tell", "show", "give", "list", "please", "case", "document", "documents",
}


def search_authorized_chunks(
    db: Session,
    user: User,
    query: str,
    case_id_filter: Optional[str] = None,
    doc_type_filter: Optional[str] = None,
    limit: int = 8
) -> List[Dict[str, Any]]:
    """Rank chunks from authorized cases only; returns [] if none are visible."""
    authorized_case_ids = get_authorized_case_ids(user, db)
    if not authorized_case_ids:
        return []

    if case_id_filter:
        if case_id_filter not in authorized_case_ids:
            return []
        target_case_ids = [case_id_filter]
    else:
        target_case_ids = authorized_case_ids

    query_base = db.query(DocumentChunk, Document).join(
        Document, DocumentChunk.document_id == Document.id
    ).filter(DocumentChunk.case_id.in_(target_case_ids))

    if doc_type_filter:
        query_base = query_base.filter(Document.document_type == doc_type_filter)

    records = query_base.all()
    if not records:
        return []

    current_space = embedding_space_id()
    query_vec = generate_text_embedding(query)

    chunk_vecs: List[List[float]] = []
    mismatch_positions: List[int] = []
    for i, (chunk, _doc) in enumerate(records):
        space, vec = _decode_vector(chunk.vector_json)
        chunk_vecs.append(vec)
        if space != current_space:
            mismatch_positions.append(i)

    if mismatch_positions:
        texts = [records[i][0].content for i in mismatch_positions]
        new_vecs = generate_text_embeddings(texts)
        for pos, vec in zip(mismatch_positions, new_vecs):
            chunk_vecs[pos] = vec

    ranked_results = []
    total_chunks = max(1, len(records))
    doc_freq: Counter = Counter()
    for chunk, _doc in records:
        for term in set(_terms(chunk.content)):
            doc_freq[term] += 1

    for i, (chunk, doc) in enumerate(records):
        if doc.classification == "SECRET" and user.role.value not in ["ADMINISTRATOR", "SUPERVISOR"]:
            continue

        sim = cosine_similarity(query_vec, chunk_vecs[i]) if chunk_vecs[i] else 0.0

        q_terms = {
            _stem(w) for w in re.findall(r"[a-z0-9]+", query.lower())
            if len(w) > 3 and w not in _QUERY_STOPWORDS
        }
        kw_boost = 0.0
        if q_terms:
            hay_terms = _terms(f"{chunk.content} {doc.document_type} {doc.case_id}")
            tf = Counter(hay_terms)
            for term in q_terms:
                n = tf.get(term, 0)
                if n:
                    idf = math.log(1 + total_chunks / (1 + doc_freq.get(term, 0)))
                    kw_boost += min(idf, 2.5) * 0.12 * (1 + 0.15 * min(n - 1, 3))
            title_terms = set(_terms(doc.title)) & q_terms
            kw_boost += 0.20 * len(title_terms)

        final_score = round(min(1.0, sim + kw_boost), 4)
        if final_score > 0.05 or kw_boost > 0:
            ranked_results.append({
                "document_id": doc.id,
                "document_title": doc.title,
                "document_type": doc.document_type,
                "case_id": doc.case_id,
                "classification": doc.classification,
                "version_number": chunk.version_number,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "score": final_score,
                "access_status": "AUTHORIZED"
            })

    ranked_results.sort(key=lambda x: x["score"], reverse=True)

    deduped: List[Dict[str, Any]] = []
    seen_content = set()
    for item in ranked_results:
        key = re.sub(r"\W+", " ", item["content"].lower()).strip()[:240]
        if key in seen_content:
            continue
        seen_content.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped
