from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from db import get_db
from models.user import User
from schemas import ProfileResponse, ProfileUpdate, ChangePassword, OkOut
from security import verify_password, hash_password, decode_access_token

router = APIRouter(prefix="/profile", tags=["profile"])
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials

    try:
        payload = decode_access_token(token)
        user_id = payload.get("user_id")
    except Exception:
        raise HTTPException(status_code=401, detail="Неверный токен")

    if not user_id:
        raise HTTPException(status_code=401, detail="Неверный токен")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    return user


@router.get("/me", response_model=ProfileResponse)
def get_profile_me(current_user: User = Depends(get_current_user)):
    return ProfileResponse(
        full_name=current_user.full_name,
        email=current_user.email,
        phone=current_user.phone,
        company_name=current_user.company_name,
        company_inn=current_user.company_inn,
        email_verified=current_user.email_verified,
    )


@router.put("/me", response_model=ProfileResponse)
def update_profile_me(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.full_name = payload.full_name.strip()
    current_user.phone = (payload.phone or "").strip() or None
    current_user.company_name = (payload.company_name or "").strip() or None
    current_user.company_inn = (payload.company_inn or "").strip() or None

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return ProfileResponse(
        full_name=current_user.full_name,
        email=current_user.email,
        phone=current_user.phone,
        company_name=current_user.company_name,
        company_inn=current_user.company_inn,
        email_verified=current_user.email_verified,
    )


@router.post("/change-password", response_model=OkOut)
def change_password(
    payload: ChangePassword,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Текущий пароль неверный")

    if payload.old_password == payload.new_password:
        raise HTTPException(status_code=400, detail="Новый пароль должен отличаться от старого")

    current_user.password_hash = hash_password(payload.new_password)

    db.add(current_user)
    db.commit()

    return OkOut(ok=True, detail="Пароль успешно изменён")