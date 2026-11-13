
import re
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.user import User
from app.ai.vector_store import search_authorized_chunks
from app.ai import llm as llm_adapter
from app.security.abac import get_authorized_case_ids

_MODEL = "LexSecure Deterministic RAG Engine"

_GREETINGS = {
    "hi", "hii", "hiii", "hello", "hey", "namaste", "good morning",
    "good afternoon", "good evening", "yo", "hola", "greetings",
    "how are you", "how r u", "what's up", "whats up", "sup",
}
_FAREWELLS = {"bye", "goodbye", "good night", "see you", "thanks bye"}
_THANKS = {"thanks", "thank you", "thankyou", "thx", "shukriya", "dhanyavad"}
_IDENTITY = {
    "who are you", "what are you", "your name", "about yourself",
    "introduce yourself", "what is lexsecure", "what is this system",
}
_HELP = {
    "help", "what can you do", "how do i use", "how to use",
    "capabilities", "what do you do", "commands", "options",
}

def _normalize(text: str) -> str:
    t = text.lower().strip()
    t = re.sub(r"[!.,?;:…]+$", "", t).strip()
    return t

def _handle_conversational(question: str, user: User) -> Optional[Dict[str, Any]]:

    q = _normalize(question)
    first_name = (user.full_name or "Officer").split()[0]

    if q in _GREETINGS:
        return {
            "answer": (
                f"Hello {first_name}. I am the LexSecure Investigative Assistant — "
                f"your secure, permission-aware aide for case evidence.\n\n"
                f"You can ask me to:\n"
                f"- **Summarize findings** for a case you are assigned to\n"
                f"- **Recall witness statements** and correlate exhibits\n"
                f"- **List the charges** framed in a charge sheet\n\n"
                f"Every answer cites its evidentiary sources, and I can only see "
                f"documents within your clearance.\n\n"
                f"How can I assist your investigation today?"
            ),
            "sources": [],
            "status": "SUCCESS",
            "model": _MODEL,
        }
    if q in _FAREWELLS:
        return {
            "answer": (
                f"Goodbye {first_name}. Your session activity has been logged to the audit trail. "
                f"Stay vigilant, Officer."
            ),
            "sources": [],
            "status": "SUCCESS",
            "model": _MODEL,
        }
    if q in _THANKS:
        return {
            "answer": (
                f"You are welcome, {first_name}. If you need case summaries, evidence "
                f"correlation, or charge-sheet details, just ask."
            ),
            "sources": [],
            "status": "SUCCESS",
            "model": _MODEL,
        }
    if q in _IDENTITY:
        return {
            "answer": (
                "I am the **LexSecure Investigative Assistant**, a retrieval-augmented "
                "AI operating strictly inside this agency's evidence repository.\n\n"
                "- I answer **only** from documents you are authorized to view (ABAC-enforced).\n"
                "- Every factual claim carries **source citations** (document + version).\n"
                "- I cannot access the internet or any data outside this system.\n\n"
                "Ask me to summarize evidence, recall testimony, explain charges, or "
                "correlate exhibits for any case you are assigned to."
            ),
            "sources": [],
            "status": "SUCCESS",
            "model": _MODEL,
        }
    if q in _HELP or q.startswith("help "):
        return {
            "answer": (
                f"Here is what I can do for you, {first_name}:\n\n"
                f"- **Summarize evidence** — forensic findings, investigation reports, exhibit lists.\n"
                f"- **Recall testimony** — what a witness stated, and when.\n"
                f"- **Explain charges** — the sections invoked and the supporting evidence.\n"
                f"- **Correlate exhibits** — link a suspect, device or account to an act.\n\n"
                f"I stay silent on cases outside your assignment — that is a "
                f"security boundary, not a gap in knowledge."
            ),
            "sources": [],
            "status": "SUCCESS",
            "model": _MODEL,
        }
    return None

