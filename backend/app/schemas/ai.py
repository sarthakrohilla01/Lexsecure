"""AI Search and RAG Schemas"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class SearchQueryRequest(BaseModel):
    query: str
    case_id: Optional[str] = None
    document_type: Optional[str] = None
    limit: Optional[int] = 8

class SearchResultItem(BaseModel):
    document_id: int
    document_title: str
    document_type: str
    case_id: str
    classification: str
    version_number: int
    content: str
    score: float
    access_status: str

class RAGQueryRequest(BaseModel):
    question: str
    case_id: Optional[str] = None

class RAGSourceItem(BaseModel):
    document_id: int
    document_title: str
    document_type: str
    version_number: int
    case_id: str
    classification: str
    snippet: str

class RAGResponse(BaseModel):
    answer: str
    sources: List[RAGSourceItem]
    status: str
    model: str
    llm_error: Optional[Dict[str, Any]] = None
