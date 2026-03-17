import re
from fastapi import HTTPException

PHONE_RE = re.compile(r"^\+[1-9]\d{10,14}$")
PASSWORD_LETTER_RE = re.compile(r"[A-Za-zА-Яа-я]")
PASSWORD_DIGIT_RE = re.compile(r"\d")
PASSWORD_SPECIAL_RE = re.compile(r"[^\w\s]")


def validate_password_rules(password: str) -> None:
    if not PASSWORD_LETTER_RE.search(password):
        raise HTTPException(status_code=400, detail="Пароль должен содержать хотя бы одну букву.")
    if not PASSWORD_DIGIT_RE.search(password):
        raise HTTPException(status_code=400, detail="Пароль должен содержать хотя бы одну цифру.")
    if not PASSWORD_SPECIAL_RE.search(password):
        raise HTTPException(status_code=400, detail="Пароль должен содержать хотя бы один спецсимвол.")


def validate_phone(phone: str | None) -> None:
    if not phone:
        return
    if not PHONE_RE.fullmatch(phone):
        raise HTTPException(status_code=400, detail="Телефон должен быть в формате +79991234567.")


def validate_inn(inn: str | None) -> None:
    if not inn:
        return
    if not inn.isdigit():
        raise HTTPException(status_code=400, detail="ИНН должен содержать только цифры.")
    if len(inn) not in (10, 12):
        raise HTTPException(status_code=400, detail="ИНН должен содержать 10 или 12 цифр.")