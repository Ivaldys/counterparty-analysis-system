from sqlalchemy import Column, BigInteger, Text, Boolean, DateTime, func
from db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)

    email = Column(Text, nullable=False, unique=True, index=True)
    password_hash = Column(Text, nullable=False)

    full_name = Column(Text, nullable=False)
    phone = Column(Text)

    company_name = Column(Text)
    company_inn = Column(Text)

    email_verified = Column(Boolean, nullable=False, default=False)
    last_login_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())