from datetime import datetime, timedelta
import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db import get_db
from models.user import User
from models.auth_email_codes import AuthEmailCode
from schemas import RegisterIn, LoginIn, VerifyEmailIn, TokenOut, OkOut
from security import hash_password, verify_password, create_access_token
from validators import validate_password_rules, validate_phone, validate_inn
from services.email_service import send_email_smtp
router = APIRouter(prefix="/auth", tags=["auth"])


def generate_code() -> str:
    return f"{random.randint(100000, 999999)}"

def utc_now():
    return datetime.utcnow().replace(tzinfo=None)

def send_email_code(email: str, code: str, purpose: str):
    if purpose == "email_verify":
        subject = "Подтверждение почты"
        body = (
            "Здравствуйте!\n\n"
            f"Ваш код подтверждения почты: {code}\n\n"
            "Код действует 15 минут."
        )
    elif purpose == "password_reset":
        subject = "Сброс пароля"
        body = (
            "Здравствуйте!\n\n"
            f"Ваш код для сброса пароля: {code}\n\n"
            "Код действует 15 минут."
        )
    else:
        subject = "Код подтверждения"
        body = (
            "Здравствуйте!\n\n"
            f"Ваш код: {code}\n\n"
            "Код действует 15 минут."
        )

    send_email_smtp(email, subject, body)


def deactivate_old_codes(db: Session, user_id: int, purpose: str):
    rows = (
        db.query(AuthEmailCode)
        .filter(
            AuthEmailCode.user_id == user_id,
            AuthEmailCode.purpose == purpose,
            AuthEmailCode.is_active == True,
            AuthEmailCode.used_at.is_(None),
        )
        .all()
    )
    for row in rows:
        row.is_active = False


@router.post("/register", response_model=OkOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    full_name = payload.full_name.strip()
    phone = (payload.phone or "").strip() or None
    company_name = (payload.company_name or "").strip() or None
    company_inn = (payload.company_inn or "").strip() or None

    validate_password_rules(payload.password)
    validate_phone(phone)
    validate_inn(company_inn)

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с такой почтой уже существует.")

    user = User(
        full_name=full_name,
        email=email,
        password_hash=hash_password(payload.password),
        phone=phone,
        company_name=company_name,
        company_inn=company_inn,
        email_verified=False,
        is_active=True,
    )
    db.add(user)
    db.flush()

    deactivate_old_codes(db, user.id, "email_verify")

    code = generate_code()
    row = AuthEmailCode(
        user_id=user.id,
        code_hash=hash_password(code),
        purpose="email_verify",
        expires_at=utc_now() + timedelta(minutes=15),
        attempts=0,
        max_attempts=5,
        is_active=True,
        used_at=None,
    )
    db.add(row)
    db.commit()
    try:
        send_email_code(email, code, "email_verify")
        return OkOut(ok=True, detail="Код подтверждения отправлен на почту.")
    except Exception as e:
        print("EMAIL SEND ERROR:", repr(e))
        return OkOut(ok=True, detail="Пользователь создан, но письмо пока не отправилось.")


@router.post("/verify-email", response_model=OkOut)
def verify_email(payload: VerifyEmailIn, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    code = payload.code.strip()

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден.")

    row = (
        db.query(AuthEmailCode)
        .filter(
            AuthEmailCode.user_id == user.id,
            AuthEmailCode.purpose == "email_verify",
            AuthEmailCode.is_active == True,
            AuthEmailCode.used_at.is_(None),
        )
        .order_by(AuthEmailCode.id.desc())
        .first()
    )

    if not row:
        raise HTTPException(status_code=400, detail="Активный код подтверждения не найден.")

    if row.expires_at.replace(tzinfo=None) < utc_now():
        row.is_active = False
        db.commit()
        raise HTTPException(status_code=400, detail="Срок действия кода истёк.")

    if row.attempts >= row.max_attempts:
        row.is_active = False
        db.commit()
        raise HTTPException(status_code=400, detail="Превышено число попыток ввода кода.")

    row.attempts += 1

    if not verify_password(code, row.code_hash):
        db.commit()
        raise HTTPException(status_code=400, detail="Неверный код подтверждения.")

    row.used_at = datetime.utcnow()
    row.is_active = False
    user.email_verified = True
    db.commit()

    return OkOut(ok=True, detail="Почта успешно подтверждена.")


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    password = payload.password

    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Неверная почта или пароль.")

    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверная почта или пароль.")

    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Сначала подтвердите почту.")

    token = create_access_token(user.id)
    return TokenOut(access_token=token, token_type="bearer")