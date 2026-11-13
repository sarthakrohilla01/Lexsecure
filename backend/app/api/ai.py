"""AI Search & Permission-Aware RAG API"""

from typing import List, Dict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.schemas.ai import SearchQueryRequest, SearchResultItem, RAGQueryRequest, RAGResponse
from app.security.abac import get_current_user
from app.ai.vector_store import search_authorized_chunks
from app.ai.rag_engine import generate_rag_response
from app.ai import llm as llm_adapter
from app.audit.logger import record_audit_event
from app.config import settings

router = APIRouter(prefix="/ai", tags=["AI & Vector Search"])

@router.get("/status")
def get_ai_status():
    """Reports how the AI features actually operate, so the UI can label deterministic vs LLM-backed mode honestly (no overclaiming)."""
    from app.ai.embeddings import embedding_space_id

    llm_ready = llm_adapter.llm_configured()
    provider = settings.LLM_PROVIDER.strip().lower()
    space = embedding_space_id()
    gemini_embeddings = space.startswith("gemini:")
    nara_embeddings = space.startswith("nara:")

    if provider == "nara":
        allowed = llm_adapter.nara_models()
    elif provider == "gemini":
        allowed = llm_adapter.allowed_models()
    else:
        allowed = []

    last_error = llm_adapter.llm_last_error()
    if llm_ready and last_error:
        note = (
            f"{provider} is configured ({llm_adapter.active_model()}), but the last "
            f"provider call failed: {last_error['reason']} Answers fall back to the "
            "deterministic template until it recovers — retrieval stays inside the "
            "authorized corpus."
        )
    elif llm_ready:
        note = (
            f"Real LLM answer synthesis enabled ({provider}"
            f"/{llm_adapter.active_model()}); retrieval stays inside the "
            "authorized corpus."
        )
    else:
        reason = llm_adapter.llm_missing_reason()
        note = (
            f"{reason} Falling back to deterministic template synthesis."
            if reason else
            "Deterministic mode: retrieval is a real vector search over authorized "
            "documents; answer synthesis uses the local template."
        )

    return {
        "generation_mode": "llm" if llm_ready else "deterministic-template",
        "llm_provider": provider or None,
        "llm_model": llm_adapter.active_model() if provider else None,
        "llm_configured_model": llm_adapter._resolved_model() if provider else None,
        "llm_allowed_models": allowed,
        "llm_ready": llm_ready,
        "llm_missing_reason": llm_adapter.llm_missing_reason(),
        "llm_last_error": llm_adapter.llm_last_error(),
        "quota_exhausted": llm_adapter.quota_state(),
        "embedding_provider": ("gemini" if gemini_embeddings
                               else "nara" if nara_embeddings else "local"),
        "embedding_model": (settings.EMBEDDING_MODEL if gemini_embeddings
                            else settings.NARA_EMBEDDING_MODEL if nara_embeddings
                            else None),
        "embedding_space": space,
        "vector_store": "local cosine-similarity index",
        "abac_filtering": "applied BEFORE retrieval — unauthorized chunks never reach ranking or generation",
        "environment": (settings.ENVIRONMENT or "development").strip().lower(),
        "note": note,
    }

@router.post("/search", response_model=List[SearchResultItem])
def semantic_search(
    payload: SearchQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Executes semantic vector search strictly filtered by user's ABAC authorization. Unauthorized case documents are pruned before vector similarity calculation."""
    results = search_authorized_chunks(
        db=db,
        user=current_user,
        query=payload.query,
        case_id_filter=payload.case_id,
        doc_type_filter=payload.document_type,
        limit=payload.limit or 8
    )

    record_audit_event(
        db=db,
        action="AI_SEMANTIC_SEARCH",
        details=f"Query: '{payload.query}' (Found {len(results)} authorized matches)",
        user=current_user,
        status="SUCCESS"
    )

    return results

@router.post("/ask", response_model=RAGResponse)
def ask_ai_assistant(
    payload: RAGQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """RAG Document Q&A Assistant: Retrieves authorized evidence chunks and synthesizes source-grounded answers. Answers include transparent source citations with document name and version."""
    response_data = generate_rag_response(
        db=db,
        user=current_user,
        question=payload.question,
        case_id_filter=payload.case_id
    )

    response_data.setdefault("llm_error", llm_adapter.llm_last_error())

    record_audit_event(
        db=db,
        action="AI_RAG_QUERY",
        details=(
            f"Question: '{payload.question[:80]}' (Status: {response_data['status']}"
            + (f", LLM: {response_data.get('model')}" if not response_data.get("llm_error")
               else f", LLM FAILED: {response_data['llm_error'].get('reason')}")
            + ")"
        ),
        user=current_user,
        status="SUCCESS" if response_data["status"] == "SUCCESS" and not response_data.get("llm_error") else "WARNING"
    )

    return response_data

@router.get("/suggested-prompts")
def get_suggested_prompts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns starter questions derived from the cases this officer is actually authorized to see. Nothing is hard-coded: the prompts reflect real assigned cases, so the assistant never advertises documents the officer cannot open."""
    from app.security.abac import get_authorized_case_ids
    from app.models.case import Case

    case_ids = list(get_authorized_case_ids(current_user, db) or [])
    if not case_ids:
        return []

    cases = (
        db.query(Case)
        .filter(Case.id.in_(case_ids))
        .order_by(Case.created_at.desc())
        .limit(3)
        .all()
    )
    prompts: List[Dict[str, str]] = []
    for case in cases:
        prompts.append({
            "prompt": f"Summarize the latest findings in {case.id}.",
            "case_id": case.id,
        })
    for case in cases[:2]:
        prompts.append({
            "prompt": f"What evidence has been collected so far in {case.id}?",
            "case_id": case.id,
        })
    return prompts[:5]
