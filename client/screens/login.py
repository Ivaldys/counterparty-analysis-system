from kivy.uix.screenmanager import Screen
from kivy.properties import ObjectProperty
from kivy.clock import Clock
from kivy.app import App
import re
import threading
import requests
from storage import save_token
PASSWORD_MIN = 8
PASSWORD_MAX = 64

API_BASE_URL = "http://127.0.0.1:8000"
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

class LoginScreen(Screen):
    def set_message(self, text: str, kind: str = "error"):
        """
        kind:
        - error   -> красный
        - success -> зеленый
        - info    -> нейтральный
        """
        def _apply(dt):
            lbl = self.ids.get("login_msg_label")
            if not lbl:
                print("[LOGIN MSG]", text)
                return

            lbl.text = text

            if kind == "success":
                lbl.color = (0.15, 0.60, 0.20, 1)
            elif kind == "info":
                lbl.color = (0.25, 0.35, 0.70, 1)
            else:
                lbl.color = (0.85, 0.20, 0.20, 1)

        Clock.schedule_once(_apply, 0)

    def on_login(self, email: str, password: str):
        email = (email or "").strip()
        password = password or ""

        # очистим старое сообщение
        self.set_message("", kind="info")

        if not email:
            self.set_message("Введите почту.", kind="error")
            return
        if not password:
            self.set_message("Введите пароль.", kind="error")
            return
        if not EMAIL_RE.match(email):
            self.set_message("Некорректная почта.", kind="error")
            return
        if len(password) < PASSWORD_MIN:
            self.set_message(f"Пароль минимум {PASSWORD_MIN} символов.", kind="error")
            return
        if len(password) > PASSWORD_MAX:
            self.set_message(f"Пароль максимум {PASSWORD_MAX} символов.", kind="error")
            return

        self.set_message("Входим...", kind="info")

        threading.Thread(
            target=self._login_request,
            args=(email, password),
            daemon=True
        ).start()

    def _login_request(self, email: str, password: str):
        try:
            r = requests.post(
                f"{API_BASE_URL}/auth/login",
                json={"email": email, "password": password},
                timeout=10
            )

            if r.status_code != 200:
                detail = "Ошибка входа"
                if r.headers.get("content-type", "").startswith("application/json"):
                    detail = r.json().get("detail", detail)
                self.set_message(detail, kind="error")
                return

            data = r.json()
            token = data.get("access_token")


            if not token:
                self.set_message("Сервер не вернул токен.", kind="error")
                return

            # ✅ успех
            self.set_message("Успешный вход!", kind="success")
            save_token(token)
            print("[LOGIN OK] token =", token)
            Clock.schedule_once(lambda dt: setattr(self.manager, "current", "home"), 0.8)

        except Exception as e:
            self.set_message(f"Сервер недоступен: {e}", kind="error")

    def on_forgot_password(self):
        self.manager.current = "forgot_email"
        print("[FORGOT] clicked")

    def on_register(self):
        self.manager.current = "register"

    def on_exit(self):
        App.get_running_app().stop()