def generate_rag_response(
    db: Session,
    user: User,
    question: str,
    case_id_filter: Optional[str] = None
) -> Dict[str, Any]:
    small_talk = _handle_conversational(question, user)
    if small_talk is not None:
        return small_talk

    authorized_case_ids = get_authorized_case_ids(user, db)
    if case_id_filter and case_id_filter not in authorized_case_ids:
        return {
            "answer": f"Access Denied: Officer {user.email} does not have security clearance or assignment for case {case_id_filter}.",
            "sources": [],
            "status": "DENIED",
            "model": "LexSecure RBAC/ABAC Security Filter"
        }

    chunks = search_authorized_chunks(
        db=db,
        user=user,
        query=question,
        case_id_filter=case_id_filter,
        limit=5
    )

    if not chunks:
        return {
            "answer": (
                "I could not find matching evidence within the documents you are "
                "authorized to view.\n\n"
                "- Try rephrasing with case-specific terms (exhibit names, sections "
                "of law, or officer observations).\n"
                "- If the record exists in a case outside your assignment, I am "
                "not permitted to disclose it — please contact your supervising officer."
            ),
            "sources": [],
            "status": "NO_RECORDS",
            "model": "LexSecure Retrieval Assistant (deterministic)"
        }

    sources = []
    seen_docs = set()
    context_passages = []

    for c in chunks:
        doc_key = f"{c['document_title']} (v{c['version_number']})"
        if doc_key not in seen_docs:
            seen_docs.add(doc_key)
            sources.append({
                "document_id": c["document_id"],
                "document_title": c["document_title"],
                "document_type": c["document_type"],
                "version_number": c["version_number"],
                "case_id": c["case_id"],
                "classification": c["classification"],
                "snippet": c["content"][:240] + ("..." if len(c["content"]) > 240 else "")
            })
        context_passages.append(f"[{c['document_title']} v{c['version_number']}]: {c['content']}")

    llm_answer = llm_adapter.generate_answer(question, context_passages)
    if llm_answer:
        cited = [
            s for s in sources
            if f"[{s['document_title']} v{s['version_number']}]".lower()
            in llm_answer.lower()
        ]
        return {
            "answer": llm_answer,
            "sources": cited or sources,
            "status": "SUCCESS",
            "model": (
                f"LexSecure RAG + {llm_adapter._resolved_provider()}"
                f"/{llm_adapter.active_model()} (retrieval: local vector index)"
            ),
            "llm_error": None,
        }

    llm_error = llm_adapter.llm_last_error()

    lead_source = sources[0]

    query_terms = {
        w.lower().strip(".,;:()[]{}\"'") for w in question.split() if len(w) > 3
    }
    _DISCLAIMER = re.compile(
        r"\b(synthetic demo|no real personal data|page \d+ of \d+|lorem ipsum)\b", re.I)

    def _clean(passage: str):
        """Splits '[Doc vN]: body' and unwraps hard line breaks / bullets."""
        label, _, body = passage.partition("]: ")
        cite = (label + "]") if label.startswith("[") else ""
        text = body or passage
        text = re.sub(r"(?m)^[ \t]*[*\-\u2022][ \t]+", "", text)
        text = re.sub(r"[ \t]*\n[ \t]*", " ", text)
        return cite, " ".join(text.split())

    candidates = []
    for passage in context_passages[:4]:
        cite, body = _clean(passage)
        for raw in re.split(r"(?<=[.!?])\s+", body):
            s = raw.strip()
            if len(s) < 60 or len(s.split()) < 10:
                continue
            if not s.endswith((".", "!", "?")):
                continue
            letters = [c for c in s if c.isalpha()]
            if letters and sum(c.isupper() for c in letters) / len(letters) > 0.6:
                continue
            if "---" in s or s.count("|") >= 2:
                continue
            words = s.split()
            if sum(1 for w in words if w.isupper() and len(w) > 2) / max(1, len(words)) > 0.2:
                continue
            if _DISCLAIMER.search(s) or s.startswith("["):
                continue
            candidates.append((s, cite))

    def relevance(item) -> int:
        low = item[0].lower()
        hits = sum(1 for t in query_terms if t in low)
        readable = 1 if 80 <= len(item[0]) <= 320 else 0
        return hits * 3 + readable

    picked, seen = [], set()
    for sentence, cite in sorted(candidates, key=relevance, reverse=True):
        if sentence in seen:
            continue
        seen.add(sentence)
        picked.append((sentence, cite))
        if len(picked) == 4:
            break
    picked.sort(key=lambda item: candidates.index(item))

    def _as_bullet(sentence: str, cite: str) -> str:
        """Promotes an existing 'Label: value' sentence into a bold lead-in."""
        m = re.match(r"^([A-Z][^:]{2,40}):\s+(.+)$", sentence)
        text = f"**{m.group(1)}:** {m.group(2)}" if m else sentence
        return f"{text} {cite}".strip()

    if picked:
        bullets = "\n".join(f"- {_as_bullet(s, c)}" for s, c in picked)
    else:
        bullets = f"- {' '.join(_clean(context_passages[0])[1].split())[:300]}"

    cited_docs = {entry for entry in (cite for _, cite in picked) if entry}
    if len(cited_docs) == 1 and picked:
        cite = next(iter(cited_docs))
        doc = next((s for s in sources
                    if f"[{s['document_title']} v{s['version_number']}]" == cite),
                   lead_source)
        header = (f"**Case {doc['case_id']}** — "
                  f"{doc['document_title']} (v{doc['version_number']})")
    else:
        case_ids = sorted({c["case_id"] for c in chunks})
        cases_label = ", ".join(case_ids[:3]) + ("…" if len(case_ids) > 3 else "")
        count = max(len(cited_docs), len(sources))
        header = (f"**{cases_label}** — deterministic summary of {count} "
                  f"authorized document{'s' if count != 1 else ''}")

    answer = (
        f"{header}\n\n"
        f"{bullets}\n\n"
        f"*Deterministic summary built from the authorized documents cited below — "
        f"the AI provider was unavailable for this request.*"
    )

    return {
        "answer": answer,
        "sources": sources,
        "status": "SUCCESS",
        "model": "LexSecure Deterministic RAG Engine",
        "llm_error": llm_error,
    }
