"""LedgerBlock Model"""


from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.session import Base
from app.utils.time import utcnow

class LedgerBlock(Base):
    __tablename__ = "ledger_blocks"

    id = Column(Integer, primary_key=True, index=True)
    block_number = Column(Integer, unique=True, nullable=False, index=True)
    timestamp = Column(DateTime, default=utcnow, nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True, index=True)
    case_id = Column(String(50), nullable=True)
    version_number = Column(Integer, nullable=True)
    document_hash = Column(String(64), nullable=False)
    event_type = Column(String(50), nullable=False)
    user_id = Column(Integer, nullable=True)
    user_email = Column(String(255), nullable=True)
    user_role = Column(String(100), nullable=True)
    previous_hash = Column(String(64), nullable=False)
    block_hash = Column(String(64), unique=True, nullable=False)
    chaincode_tx_id = Column(String(100), nullable=True)

    document = relationship("Document", back_populates="ledger_blocks")
