"""Collaboration & Approval Workflow API"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.document import Document, DocumentVersion
from app.models.workflow import DocumentComment
from app.models.user import User, UserRole
from app.schemas.workflow import WorkflowActionRequest, CommentCreate, CommentResponse
from app.security.abac import (
    get_authorized_case_ids,
    get_current_user,
    require_roles,
    verify_document_access,
)
from app.blockchain.ledger_service import record_ledger_block
from app.audit.logger import record_audit_event

router = APIRouter(prefix="/workflow", tags=["Collaboration & Workflow"])

@router.post("/approve")
def approve_document(
    payload: WorkflowActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.SUPERVISOR, UserRole.LEGAL_OFFICER, UserRole.ADMINISTRATOR]))
):
    """Supervisory approval for legal / investigation documents. Transitions document state to APPROVED and commits an event to the Blockchain Ledger."""
    doc = db.query(Document).filter(Document.id == payload.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    verify_document_access(current_user, doc, db)

    version = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc.id,
        DocumentVersion.version_number == doc.current_version
    ).first()

    doc.status = "APPROVED"
    db.commit()

    ledger_block = record_ledger_block(
        db=db,
        document_id=doc.id,
        case_id=doc.case_id,
        version_number=doc.current_version,
        document_hash=version.sha256_hash if version else "0"*64,
        event_type="APPROVED",
        user_id=current_user.id,
        user_email=current_user.email,
        user_role=current_user.role.value
    )

    record_audit_event(
        db=db,
        action="DOCUMENT_APPROVED",
        target_type="DOCUMENT",
        target_id=str(doc.id),
        details=f"Document '{doc.title}' v{doc.current_version} approved by {current_user.full_name}. Notes: {payload.notes or 'None'}. Ledger Block #{ledger_block.block_number}",
        user=current_user,
        status="SUCCESS"
    )

    return {
        "status": "SUCCESS",
        "document_id": doc.id,
        "document_status": doc.status,
        "approved_by": current_user.full_name,
        "ledger_block_number": ledger_block.block_number
    }

@router.post("/reject")
def reject_document(
    payload: WorkflowActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.SUPERVISOR, UserRole.LEGAL_OFFICER, UserRole.ADMINISTRATOR]))
):
    """Rejects a submitted document with review notes."""
    doc = db.query(Document).filter(Document.id == payload.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    verify_document_access(current_user, doc, db)

    doc.status = "REJECTED"
    db.commit()

    record_audit_event(
        db=db,
        action="DOCUMENT_REJECTED",
        target_type="DOCUMENT",
        target_id=str(doc.id),
        details=f"Document '{doc.title}' rejected by {current_user.full_name}. Reason: {payload.notes}",
        user=current_user,
        status="WARNING"
    )

    return {
        "status": "SUCCESS",
        "document_id": doc.id,
        "document_status": doc.status,
        "rejected_by": current_user.full_name
    }

@router.get("/tasks")
def get_pending_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns documents pending review or approval."""
    authorized_case_ids = get_authorized_case_ids(current_user, db)
    if not authorized_case_ids:
        return []

    docs = (
        db.query(Document)
        .filter(
            Document.status == "UNDER_REVIEW",
            Document.case_id.in_(authorized_case_ids),
        )
        .all()
    )
    tasks = []
    for d in docs:
        tasks.append({
            "document_id": d.id,
            "case_id": d.case_id,
            "title": d.title,
            "document_type": d.document_type,
            "current_version": d.current_version,
            "uploaded_by": d.uploader.full_name if d.uploader else "Unknown",
            "created_at": d.created_at,
            "status": d.status
        })
    return tasks

@router.post("/comments", response_model=CommentResponse)
def add_document_comment(
    payload: CommentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Adds a collaboration comment or investigation note to a document."""
    doc = db.query(Document).filter(Document.id == payload.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    verify_document_access(current_user, doc, db, request=request)

    comment = DocumentComment(
        document_id=doc.id,
        user_id=current_user.id,
        user_name=current_user.full_name,
        user_role=current_user.role.value,
        content=payload.content
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    record_audit_event(
        db=db,
        action="COMMENT_ADDED",
        target_type="DOCUMENT",
        target_id=str(doc.id),
        details=f"Comment added on {doc.title} by {current_user.full_name}",
        user=current_user,
        status="SUCCESS"
    )

    return comment

@router.get("/comments/{document_id}", response_model=List[CommentResponse])
def get_document_comments(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists comments and notes for a document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    verify_document_access(current_user, doc, db, request=request)

    return db.query(DocumentComment).filter(
        DocumentComment.document_id == document_id
    ).order_by(DocumentComment.created_at.asc()).all()
