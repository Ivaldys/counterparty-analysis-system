from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, BigInteger
from datetime import datetime
from db import Base
from sqlalchemy.orm import relationship


class AuthEmailCode(Base):
    __tablename__ = "auth_email_codes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code_hash = Column(String, nullable=False)
    purpose = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)
    is_active = Column(Boolean, nullable=False, default=True)
    used_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User")