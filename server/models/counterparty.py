from sqlalchemy import Column, BigInteger, Text, Date, DateTime, func
from db import Base


class Counterparty(Base):
    __tablename__ = "counterparties"

    id = Column(BigInteger, primary_key=True, index=True)
    inn = Column(Text, nullable=False, unique=True, index=True)
    kpp = Column(Text)
    ogrn = Column(Text)
    name = Column(Text)
    full_name = Column(Text)
    status = Column(Text)
    reg_date = Column(Date)
    address = Column(Text)
    okved_main = Column(Text)
    ceo_name = Column(Text)
    ceo_inn = Column(Text)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())