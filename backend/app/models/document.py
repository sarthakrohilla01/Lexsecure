"""Document, DocumentVersion, and DocumentMetadata Models"""


from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from app.database.session import Base
from app.utils.time import utcnow

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String(50), ForeignKey("cases.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    document_type = Column(String(100), nullable=False)
    classification = Column(String(50), default="RESTRICTED")
    requires_dual_auth = Column(Boolean, default=False)
    current_version = Column(Integer, default=1)
    status = Column(String(50), default="DRAFT")
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    case = relationship("Case", back_populates="documents")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan", order_by="DocumentVersion.version_number")
    uploader = relationship("User", foreign_keys=[uploaded_by_id])
    comments = relationship("DocumentComment", back_populates="document", cascade="all, delete-orphan")
    ledger_blocks = relationship("LedgerBlock", back_populates="document")

class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    object_key = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    sha256_hash = Column(String(64), nullable=False, index=True)
    encryption_iv = Column(String(64), nullable=False)
    encryption_tag = Column(String(64), nullable=False)
    change_reason = Column(Text, nullable=True)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow)

    is_tampered = Column(Boolean, default=False)
    tampered_hash = Column(String(64), nullable=True)

    document = relationship("Document", back_populates="versions")
    metadata_record = relationship("DocumentMetadata", back_populates="version", uselist=False, cascade="all, delete-orphan")
    signatures = relationship("DigitalSignature", back_populates="version", cascade="all, delete-orphan")
    uploader = relationship("User", foreign_keys=[uploaded_by_id])

class DocumentMetadata(Base):
    __tablename__ = "document_metadata"

    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("document_versions.id"), nullable=False, unique=True)
    extracted_text = Column(Text, nullable=True)
    page_count = Column(Integer, default=1)
    ocr_applied = Column(Boolean, default=False)
    malware_scanned = Column(Boolean, default=True)
    scan_clean = Column(Boolean, default=True)
    ai_classification = Column(String(100), nullable=True)
    ai_confidence = Column(Float, default=0.95)
    extracted_keywords = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    scan_engine = Column(String(50), nullable=True)
    scan_signature = Column(String(255), nullable=True)

    version = relationship("DocumentVersion", back_populates="metadata_record")
