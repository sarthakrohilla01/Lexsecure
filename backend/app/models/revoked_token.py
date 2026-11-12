"""RevokedToken Model"""

from sqlalchemy import Column, Integer, String, DateTime

from app.database.session import Base
from app.utils.time import utcnow


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, default=utcnow, nullable=False)
