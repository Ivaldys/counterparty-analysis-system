import bcrypt
import secrets
import hashlib
from jose import jwt, JWTError

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from db import get_db
from models.user import User

RESET_CODE_TTL_MIN = 10
SECRET_KEY = "CHANGE_ME_SUPER_SECRET"
ALGORITHM = "HS256"

bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def gen_6digit_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def hash_code(user_id: int, code: str) -> str:
    raw = f"{user_id}:{code}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def create_access_token(user_id: int) -> str:
    payload = {"user_id": user_id}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials

    try:
        payload = decode_access_token(token)
        user_id = payload.get("user_id")
    except JWTError:
        raise HTTPException(status_code=401, detail="Недействительный токен.")

    if not user_id:
        raise HTTPException(status_code=401, detail="Некорректный токен.")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден или неактивен.")

    return user