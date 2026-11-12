"""Workflow & Collaboration Schemas"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class WorkflowActionRequest(BaseModel):
    task_id: Optional[int] = None
    document_id: int
    action: str
    notes: Optional[str] = None

class CommentCreate(BaseModel):
    document_id: int
    content: str

class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    user_name: str
    user_role: str
    content: str
    created_at: datetime
