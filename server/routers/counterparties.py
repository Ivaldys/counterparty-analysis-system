from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy import func
from db import get_db
from models.counterparty import Counterparty
from models.user_counterparty import UserCounterparty
from models.counterparty_rating_agg import CounterpartyRatingAgg
from models.user import User
from services.dadata_service import get_dadata_finance_cached
from schemas import (
    CounterpartyDetailOut,
    UserCounterpartyUpsertIn,
    CounterpartyReviewUpdateIn,
    CounterpartyReviewsOut,
    CounterpartyReviewItemOut,
)
from security import get_current_user
from schemas import CounterpartyAISummaryOut, CounterpartyAISummaryIn
from services.llm_service import generate_counterparty_ai_summary

router = APIRouter(prefix="/counterparties", tags=["counterparties"])


def parse_date_safe(value):
    if not value:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "")).date()
        except Exception:
            return None
    return None

@router.post("/{counterparty_id}/ai-summary", response_model=CounterpartyAISummaryOut)
def get_counterparty_ai_summary(
    counterparty_id: int,
    payload: CounterpartyAISummaryIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cp = db.execute(
        select(Counterparty).where(Counterparty.id == counterparty_id)
    ).scalar_one_or_none()

    if not cp:
        raise HTTPException(status_code=404, detail="Контрагент не найден.")

    user_data = db.execute(
        select(UserCounterparty).where(
            UserCounterparty.user_id == current_user.id,
            UserCounterparty.counterparty_id == counterparty_id,
        )
    ).scalar_one_or_none()

    agg = db.execute(
        select(CounterpartyRatingAgg).where(
            CounterpartyRatingAgg.counterparty_id == counterparty_id
        )
    ).scalar_one_or_none()

    card = {
        "name": cp.name or cp.full_name,
        "inn": cp.inn,
        "entity_type": "ИП / самозанятый" if cp.inn and len(str(cp.inn)) == 12 else "Юрлицо",

        "total_paid": payload.total_paid if payload.total_paid is not None else (user_data.total_paid if user_data else None),
        "first_contract_date": payload.first_contract_date if payload.first_contract_date is not None else (
            user_data.first_contract_date.isoformat() if user_data and user_data.first_contract_date else None
        ),
        "reg_date": cp.reg_date.isoformat() if cp.reg_date else None,

        "income_2024": payload.income_2024,
        "staff_count": payload.staff_count,
        "income_share": payload.income_share,
        "date_diff_days": payload.date_diff_days,
        "income_per_staff": payload.income_per_staff,
        "final_score": payload.final_score,

        "user_verdict": user_data.verdict if user_data else None,
        "avg_rating": float(agg.avg_rating) if agg and agg.avg_rating is not None else None,
        "reviews_count": agg.reviews_count if agg else 0,

        "egrul_flags": payload.egrul_flags or [],
        "egrul_risk": payload.egrul_risk,
    }
    summary = generate_counterparty_ai_summary(card)
    return {"summary": summary}

def fill_counterparty_from_dadata(cp: Counterparty, dadata_item: dict | None):
    if not dadata_item:
        return

    data = dadata_item.get("data") or {}

    name_data = data.get("name") or {}
    state_data = data.get("state") or {}
    address_data = data.get("address") or {}
    management_data = data.get("management") or {}

    cp.inn = data.get("inn") or cp.inn
    cp.kpp = data.get("kpp") or cp.kpp
    cp.ogrn = data.get("ogrn") or cp.ogrn

    short_name = (
        name_data.get("short_with_opf")
        or name_data.get("short")
        or name_data.get("full_with_opf")
    )

    full_name = (
        name_data.get("full_with_opf")
        or name_data.get("full")
        or short_name
    )

    cp.name = short_name or cp.name
    cp.full_name = full_name or cp.full_name

    cp.status = state_data.get("status") or cp.status
    cp.address = address_data.get("value") or cp.address
    cp.okved_main = data.get("okved") or cp.okved_main
    cp.ceo_name = management_data.get("name") or cp.ceo_name

    reg_ts = state_data.get("registration_date")
    if reg_ts and not cp.reg_date:
        try:
            cp.reg_date = datetime.fromtimestamp(reg_ts / 1000).date()
        except Exception:
            pass

def recalc_counterparty_rating_agg(db: Session, counterparty_id: int):
    stats = db.query(
        func.count(UserCounterparty.id).filter(UserCounterparty.rating.isnot(None)),
        func.avg(UserCounterparty.rating).filter(UserCounterparty.rating.isnot(None)),
        func.count(UserCounterparty.id).filter(UserCounterparty.verdict == "suspicious"),
    ).filter(
        UserCounterparty.counterparty_id == counterparty_id
    ).one()

    reviews_count = int(stats[0] or 0)
    avg_rating = float(stats[1]) if stats[1] is not None else None
    suspicious_count = int(stats[2] or 0)

    agg = db.execute(
        select(CounterpartyRatingAgg).where(
            CounterpartyRatingAgg.counterparty_id == counterparty_id
        )
    ).scalar_one_or_none()

    if not agg:
        agg = CounterpartyRatingAgg(
            counterparty_id=counterparty_id,
            reviews_count=reviews_count,
            suspicious_count=suspicious_count,
            avg_rating=avg_rating,
        )
        db.add(agg)
    else:
        agg.reviews_count = reviews_count
        agg.suspicious_count = suspicious_count
        agg.avg_rating = avg_rating


@router.get("/by-inn/{inn}", response_model=CounterpartyDetailOut)
def get_counterparty_detail_by_inn(
    inn: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    inn = (inn or "").strip()
    if not inn:
        raise HTTPException(status_code=400, detail="ИНН обязателен.")

    cp = db.execute(
        select(Counterparty).where(Counterparty.inn == inn)
    ).scalar_one_or_none()

    if cp is None:
        cp = Counterparty(inn=inn)
        db.add(cp)
        db.flush()

    # тянем данные из DaData
    try:
        dadata_pack = get_dadata_finance_cached(inn)
        dadata_party = dadata_pack.get("party_raw")
        fill_counterparty_from_dadata(cp, dadata_party)
        db.commit()
        db.refresh(cp)
    except Exception as e:
        print("DADATA LOAD ERROR:", e)
        db.rollback()

        cp = db.execute(
            select(Counterparty).where(Counterparty.inn == inn)
        ).scalar_one_or_none()

    user_data = db.execute(
        select(UserCounterparty).where(
            UserCounterparty.user_id == current_user.id,
            UserCounterparty.counterparty_id == cp.id,
        )
    ).scalar_one_or_none()

    agg = db.execute(
        select(CounterpartyRatingAgg).where(
            CounterpartyRatingAgg.counterparty_id == cp.id
        )
    ).scalar_one_or_none()

    return {
        "counterparty": cp,
        "user_data": user_data,
        "agg": agg,
    }


@router.post("/upsert-me", response_model=CounterpartyDetailOut)
def upsert_user_counterparty_from_analysis(
    payload: UserCounterpartyUpsertIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    inn = (payload.inn or "").strip()
    if not inn:
        raise HTTPException(status_code=400, detail="ИНН обязателен.")

    cp = db.execute(
        select(Counterparty).where(Counterparty.inn == inn)
    ).scalar_one_or_none()

    if cp is None:
        cp = Counterparty(
            inn=inn,
            name=(payload.name or "").strip() or None,
        )
        db.add(cp)
        db.flush()
    else:
        if payload.name and str(payload.name).strip():
            cp.name = str(payload.name).strip()

    parsed_first_date = parse_date_safe(payload.first_contract_date)
    parsed_last_date = parse_date_safe(payload.last_contract_date)

    uc = db.execute(
        select(UserCounterparty).where(
            UserCounterparty.user_id == current_user.id,
            UserCounterparty.counterparty_id == cp.id,
        )
    ).scalar_one_or_none()

    if uc is None:
        uc = UserCounterparty(
            user_id=current_user.id,
            counterparty_id=cp.id,
            total_paid=payload.total_paid,
            tx_count=payload.tx_count if payload.tx_count is not None else 0,
            first_contract_date=parsed_first_date,
            last_contract_date=parsed_last_date,
            active_months_count=payload.active_months_count,
            verdict=payload.verdict or "unknown",
        )
        db.add(uc)
    else:
        if payload.total_paid is not None:
            uc.total_paid = payload.total_paid

        if payload.tx_count is not None:
            uc.tx_count = payload.tx_count

        if parsed_first_date is not None:
            uc.first_contract_date = parsed_first_date

        if parsed_last_date is not None:
            uc.last_contract_date = parsed_last_date

        if payload.active_months_count is not None:
            uc.active_months_count = payload.active_months_count

        if payload.verdict is not None:
            uc.verdict = payload.verdict

    db.commit()
    db.refresh(cp)
    db.refresh(uc)

    agg = db.execute(
        select(CounterpartyRatingAgg).where(
            CounterpartyRatingAgg.counterparty_id == cp.id
        )
    ).scalar_one_or_none()

    return {
        "counterparty": {
            "id": cp.id,
            "inn": cp.inn,
            "kpp": cp.kpp,
            "ogrn": cp.ogrn,
            "name": cp.name,
            "full_name": cp.full_name,
            "status": cp.status,
            "reg_date": cp.reg_date.isoformat() if cp.reg_date else None,
            "address": cp.address,
            "okved_main": cp.okved_main,
            "ceo_name": cp.ceo_name,
            "ceo_inn": cp.ceo_inn,
        },
        "user_data": {
            "id": uc.id,
            "user_id": uc.user_id,
            "counterparty_id": uc.counterparty_id,
            "total_paid": float(uc.total_paid) if uc.total_paid is not None else None,
            "tx_count": uc.tx_count,
            "first_contract_date": uc.first_contract_date.isoformat() if uc.first_contract_date else None,
            "last_contract_date": uc.last_contract_date.isoformat() if uc.last_contract_date else None,
            "active_months_count": uc.active_months_count,
            "verdict": uc.verdict,
            "rating": uc.rating,
            "review_text": uc.review_text,
        },
        "agg": {
            "reviews_count": agg.reviews_count if agg else 0,
            "suspicious_count": agg.suspicious_count if agg else 0,
            "avg_rating": float(agg.avg_rating) if agg and agg.avg_rating is not None else None,
        },
    }


@router.put("/{counterparty_id}/review", response_model=CounterpartyReviewItemOut)
def update_review(
    counterparty_id: int,
    payload: CounterpartyReviewUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cp = db.execute(
        select(Counterparty).where(Counterparty.id == counterparty_id)
    ).scalar_one_or_none()

    if not cp:
        raise HTTPException(status_code=404, detail="Контрагент не найден.")

    uc = db.execute(
        select(UserCounterparty).where(
            UserCounterparty.user_id == current_user.id,
            UserCounterparty.counterparty_id == counterparty_id,
        )
    ).scalar_one_or_none()

    if not uc:
        uc = UserCounterparty(
            user_id=current_user.id,
            counterparty_id=counterparty_id,
            total_paid=0,
            tx_count=0,
            verdict=payload.verdict if payload.verdict is not None else "unknown",
            rating=payload.rating,
            review_text=(payload.review_text or "").strip() or None,
            is_anonymous=payload.is_anonymous,
        )
        db.add(uc)
    else:
        if payload.verdict is not None:
            uc.verdict = payload.verdict
        uc.rating = payload.rating
        uc.review_text = (payload.review_text or "").strip() or None
        uc.is_anonymous = payload.is_anonymous

    db.flush()

    recalc_counterparty_rating_agg(db, counterparty_id)

    db.commit()
    db.refresh(uc)

    return CounterpartyReviewItemOut(
        user_counterparty_id=uc.id,
        user_id=uc.user_id,
        rating=uc.rating,
        review_text=uc.review_text,
        verdict=uc.verdict,
        is_anonymous=bool(uc.is_anonymous),
        author_name=None if uc.is_anonymous else current_user.full_name,
        author_company=None if uc.is_anonymous else current_user.company_name,
        author_inn=None if uc.is_anonymous else current_user.company_inn,
        updated_at=uc.updated_at,
    )

@router.get("/{counterparty_id}/reviews", response_model=CounterpartyReviewsOut)
def get_counterparty_reviews(
    counterparty_id: int,
    db: Session = Depends(get_db),
):
    rows = (
        db.query(UserCounterparty, User)
        .join(User, User.id == UserCounterparty.user_id)
        .filter(
            UserCounterparty.counterparty_id == counterparty_id,
            UserCounterparty.rating.isnot(None)
        )
        .order_by(UserCounterparty.updated_at.desc())
        .all()
    )

    items = []

    for uc, user in rows:
        is_anonymous = bool(uc.is_anonymous)

        items.append(
            CounterpartyReviewItemOut(
                user_counterparty_id=uc.id,
                user_id=uc.user_id,
                rating=uc.rating,
                review_text=uc.review_text,
                verdict=uc.verdict,
                is_anonymous=is_anonymous,
                author_name=None if is_anonymous else user.full_name,
                author_company=None if is_anonymous else user.company_name,
                author_inn=None if is_anonymous else user.company_inn,
                updated_at=uc.updated_at,
            )
        )

    return CounterpartyReviewsOut(items=items)