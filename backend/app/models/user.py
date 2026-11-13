"""User, Role, and Department Models"""

import enum

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, Text
from sqlalchemy.orm import relationship
from app.database.session import Base
from app.utils.time import utcnow

class UserRole(str, enum.Enum):
    INVESTIGATOR = "INVESTIGATOR"
    FORENSIC_EXPERT = "FORENSIC_EXPERT"
    LEGAL_OFFICER = "LEGAL_OFFICER"
    SUPERVISOR = "SUPERVISOR"
    ADMINISTRATOR = "ADMINISTRATOR"

class Department(str, enum.Enum):
    CYBER_CRIME = "Cyber Crime Division"
    WOMEN_SAFETY = "Women Safety Division"
    FORENSIC_LAB = "Central Forensic Science Laboratory"
    PROSECUTION = "Directorate of Prosecution"
    SPECIAL_INVESTIGATION = "Special Investigation Cell"
    ADMINISTRATION = "System Administration"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.INVESTIGATOR)
    department = Column(String(255), nullable=False, default=Department.CYBER_CRIME.value)
    hashed_password = Column(String(255), nullable=False)
    badge_number = Column(String(50), nullable=True)

    mfa_enabled = Column(Boolean, default=True)
    mfa_secret = Column(String(64), nullable=True)
    mfa_activated_at = Column(DateTime, nullable=True)
    mfa_last_step = Column(Integer, nullable=True)
    mfa_backup_codes = Column(Text, nullable=True)

    public_key_pem = Column(Text, nullable=True)
    private_key_pem = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)
    is_temporary = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    case_assignments = relationship("CaseAssignment", back_populates="user")
    signatures = relationship("DigitalSignature", back_populates="signer")
