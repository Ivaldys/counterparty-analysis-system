from kivy.clock import Clock
from kivy.uix.screenmanager import Screen
import threading
import requests
import re

API_BASE_URL = "http://127.0.0.1:8000"
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


class VerifyEmailScreen(Screen):
    def set_message(self, text: str, kind: str = "error"):
        def _apply(dt):
            lbl = self.ids.get("verify_msg")
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

    def on_pre_enter(self, *args):
        self.set_message("", "error")

    def on_back(self):
        self.manager.current = "register"

    def on_confirm(self):
        email = (self.ids.verify_email.text or "").strip().lower()
        code = (self.ids.verify_code.text or "").strip()

        if not email or not EMAIL_RE.match(email):
            self.set_message("Введите корректную почту.", "error")
            return

        if not code:
            self.set_message("Введите код подтверждения.", "error")
            return

        self.set_message("Подтверждаем почту...", "info")
        threading.Thread(target=self._confirm_request, args=(email, code), daemon=True).start()

    def _confirm_request(self, email: str, code: str):
        try:
            r = requests.post(
                f"{API_BASE_URL}/auth/verify-email",
                json={"email": email, "code": code},
                timeout=10
            )

            if r.status_code != 200:
                detail = "Ошибка подтверждения"
                if r.headers.get("content-type", "").startswith("application/json"):
                    detail = r.json().get("detail", detail)
                self.set_message(detail, "error")
                return

            self.set_message("Почта подтверждена. Теперь войдите.", "success")
            Clock.schedule_once(lambda dt: setattr(self.manager, "current", "login"), 1.0)

        except Exception as e:
            self.set_message(f"Сервер недоступен: {e}", "error")