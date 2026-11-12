"""Document and Version Schemas"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class DigitalSignatureDTO(BaseModel):
    signer_name: str
    signer_role: str
    signature_hex: str
    algorithm: str
    signed_at: datetime
    is_valid: bool
    certificate_serial: Optional[str] = None

class DocumentMetadataDTO(BaseModel):
    page_count: int = 1
    ocr_applied: bool = False
    malware_scanned: bool = True
    scan_clean: bool = True
    ai_classification: Optional[str] = None
    ai_confidence: float = 0.95
    extracted_keywords: Optional[str] = None
    summary: Optional[str] = None

class DocumentVersionDTO(BaseModel):
    id: int
    version_number: int
    file_name: str
    file_size: int
    mime_type: str
    sha256_hash: str
    change_reason: Optional[str] = None
    created_at: datetime
    uploader_name: Optional[str] = None
    is_tampered: bool = False
    metadata: Optional[DocumentMetadataDTO] = None
    signatures: List[DigitalSignatureDTO] = []

class DocumentSummaryDTO(BaseModel):
    id: int
    case_id: str
    title: str
    document_type: str
    classification: str
    requires_dual_auth: bool = False
    current_version: int
    status: str
    uploaded_by_name: Optional[str] = None
    created_at: datetime
    latest_hash: Optional[str] = None
    is_tampered: bool = False

class DocumentDetailDTO(DocumentSummaryDTO):
    versions: List[DocumentVersionDTO] = []
    can_edit: bool = True
    can_sign: bool = True
    can_approve: bool = False
    signed_by_me: bool = False
    dual_auth_granted: bool = False
    dual_auth_expires_at: Optional[datetime] = None

class SignRequest(BaseModel):
    notes: Optional[str] = "Approved and signed digital record"

class IntegrityReportDTO(BaseModel):
    status: str
    is_valid: bool
    document_id: int
    version_number: int
    expected_hash: str
    actual_hash: str
    hash_match: bool
    decryption_status: str
    digital_signature: Dict[str, Any]
    blockchain_ledger: Dict[str, Any]
    details: str
