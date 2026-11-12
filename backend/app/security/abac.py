"""Attribute-Based & Role-Based Access Control (ABAC + RBAC) Policy Engine"""

from typing import List, Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.user import User, UserRole
from app.models.case import Case, CaseAssignment
from app.models.document import Document
from app.models.audit import AuditLog
from app.security.jwt import decode_access_token, is_token_revoked
from app.utils.time import utcnow

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Extracts and validates user from bearer token."""
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("scope") == "mfa_enroll":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Enrolment tokens cannot access this resource.",
        )

    if is_token_revoked(db, payload):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This session has been signed out.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    if user.expires_at and user.expires_at < utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Temporary account expired")

    return user

def require_roles(allowed_roles: List[UserRole]):
    """RBAC gatekeeper decorator/dependency."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Role '{current_user.role.value}' lacks required permissions."
            )
        return current_user
    return role_checker

def verify_case_access(
    user: User,
    case_id: str,
    db: Session,
    request: Optional[Request] = None,
    action: str = "CASE_ACCESS"
) -> Case:
    """ABAC evaluation for Case access. Admins and Supervisors have broad oversight access. Investigators, Forensic Experts, Legal Officers must be assigned to the case."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{case_id}' not found")

    if user.role in [UserRole.ADMINISTRATOR, UserRole.SUPERVISOR]:
        return case

    assignment = db.query(CaseAssignment).filter(
        CaseAssignment.case_id == case_id,
        CaseAssignment.user_id == user.id
    ).first()

    if not assignment:
        client_ip = request.client.host if request and request.client else "127.0.0.1"
        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            user_role=user.role.value,
            ip_address=client_ip,
            action="UNAUTHORIZED_ACCESS",
            target_type="CASE",
            target_id=case_id,
            details=f"User {user.email} ({user.role.value}) attempted unauthorized access to unassigned case {case_id}",
            status="BLOCKED"
        )
        db.add(audit)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access Denied: Officer {user.email} is not assigned to Case {case_id}."
        )

    return case

def verify_document_access(
    user: User,
    document: Document,
    db: Session,
    request: Optional[Request] = None
) -> bool:
    """ABAC evaluation for Document access. Evaluates: 1. Case-level authorization. 2. Document classification level vs role. 3. Workflow state (Draft documents only viewable by uploader or supervisor)."""
    verify_case_access(user, document.case_id, db, request, action="DOCUMENT_ACCESS")

    if document.classification == "SECRET":
        if user.role not in [UserRole.ADMINISTRATOR, UserRole.SUPERVISOR]:
            assignment = db.query(CaseAssignment).filter(
                CaseAssignment.case_id == document.case_id,
                CaseAssignment.user_id == user.id,
                CaseAssignment.assignment_role == "LEAD_INVESTIGATOR"
            ).first()
            if not assignment:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access Denied: TOP SECRET clearance required for this document."
                )

    if document.status == "DRAFT":
        if document.uploaded_by_id != user.id and user.role not in [UserRole.ADMINISTRATOR, UserRole.SUPERVISOR]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access Denied: Draft document is restricted to uploader and supervisor."
            )

    return True

def get_authorized_case_ids(user: User, db: Session) -> List[str]:
    """Returns list of case IDs the user is authorized to access."""
    if user.role in [UserRole.ADMINISTRATOR, UserRole.SUPERVISOR]:
        return [c.id for c in db.query(Case.id).all()]
    
    assignments = db.query(CaseAssignment.case_id).filter(CaseAssignment.user_id == user.id).all()
    return [a[0] for a in assignments]
