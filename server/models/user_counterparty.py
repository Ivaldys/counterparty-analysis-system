from sqlalchemy import (
    Column, BigInteger, ForeignKey, Text, Date, Integer, Numeric,
    DateTime, Boolean, func
)
from db import Base


class UserCounterparty(Base):
    __tablename__ = "user_counterparty"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    counterparty_id = Column(BigInteger, ForeignKey("counterparties.id", ondelete="CASCADE"), nullable=False, index=True)

    total_paid = Column(Numeric(18, 2))
    tx_count = Column(Integer)
    first_contract_date = Column(Date)
    last_contract_date = Column(Date)
    active_months_count = Column(Integer)

    verdict = Column(Text)          # ok / suspicious / unknown
    rating = Column(Integer)        # 1..5
    review_text = Column(Text)
    is_anonymous = Column(Boolean, nullable=False, server_default="false")

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
