from kivy.clock import Clock
from kivy.uix.screenmanager import Screen
from kivy.app import App
import threading
import requests
import re

API_BASE_URL = "http://127.0.0.1:8000"
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PASSWORD_MIN = 8
PASSWORD_MAX = 64


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


def _set_label(screen: Screen, label_id: str, text: str, ok: bool, info: bool = False):
    def _apply(dt):
        lbl = screen.ids.get(label_id)
        if not lbl:
            return
        lbl.text = text
        if info:
            lbl.color = (0.25, 0.35, 0.70, 1)
        else:
            lbl.color = (0.15, 0.60, 0.20, 1) if ok else (0.85, 0.20, 0.20, 1)
    Clock.schedule_once(_apply, 0)


class ForgotPasswordScreen(Screen):
    def on_back(self):
        self.manager.current = "login"

    def on_pre_enter(self, *args):
        _set_label(self, "forgot_msg", "", ok=False)

    def on_request_code(self):
        email = (self.ids.forgot_email.text or "").strip().lower()
        if not email or not EMAIL_RE.match(email):
            _set_label(self, "forgot_msg", "Введите корректную почту.", ok=False)
            return

        _set_label(self, "forgot_msg", "Отправляем код...", ok=False, info=True)
        threading.Thread(target=self._request_code, args=(email,), daemon=True).start()

    def _request_code(self, email: str):
        try:
            r = requests.post(f"{API_BASE_URL}/forgot/request", json={"email": email}, timeout=10)
            if r.status_code != 200:
                detail = "Ошибка отправки кода"
                if r.headers.get("content-type", "").startswith("application/json"):
                    detail = r.json().get("detail", detail)
                _set_label(self, "forgot_msg", detail, ok=False)
                return

            app = App.get_running_app()
            app.reset_email = email
            app.reset_code = None

            _set_label(self, "forgot_msg", "Код отправлен. Проверьте почту.", ok=True)
            Clock.schedule_once(lambda dt: setattr(self.manager, "current", "forgot_code"), 0.5)

        except Exception as e:
            _set_label(self, "forgot_msg", f"Сервер недоступен: {e}", ok=False)


class ForgotCodeScreen(Screen):
    def on_back(self):
        self.manager.current = "forgot_email"

    def on_pre_enter(self, *args):
        _set_label(self, "code_msg", "", ok=False)

    def on_confirm_code(self):
        code = (self.ids.code_input.text or "").strip()
        app = App.get_running_app()
        email = getattr(app, "reset_email", None)

        if not email:
            _set_label(self, "code_msg", "Сначала введите почту.", ok=False)
            self.manager.current = "forgot_email"
            return

        if not code:
            _set_label(self, "code_msg", "Введите код.", ok=False)
            return

        _set_label(self, "code_msg", "Проверяем код...", ok=False, info=True)
        threading.Thread(target=self._confirm_code, args=(email, code), daemon=True).start()

    def _confirm_code(self, email: str, code: str):
        try:
            r = requests.post(f"{API_BASE_URL}/forgot/confirm", json={"email": email, "code": code}, timeout=10)
            if r.status_code != 200:
                detail = "Неверный код"
                if r.headers.get("content-type", "").startswith("application/json"):
                    detail = r.json().get("detail", detail)
                _set_label(self, "code_msg", detail, ok=False)
                return

            app = App.get_running_app()
            app.reset_code = code

            _set_label(self, "code_msg", "Код подтверждён.", ok=True)
            Clock.schedule_once(lambda dt: setattr(self.manager, "current", "reset_password"), 0.5)

        except Exception as e:
            _set_label(self, "code_msg", f"Сервер недоступен: {e}", ok=False)


class ResetPasswordScreen(Screen):
    def on_back(self):
        self.manager.current = "forgot_code"

    def on_pre_enter(self, *args):
        _set_label(self, "reset_msg", "", ok=False)
        self.ids.new_pass.text = ""
        self.ids.new_pass2.text = ""

    def on_reset_password(self):
        p1 = self.ids.new_pass.text or ""
        p2 = self.ids.new_pass2.text or ""

        password_error = validate_password(p1)
        if password_error:
            _set_label(self, "reset_msg", password_error, ok=False)
            return

        if p1 != p2:
            _set_label(self, "reset_msg", "Пароли не совпадают.", ok=False)
            return

        app = App.get_running_app()
        email = getattr(app, "reset_email", None)
        code = getattr(app, "reset_code", None)

        if not email or not code:
            _set_label(self, "reset_msg", "Сначала подтвердите код.", ok=False)
            self.manager.current = "forgot_email"
            return

        _set_label(self, "reset_msg", "Меняем пароль...", ok=False, info=True)
        threading.Thread(target=self._reset_password, args=(email, code, p1), daemon=True).start()

    def _reset_password(self, email: str, code: str, new_password: str):
        try:
            r = requests.post(
                f"{API_BASE_URL}/forgot/reset",
                json={"email": email, "code": code, "new_password": new_password},
                timeout=10
            )
            if r.status_code != 200:
                detail = "Ошибка смены пароля"
                if r.headers.get("content-type", "").startswith("application/json"):
                    detail = r.json().get("detail", detail)
                _set_label(self, "reset_msg", detail, ok=False)
                return

            app = App.get_running_app()
            app.reset_email = None
            app.reset_code = None

            _set_label(self, "reset_msg", "Пароль изменён. Теперь войдите.", ok=True)
            Clock.schedule_once(lambda dt: setattr(self.manager, "current", "login"), 1.0)

        except Exception as e:
            _set_label(self, "reset_msg", f"Сервер недоступен: {e}", ok=False)