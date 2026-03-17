from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
import re
import threading
import requests

PASSWORD_MIN = 8
PASSWORD_MAX = 64

API_BASE_URL = "http://127.0.0.1:8000"
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+[1-9]\d{10,14}$")


def validate_password(password: str) -> str | None:
    if len(password) < PASSWORD_MIN:
        return f"Пароль минимум {PASSWORD_MIN} символов."
    if len(password) > PASSWORD_MAX:
        return f"Пароль максимум {PASSWORD_MAX} символов."
    if not re.search(r"[A-Za-zА-Яа-я]", password):
        return "Пароль должен содержать хотя бы одну букву."
    if not re.search(r"\d", password):
        return "Пароль должен содержать хотя бы одну цифру."
    if not re.search(r"[^\w\s]", password):
        return "Пароль должен содержать хотя бы один спецсимвол."
    return None


def validate_phone(phone: str) -> str | None:
    if not phone:
        return None
    if not PHONE_RE.match(phone):
        return "Телефон должен быть в формате +79991234567."
    return None


def validate_inn(company_inn: str) -> str | None:
    if not company_inn:
        return None
    if not company_inn.isdigit():
        return "ИНН должен содержать только цифры."
    if len(company_inn) not in (10, 12):
        return "ИНН должен содержать 10 или 12 цифр."
    return None


class RegisterScreen(Screen):
    def set_message(self, text: str, kind: str = "error"):
        def _apply(dt):
            lbl = self.ids.get("msg_label")
            if not lbl:
                return
            lbl.text = text
            if kind == "success":
                lbl.color = (0.15, 0.60, 0.20, 1)
            elif kind == "info":
                lbl.color = (0.25, 0.35, 0.70, 1)
            else:
                lbl.color = (0.85, 0.20, 0.20, 1)
        Clock.schedule_once(_apply, 0)

    def on_back(self):
        self.manager.current = "login"

    def on_submit(self):
        full_name = (self.ids.reg_full_name.text or "").strip()
        email = (self.ids.reg_email.text or "").strip().lower()
        password = self.ids.reg_password.text or ""
        phone = (self.ids.reg_phone.text or "").strip()
        company_name = (self.ids.reg_company_name.text or "").strip()
        company_inn = (self.ids.reg_company_inn.text or "").strip()

        self.set_message("", kind="error")

        if len(full_name) < 2:
            self.set_message("Введите корректное ФИО.", kind="error")
            return

        if not email or not EMAIL_RE.match(email):
            self.set_message("Введите корректную почту.", kind="error")
            return

        password_error = validate_password(password)
        if password_error:
            self.set_message(password_error, kind="error")
            return

        phone_error = validate_phone(phone)
        if phone_error:
            self.set_message(phone_error, kind="error")
            return

        inn_error = validate_inn(company_inn)
        if inn_error:
            self.set_message(inn_error, kind="error")
            return

        payload = {
            "full_name": full_name,
            "email": email,
            "password": password,
            "phone": phone or None,
            "company_name": company_name or None,
            "company_inn": company_inn or None,
        }

        self.set_message("Регистрируем и отправляем код...", kind="info")
        threading.Thread(target=self._register_request, args=(payload,), daemon=True).start()

    def _register_request(self, payload: dict):
        try:
            r = requests.post(f"{API_BASE_URL}/auth/register", json=payload, timeout=10)

            if r.status_code != 200:
                detail = "Ошибка регистрации"
                if r.headers.get("content-type", "").startswith("application/json"):
                    detail = r.json().get("detail", detail)
                self.set_message(detail, kind="error")
                return

            def apply_success(dt):
                self.ids.reg_password.text = ""
                self.set_message("Код подтверждения отправлен на почту.", kind="success")

                verify_screen = self.manager.get_screen("verify_email")
                verify_screen.ids.verify_email.text = payload["email"]

                self.manager.current = "verify_email"

            Clock.schedule_once(apply_success, 0)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.set_message(f"Ошибка: {e}", kind="error")