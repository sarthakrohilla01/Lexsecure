"""AuditLog Model"""


from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database.session import Base
from app.utils.time import utcnow

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=utcnow, nullable=False, index=True)
    user_id = Column(Integer, nullable=True)
    user_email = Column(String(255), nullable=True)
    user_role = Column(String(100), nullable=True)
    ip_address = Column(String(100), default="127.0.0.1")
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=True)
    target_id = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    status = Column(String(50), default="SUCCESS")
