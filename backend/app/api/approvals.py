"""Approvals API"""

from typing import List
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.user import User, UserRole
from app.models.document import Document
from app.models.approval import DualAuthRequest
from app.security.abac import get_current_user, verify_document_access
from fastapi import Request
from app.audit.logger import record_audit_event
from app.api.ws import ws_manager
from app.utils.time import utcnow
from pydantic import BaseModel

router = APIRouter(prefix="/approvals", tags=["Dual Auth Approvals"])

class RequestAccessDTO(BaseModel):
    document_id: int

class ApprovalDTO(BaseModel):
    request_id: int
    approve: bool

class DualAuthResponseDTO(BaseModel):
    id: int
    document_id: int
    document_title: str
    requester_email: str
    status: str
    unlock_token: str | None = None
    expires_at: datetime | None = None

def _to_dto(r: DualAuthRequest, requester_email: str) -> DualAuthResponseDTO:
    live_token = r.unlock_token
    if r.status != "APPROVED" or (r.expires_at and r.expires_at < utcnow()):
        live_token = None
    return DualAuthResponseDTO(
        id=r.id,
        document_id=r.document_id,
        document_title=r.document.title,
        requester_email=requester_email,
        status=r.status,
        unlock_token=live_token,
        expires_at=r.expires_at
    )

@router.post("/request", response_model=DualAuthResponseDTO)
def request_access(
    payload: RequestAccessDTO,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doc = db.query(Document).filter(Document.id == payload.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    verify_document_access(current_user, doc, db, request=request)

    if not doc.requires_dual_auth:
        raise HTTPException(status_code=400, detail="Document does not require dual auth.")

    live = db.query(DualAuthRequest).filter(
        DualAuthRequest.document_id == doc.id,
        DualAuthRequest.requester_id == current_user.id,
        DualAuthRequest.status == "APPROVED",
        DualAuthRequest.expires_at > utcnow()
    ).first()
    if live:
        return _to_dto(live, current_user.email)

    existing = db.query(DualAuthRequest).filter(
        DualAuthRequest.document_id == doc.id,
        DualAuthRequest.requester_id == current_user.id,
        DualAuthRequest.status == "PENDING"
    ).first()

    if existing:
        return _to_dto(existing, current_user.email)

    req = DualAuthRequest(
        document_id=doc.id,
        requester_id=current_user.id
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    record_audit_event(
        db=db,
        action="DUAL_AUTH_REQUESTED",
        user=current_user,
        details=f"Requested access to {doc.title}"
    )

    return _to_dto(req, current_user.email)

@router.get("/pending", response_model=List[DualAuthResponseDTO])
def get_pending_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in [UserRole.SUPERVISOR, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only supervisors can view pending requests.")

    reqs = (
        db.query(DualAuthRequest)
        .filter(DualAuthRequest.status == "PENDING")
        .order_by(DualAuthRequest.id.desc())
        .all()
    )

    return [_to_dto(r, r.requester.email) for r in reqs]
    
@router.get("/my-requests", response_model=List[DualAuthResponseDTO])
def get_my_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    reqs = (
        db.query(DualAuthRequest)
        .filter(DualAuthRequest.requester_id == current_user.id)
        .order_by(DualAuthRequest.id.desc())
        .all()
    )
    return [_to_dto(r, current_user.email) for r in reqs]

@router.post("/process", response_model=DualAuthResponseDTO)
def process_request(
    payload: ApprovalDTO,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in [UserRole.SUPERVISOR, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only supervisors can approve requests.")

    req = db.query(DualAuthRequest).filter(DualAuthRequest.id == payload.request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if payload.approve:
        req.status = "APPROVED"
        req.approver_id = current_user.id
        req.unlock_token = str(uuid.uuid4())
        req.expires_at = utcnow() + timedelta(hours=2)
        
        record_audit_event(
            db=db,
            action="DUAL_AUTH_APPROVED",
            user=current_user,
            details=f"Approved access to document {req.document_id} for user {req.requester.email}"
        )
    else:
        req.status = "REJECTED"
        req.approver_id = current_user.id
        
        record_audit_event(
            db=db,
            action="DUAL_AUTH_REJECTED",
            user=current_user,
            details=f"Rejected access to document {req.document_id} for user {req.requester.email}"
        )

    db.commit()
    db.refresh(req)

    ws_manager.broadcast_sync("APPROVAL_DECIDED", {
        "request_id": req.id,
        "document_id": req.document_id,
        "status": req.status,
        "approver": current_user.email,
        "requester": req.requester.email,
        "message": (
            f"{current_user.full_name} {req.status.lower()} dual-authorization "
            f"for document #{req.document_id}"
        ),
    })

    return _to_dto(req, req.requester.email)
