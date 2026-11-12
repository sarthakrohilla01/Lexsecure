"""Case and CaseAssignment Models"""


from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database.session import Base
from app.utils.time import utcnow

class Case(Base):
    __tablename__ = "cases"

    id = Column(String(50), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    department = Column(String(255), nullable=False)
    status = Column(String(50), default="UNDER_INVESTIGATION")
    classification = Column(String(50), default="RESTRICTED")
    incident_date = Column(DateTime, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    assignments = relationship("CaseAssignment", back_populates="case", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="case", cascade="all, delete-orphan")

class CaseAssignment(Base):
    __tablename__ = "case_assignments"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String(50), ForeignKey("cases.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assignment_role = Column(String(50), nullable=False)
    assigned_at = Column(DateTime, default=utcnow)
    can_upload = Column(Boolean, default=True)
    can_approve = Column(Boolean, default=False)

    case = relationship("Case", back_populates="assignments")
    user = relationship("User", back_populates="case_assignments")
