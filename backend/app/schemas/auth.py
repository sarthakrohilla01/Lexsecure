"""Authentication Schemas"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str
    mfa_code: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: Optional[str] = None
    token_type: str = "bearer"
    mfa_verified: bool = False
    mfa_enrollment_required: bool = False
    enrollment_token: Optional[str] = None
    user: dict


class MfaCodeRequest(BaseModel):
    code: str


class MfaDisableRequest(BaseModel):
    password: str
    code: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str
    department: str
    badge_number: Optional[str] = None
    mfa_enabled: bool
    is_active: bool = True
    is_temporary: bool = False
    expires_at: Optional[datetime] = None
    public_key_pem: Optional[str] = None
