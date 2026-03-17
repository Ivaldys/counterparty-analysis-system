from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


PASSWORD_MIN = 8
PASSWORD_MAX = 64


class MetricOut(BaseModel):
    inn: str
    sum_dohod: Optional[float] = None
    staff_count: Optional[int] = None
    registration_date: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ===== Вход =====
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ===== Регистрация =====
class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)
    phone: Optional[str] = None
    company_name: Optional[str] = None
    company_inn: Optional[str] = None


class VerifyEmailIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=32)


# ===== Забыл пароль =====
class ForgotRequestIn(BaseModel):
    email: EmailStr


class ForgotConfirmIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=32)


class ForgotResetIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=32)
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


class OkOut(BaseModel):
    ok: bool = True
    detail: str = "ok"


# ===== Профиль =====
class ProfileResponse(BaseModel):
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    company_name: Optional[str] = None
    company_inn: Optional[str] = None
    email_verified: bool

    model_config = ConfigDict(from_attributes=True)


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=32)
    company_name: Optional[str] = Field(default=None, max_length=255)
    company_inn: Optional[str] = Field(default=None, max_length=20)


class ChangePassword(BaseModel):
    old_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


# ===== Контрагенты =====
class CounterpartyBaseOut(BaseModel):
    id: int
    inn: str
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    name: Optional[str] = None
    full_name: Optional[str] = None
    status: Optional[str] = None
    reg_date: Optional[date] = None
    address: Optional[str] = None
    okved_main: Optional[str] = None
    ceo_name: Optional[str] = None
    ceo_inn: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserCounterpartyOut(BaseModel):
    id: int
    user_id: int
    counterparty_id: int
    total_paid: Optional[float] = None
    tx_count: Optional[int] = None
    first_contract_date: Optional[date] = None
    last_contract_date: Optional[date] = None
    active_months_count: Optional[int] = None
    verdict: Optional[Literal["ok", "suspicious", "unknown"]] = None
    rating: Optional[int] = None
    review_text: Optional[str] = None
    is_anonymous: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CounterpartyAggOut(BaseModel):
    reviews_count: int = 0
    suspicious_count: int = 0
    avg_rating: Optional[float] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CounterpartyDetailOut(BaseModel):
    counterparty: CounterpartyBaseOut
    user_data: Optional[UserCounterpartyOut] = None
    agg: Optional[CounterpartyAggOut] = None


class UserCounterpartyUpsertIn(BaseModel):
    inn: str
    name: Optional[str] = None
    total_paid: Optional[float] = None
    tx_count: Optional[int] = None
    first_contract_date: Optional[date] = None
    last_contract_date: Optional[date] = None
    active_months_count: Optional[int] = None
    verdict: Optional[Literal["ok", "suspicious", "unknown"]] = "unknown"


# ===== Отзывы =====
class CounterpartyReviewUpdateIn(BaseModel):
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    review_text: Optional[str] = None
    verdict: Optional[Literal["ok", "suspicious", "unknown"]] = None
    is_anonymous: bool = False


class CounterpartyReviewItemOut(BaseModel):
    user_counterparty_id: int
    user_id: int

    rating: Optional[int] = None
    review_text: Optional[str] = None
    verdict: Optional[Literal["ok", "suspicious", "unknown"]] = None
    is_anonymous: bool = False

    author_name: Optional[str] = None
    author_company: Optional[str] = None
    author_inn: Optional[str] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CounterpartyReviewsOut(BaseModel):
    items: List[CounterpartyReviewItemOut]

class CounterpartyAISummaryIn(BaseModel):
    total_paid: Optional[float] = None
    first_contract_date: Optional[str] = None
    income_2024: Optional[float] = None
    staff_count: Optional[float] = None
    income_share: Optional[float] = None
    date_diff_days: Optional[float] = None
    income_per_staff: Optional[float] = None
    final_score: Optional[float] = None
    egrul_flags: Optional[List[str]] = None
    egrul_risk: Optional[float] = None
    force_refresh: Optional[bool] = False


class CounterpartyAISummaryOut(BaseModel):
    summary: str