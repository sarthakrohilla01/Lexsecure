"""Case Management Schemas"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class CaseBase(BaseModel):
    title: str
    description: Optional[str] = None
    department: str
    status: Optional[str] = "UNDER_INVESTIGATION"
    classification: Optional[str] = "RESTRICTED"

class CaseCreate(CaseBase):
    id: str

class CaseOfficerAssignment(BaseModel):
    user_id: int
    user_name: str
    user_email: str
    user_role: str
    assignment_role: str

class CaseSummaryResponse(CaseBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    document_count: int = 0
    assigned_officers_count: int = 0
    user_is_assigned: bool = False


class CaseDetailResponse(CaseBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    assigned_officers: List[CaseOfficerAssignment] = []
