from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List

from db import get_db
from models.orgmetric import OrgMetric
from schemas import MetricOut
from services.dadata_service import get_dadata_finance_cached

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/by-inn/{inn}", response_model=List[MetricOut])
def get_metrics_by_inn(inn: str, db: Session = Depends(get_db)):
    rows = db.execute(
        select(OrgMetric).where(OrgMetric.inn == inn).order_by(OrgMetric.date_ref.desc())
    ).scalars().all()

    dadata_pack = get_dadata_finance_cached(inn)
    dadata_income = dadata_pack["income_last"]

    if rows:
        return [
            MetricOut(
                inn=row.inn,
                sum_dohod=float(row.sum_dohod) if row.sum_dohod is not None else dadata_income,
                staff_count=row.staff_count if row.staff_count is not None else dadata_pack["staff_count"],
                registration_date=dadata_pack["registration_date"],
            )
            for row in rows
        ]

    return [MetricOut(inn=inn, sum_dohod=dadata_income, staff_count=dadata_pack["staff_count"], registration_date=dadata_pack["registration_date"])]