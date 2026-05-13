from datetime import datetime, timedelta
import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db import get_db
from models.user import User
from models.auth_email_codes import AuthEmailCode
from schemas import ForgotRequestIn, ForgotConfirmIn, ForgotResetIn, OkOut
from security import hash_password, verify_password
from validators import validate_password_rules
from services.email_service import send_email_smtp

router = APIRouter(prefix="/forgot", tags=["forgot"])


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


@router.post("/request", response_model=OkOut)
def forgot_request(payload: ForgotRequestIn, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()

    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь с такой почтой не найден.")

    deactivate_old_codes(db, user.id, "password_reset")

    code = generate_code()
    row = AuthEmailCode(
        user_id=user.id,
        code_hash=hash_password(code),
        purpose="password_reset",
        expires_at=datetime.utcnow() + timedelta(minutes=15),
        attempts=0,
        max_attempts=5,
        is_active=True,
        used_at=None,
    )
    db.add(row)
    db.commit()
    try:
        send_email_code(email, code, "password_reset")
        return OkOut(ok=True, detail="Код подтверждения отправлен на почту.")
    except Exception as e:
        print("EMAIL SEND ERROR:", repr(e))
        return OkOut(ok=True, detail="Пользователь создан, но письмо пока не отправилось.")


@router.post("/confirm", response_model=OkOut)
def forgot_confirm(payload: ForgotConfirmIn, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    code = payload.code.strip()

    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден.")

    row = (
        db.query(AuthEmailCode)
        .filter(
            AuthEmailCode.user_id == user.id,
            AuthEmailCode.purpose == "password_reset",
            AuthEmailCode.is_active == True,
            AuthEmailCode.used_at.is_(None),
        )
        .order_by(AuthEmailCode.id.desc())
        .first()
    )

    if not row:
        raise HTTPException(status_code=400, detail="Активный код не найден.")

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
        raise HTTPException(status_code=400, detail="Неверный код.")

    db.commit()
    return OkOut(ok=True, detail="Код подтверждён.")


@router.post("/reset", response_model=OkOut)
def forgot_reset(payload: ForgotResetIn, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    code = payload.code.strip()
    new_password = payload.new_password

    validate_password_rules(new_password)

    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден.")

    row = (
        db.query(AuthEmailCode)
        .filter(
            AuthEmailCode.user_id == user.id,
            AuthEmailCode.purpose == "password_reset",
            AuthEmailCode.is_active == True,
            AuthEmailCode.used_at.is_(None),
        )
        .order_by(AuthEmailCode.id.desc())
        .first()
    )

    if not row:
        raise HTTPException(status_code=400, detail="Активный код не найден.")

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
        raise HTTPException(status_code=400, detail="Неверный код.")

    row.used_at = datetime.utcnow()
    row.is_active = False
    user.password_hash = hash_password(new_password)
    db.commit()

    return OkOut(ok=True, detail="Пароль успешно изменён.")