import requests
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.modalview import ModalView
from kivy.uix.screenmanager import Screen

from storage import load_token, clear_token

API_BASE_URL = "http://127.0.0.1:8000"


class EditProfilePopup(ModalView):
    pass


class ChangePasswordPopup(ModalView):
    pass


class ProfileScreen(Screen):
    current_profile = {}

    def on_pre_enter(self, *args):
        self.load_profile()

    def set_message(self, text: str, kind: str = "error"):
        lbl = self.ids.get("profile_msg")
        if not lbl:
            return

        if text is None:
            text = ""
        elif not isinstance(text, str):
            text = str(text)

        lbl.text = text

        if kind == "success":
            lbl.color = (0.15, 0.60, 0.20, 1)
        elif kind == "info":
            lbl.color = (0.25, 0.35, 0.70, 1)
        else:
            lbl.color = (0.85, 0.20, 0.20, 1)
    def _extract_error_text(self, response):
        try:
            data = response.json()
        except Exception:
            return "Неизвестная ошибка."

        detail = data.get("detail", "Неизвестная ошибка.")

        if isinstance(detail, str):
            return detail

        if isinstance(detail, list):
            parts = []
            for item in detail:
                if isinstance(item, dict):
                    msg = item.get("msg")
                    loc = item.get("loc")
                    if loc and msg:
                        parts.append(f"{'.'.join(map(str, loc))}: {msg}")
                    elif msg:
                        parts.append(msg)
                    else:
                        parts.append(str(item))
                else:
                    parts.append(str(item))
            return "\n".join(parts)

        return str(detail)
    def _auth_headers(self):
        token = load_token()
        if not token:
            return None
        return {"Authorization": f"Bearer {token}"}

    def load_profile(self):
        headers = self._auth_headers()
        if not headers:
            self.set_message("Не найден токен авторизации.", "error")
            return

        self.set_message("Загружаем профиль...", "info")

        def worker():
            try:
                r = requests.get(
                    f"{API_BASE_URL}/profile/me",
                    headers=headers,
                    timeout=10,
                )

                if r.status_code != 200:
                    detail = "Не удалось загрузить профиль."
                    try:
                        detail = r.json().get("detail", detail)
                    except Exception:
                        pass
                    Clock.schedule_once(lambda dt: self.set_message(detail, "error"), 0)
                    return

                data = r.json()
                self.current_profile = data

                def apply(dt):
                    self.ids.profile_name.text = f"ФИО: {data.get('full_name') or '—'}"
                    self.ids.profile_email.text = f"Почта: {data.get('email') or '—'}"
                    self.ids.profile_phone.text = f"Телефон: {data.get('phone') or '—'}"
                    self.ids.profile_company.text = f"Компания: {data.get('company_name') or '—'}"
                    self.ids.profile_inn.text = f"ИНН компании: {data.get('company_inn') or '—'}"
                    self.ids.profile_verified.text = (
                        "Почта подтверждена: Да" if data.get("email_verified") else "Почта подтверждена: Нет"
                    )
                    self.set_message("", "info")

                Clock.schedule_once(apply, 0)

            except Exception as e:
                Clock.schedule_once(
                    lambda dt: self.set_message(f"Ошибка загрузки профиля: {e}", "error"),
                    0
                )

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def open_edit_popup(self):
        popup = EditProfilePopup()

        popup.ids.edit_full_name.text = self.current_profile.get("full_name") or ""
        popup.ids.edit_phone.text = self.current_profile.get("phone") or ""
        popup.ids.edit_company_name.text = self.current_profile.get("company_name") or ""
        popup.ids.edit_company_inn.text = self.current_profile.get("company_inn") or ""

        popup.open()

    def save_profile(self, full_name: str, phone: str, company_name: str, company_inn: str, popup):
        headers = self._auth_headers()
        if not headers:
            self.set_message("Не найден токен авторизации.", "error")
            return

        payload = {
            "full_name": (full_name or "").strip(),
            "phone": (phone or "").strip() or None,
            "company_name": (company_name or "").strip() or None,
            "company_inn": (company_inn or "").strip() or None,
        }

        if len(payload["full_name"]) < 2:
            self.set_message("ФИО должно содержать минимум 2 символа.", "error")
            return

        self.set_message("Сохраняем профиль...", "info")

        def worker():
            try:
                r = requests.put(
                    f"{API_BASE_URL}/profile/me",
                    headers=headers,
                    json=payload,
                    timeout=10,
                )

                if r.status_code != 200:
                    detail = "Не удалось обновить профиль."
                    try:
                        detail = r.json().get("detail", detail)
                    except Exception:
                        pass
                    Clock.schedule_once(lambda dt: self.set_message(detail, "error"), 0)
                    return

                data = r.json()
                self.current_profile = data

                def apply(dt):
                    if popup:
                        popup.dismiss()

                    self.ids.profile_name.text = f"ФИО: {data.get('full_name') or '—'}"
                    self.ids.profile_email.text = f"Почта: {data.get('email') or '—'}"
                    self.ids.profile_phone.text = f"Телефон: {data.get('phone') or '—'}"
                    self.ids.profile_company.text = f"Компания: {data.get('company_name') or '—'}"
                    self.ids.profile_inn.text = f"ИНН компании: {data.get('company_inn') or '—'}"
                    self.ids.profile_verified.text = (
                        "Почта подтверждена: Да" if data.get("email_verified") else "Почта подтверждена: Нет"
                    )
                    self.set_message("Профиль успешно обновлён.", "success")

                Clock.schedule_once(apply, 0)

            except Exception as e:
                Clock.schedule_once(
                    lambda dt: self.set_message(f"Ошибка обновления профиля: {e}", "error"),
                    0
                )

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def open_password_popup(self):
        popup = ChangePasswordPopup()
        popup.open()

    def change_password(self, old_password: str, new_password: str, confirm_password: str, popup):
        headers = self._auth_headers()
        if not headers:
            self.set_message("Не найден токен авторизации.", "error")
            return

        old_password = old_password or ""
        new_password = new_password or ""
        confirm_password = confirm_password or ""

        if not old_password:
            self.set_message("Введите текущий пароль.", "error")
            return

        if len(new_password) < 8:
            self.set_message("Новый пароль должен содержать минимум 8 символов.", "error")
            return

        if new_password != confirm_password:
            self.set_message("Подтверждение пароля не совпадает.", "error")
            return

        self.set_message("Меняем пароль...", "info")

        payload = {
            "old_password": old_password,
            "new_password": new_password,
        }
        print("CHANGE PASSWORD PAYLOAD =", payload)
        def worker():
            try:
                r = requests.post(
                    f"{API_BASE_URL}/profile/change-password",
                    headers=headers,
                    json=payload,
                    timeout=10,
                )

                if r.status_code != 200:
                    detail = self._extract_error_text(r)
                    Clock.schedule_once(lambda dt: self.set_message(detail, "error"), 0)
                    return
                print("CHANGE PASSWORD STATUS =", r.status_code)
                print("CHANGE PASSWORD BODY =", r.text)
                def apply(dt):
                    if popup:
                        popup.dismiss()
                    self.set_message("Пароль успешно изменён.", "success")

                Clock.schedule_once(apply, 0)

            except Exception as e:
                Clock.schedule_once(
                    lambda dt: self.set_message(f"Ошибка смены пароля: {e}", "error"),
                    0
                )

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def logout(self):
        clear_token()
        self.current_profile = {}
        self.ids.profile_name.text = "ФИО: —"
        self.ids.profile_email.text = "Почта: —"
        self.ids.profile_phone.text = "Телефон: —"
        self.ids.profile_company.text = "Компания: —"
        self.ids.profile_inn.text = "ИНН компании: —"
        self.ids.profile_verified.text = "Почта подтверждена: —"
        self.set_message("", "info")
        self.manager.current = "login"