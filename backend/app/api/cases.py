"""Case Management API Endpoints"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.case import Case, CaseAssignment
from app.models.document import Document, DocumentVersion
from app.models.user import User, UserRole
from app.schemas.case import CaseCreate, CaseSummaryResponse, CaseDetailResponse, CaseOfficerAssignment
from app.schemas.document import DocumentSummaryDTO
from app.security.abac import get_current_user, verify_case_access, get_authorized_case_ids
from app.audit.logger import record_audit_event
from app.api.ws import ws_manager

router = APIRouter(prefix="/cases", tags=["Case Management"])

@router.get("", response_model=List[CaseSummaryResponse])
def list_cases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists cases with assignment status flags. Allows officers to browse case metadata while maintaining strict document-level isolation."""
    cases = db.query(Case).all()
    user_case_ids = set(get_authorized_case_ids(current_user, db))

    results = []
    for c in cases:
        doc_count = db.query(Document).filter(Document.case_id == c.id).count()
        officers_count = db.query(CaseAssignment).filter(CaseAssignment.case_id == c.id).count()
        results.append({
            "id": c.id,
            "title": c.title,
            "description": c.description,
            "department": c.department,
            "status": c.status,
            "classification": c.classification,
            "created_at": c.created_at,
            "document_count": doc_count,
            "assigned_officers_count": officers_count,
            "user_is_assigned": c.id in user_case_ids
        })
    return results

@router.post("", response_model=CaseDetailResponse)
def create_case(
    payload: CaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Creates a new criminal or legal investigation case."""
    existing = db.query(Case).filter(Case.id == payload.id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Case ID '{payload.id}' already exists")

    new_case = Case(
        id=payload.id,
        title=payload.title,
        description=payload.description,
        department=payload.department,
        status=payload.status or "UNDER_INVESTIGATION",
        classification=payload.classification or "RESTRICTED",
        created_by_id=current_user.id
    )
    db.add(new_case)
    db.commit()

    assignment = CaseAssignment(
        case_id=new_case.id,
        user_id=current_user.id,
        assignment_role="LEAD_INVESTIGATOR",
        can_upload=True,
        can_approve=(current_user.role in [UserRole.SUPERVISOR, UserRole.ADMINISTRATOR])
    )
    db.add(assignment)
    db.commit()
    db.refresh(new_case)

    record_audit_event(
        db=db,
        action="CASE_CREATED",
        target_type="CASE",
        target_id=new_case.id,
        details=f"Created case {new_case.id}: {new_case.title}",
        user=current_user,
        status="SUCCESS"
    )

    ws_manager.broadcast_sync("CASE_CREATED", {
        "case_id": new_case.id,
        "title": new_case.title,
        "classification": new_case.classification,
        "created_by": current_user.email,
        "message": f"New case {new_case.id} created by {current_user.full_name}",
    })

    return {
        "id": new_case.id,
        "title": new_case.title,
        "description": new_case.description,
        "department": new_case.department,
        "status": new_case.status,
        "classification": new_case.classification,
        "created_at": new_case.created_at,
        "updated_at": new_case.updated_at,
        "assigned_officers": [
            {
                "user_id": current_user.id,
                "user_name": current_user.full_name,
                "user_email": current_user.email,
                "user_role": current_user.role.value,
                "assignment_role": "LEAD_INVESTIGATOR"
            }
        ]
    }

@router.get("/{case_id}", response_model=CaseDetailResponse)
def get_case_details(
    case_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns case overview. ABAC Rule: Rejects access if officer is not assigned to this case."""
    case = verify_case_access(current_user, case_id, db, request=request)

    assignments = db.query(CaseAssignment).filter(CaseAssignment.case_id == case_id).all()
    officers = []
    for a in assignments:
        officers.append({
            "user_id": a.user.id,
            "user_name": a.user.full_name,
            "user_email": a.user.email,
            "user_role": a.user.role.value,
            "assignment_role": a.assignment_role
        })

    record_audit_event(
        db=db,
        action="CASE_VIEWED",
        target_type="CASE",
        target_id=case_id,
        details=f"Case overview viewed by {current_user.email}",
        user=current_user,
        status="SUCCESS"
    )

    return {
        "id": case.id,
        "title": case.title,
        "description": case.description,
        "department": case.department,
        "status": case.status,
        "classification": case.classification,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "assigned_officers": officers
    }

@router.get("/{case_id}/documents", response_model=List[DocumentSummaryDTO])
def get_case_documents(
    case_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves authorized documents belonging to this case. ABAC Rule: Enforces case assignment and classification level."""
    verify_case_access(current_user, case_id, db, request=request)

    docs = db.query(Document).filter(Document.case_id == case_id).order_by(Document.created_at.desc()).all()
    results = []
    for d in docs:
        latest_version = db.query(DocumentVersion).filter(
            DocumentVersion.document_id == d.id,
            DocumentVersion.version_number == d.current_version
        ).first()

        results.append({
            "id": d.id,
            "case_id": d.case_id,
            "title": d.title,
            "document_type": d.document_type,
            "classification": d.classification,
            "current_version": d.current_version,
            "status": d.status,
            "uploaded_by_name": d.uploader.full_name if d.uploader else "System",
            "created_at": d.created_at,
            "latest_hash": latest_version.sha256_hash if latest_version else None,
            "is_tampered": latest_version.is_tampered if latest_version else False,
            "requires_dual_auth": d.requires_dual_auth
        })
    return results
