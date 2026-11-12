"""LoginAttempt Model"""


from sqlalchemy import Column, Integer, String, DateTime
from app.database.session import Base
from app.utils.time import utcnow


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(320), unique=True, index=True, nullable=False)
    failures = Column(Integer, default=0, nullable=False)
    first_failure_at = Column(DateTime, default=utcnow, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
