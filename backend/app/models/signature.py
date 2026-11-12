"""DigitalSignature Model"""


from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database.session import Base
from app.utils.time import utcnow

class DigitalSignature(Base):
    __tablename__ = "signatures"

    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("document_versions.id"), nullable=False, index=True)
    signer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    signer_name = Column(String(255), nullable=False)
    signer_role = Column(String(100), nullable=False)
    signature_hex = Column(Text, nullable=False)
    algorithm = Column(String(50), default="SHA256withRSA-2048")
    signed_at = Column(DateTime, default=utcnow)
    is_valid = Column(Boolean, default=True)
    certificate_serial = Column(String(100), nullable=True)

    version = relationship("DocumentVersion", back_populates="signatures")
    signer = relationship("User", back_populates="signatures")
