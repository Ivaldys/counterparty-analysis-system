from sqlalchemy import Column, Integer, String, Date, Numeric, Boolean, DateTime
from datetime import datetime
from db import Base


class OrgMetric(Base):
    __tablename__ = "fns_otkrdan_org_metrics"

    id = Column(Integer, primary_key=True, index=True)

    inn = Column(String, nullable=False, index=True)
    date_ref = Column(Date, nullable=False)
    org_name = Column(String)

    last_date_doc = Column(Date)

    staff_count = Column(Integer)
    sum_dohod = Column(Numeric(18, 2))
    sum_rashod = Column(Numeric(18, 2))

    src_sschr_file = Column(String)
    src_sschr_doc_id = Column(String)
    src_dohod_file = Column(String)
    src_dohod_doc_id = Column(String)