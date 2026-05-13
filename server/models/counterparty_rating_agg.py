from sqlalchemy import Column, BigInteger, ForeignKey, Integer, Numeric, DateTime, func
from db import Base


class CounterpartyRatingAgg(Base):
    __tablename__ = "counterparty_rating_agg"

    counterparty_id = Column(BigInteger, ForeignKey("counterparties.id", ondelete="CASCADE"), primary_key=True)
    reviews_count = Column(Integer, nullable=False, server_default="0")
    suspicious_count = Column(Integer, nullable=False, server_default="0")
    avg_rating = Column(Numeric(3, 2))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())