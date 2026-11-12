"""Audit Logging Service"""

from typing import Optional
from sqlalchemy.orm import Session
from app.models.audit import AuditLog
from app.models.user import User
from app.utils.time import utcnow

def record_audit_event(
    db: Session,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    details: Optional[str] = None,
    user: Optional[User] = None,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    user_role: Optional[str] = None,
    ip_address: str = "127.0.0.1",
    status: str = "SUCCESS"
) -> AuditLog:
    """Creates and commits an immutable audit trail entry."""
    if user:
        u_id = user.id
        u_email = user.email
        u_role = user.role.value
    else:
        u_id = user_id
        u_email = user_email or "system@ncrb.gov.in"
        u_role = user_role or "SYSTEM"

    audit_entry = AuditLog(
        timestamp=utcnow(),
        user_id=u_id,
        user_email=u_email,
        user_role=u_role,
        ip_address=ip_address,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        details=details,
        status=status
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(audit_entry)
    return audit_entry
