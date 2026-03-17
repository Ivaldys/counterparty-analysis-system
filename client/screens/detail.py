from pathlib import Path
import threading
import requests
import webbrowser
import os
from kivy.clock import Clock
from kivy.uix.modalview import ModalView
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from datetime import date, datetime
from storage import load_token
from services.egrul_loader import get_pdf_by_inn
from services.egrul_parser import parse_egrul_pdf

API_BASE_URL = "http://127.0.0.1:8000"



class ReviewPopup(ModalView):
    detail_screen = None

    def on_save(self):
        if not self.detail_screen:
            print("ReviewPopup: detail_screen is None")
            return

        self.detail_screen.save_review(
            self.ids.review_verdict.text,
            self.ids.review_rating.text,
            self.ids.review_text.text,
            self.ids.review_anonymous.active,
            self,
        )

class DetailScreen(Screen):
    current_data = {}
    db_data = {}
    egrul_data = {}
    pdf_path = None
    counterparty_id = None
    def _format_review_datetime(self, value):
        if value is None:
            return "—"

        text = str(value).strip()
        if not text or text in {"None", "nan", "<NA>"}:
            return "—"

        try:
            # 2026-03-16T16:55:38.278382+03:00
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt.strftime("%d.%m.%Y")
        except Exception:
            pass

        try:
            # 2026-03-16
            d = date.fromisoformat(text[:10])
            return d.strftime("%d.%m.%Y")
        except Exception:
            return text

    def _json_safe(self, value):
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return value

    def _auth_headers(self):
        token = load_token()
        if not token:
            return None
        return {"Authorization": f"Bearer {token}"}
    def _format_value(self, value):
        if value is None:
            return "—"

        text = str(value).strip()

        if text in {"", "None", "nan", "<NA>"}:
            return "—"

        if text.endswith(" 00:00:00"):
            return text[:10]

        return text

    def _format_number(self, value):
        if value is None:
            return "—"

        try:
            num = float(value)
            return f"{num:,.2f}".replace(",", " ").replace(".00", "")
        except Exception:
            return self._format_value(value)

    def set_data(self, data: dict):
        self.current_data = data or {}
        self.db_data = {}
        self.egrul_data = {}
        self.pdf_path = None
        self.counterparty_id = None

        self.ids.detail_status.text = ""
        self.ids.egrul_flags_label.text = "Флаги ЕГРЮЛ: не выявлены"

        if "reviews_status" in self.ids:
            self.ids.reviews_status.text = ""
        if "reviews_container" in self.ids:
            self.ids.reviews_container.clear_widgets()

        self._render()
        self.load_counterparty_from_backend()

    def _safe_set_status(self, text: str):
        self.ids.detail_status.text = str(text or "")

    def _safe_set_reviews_status(self, text: str):
        if "reviews_status" in self.ids:
            self.ids.reviews_status.text = str(text or "")

    def _get_counterparty_id(self):
        return (
            self.counterparty_id
            or self.current_data.get("counterparty_id")
            or self.current_data.get("id")
        )

    def render_reviews(self, items: list):
        container = self.ids.get("reviews_container")
        if container is None:
            return

        container.clear_widgets()

        if not items:
            self._safe_set_reviews_status("Отзывов пока нет.")
            return

        self._safe_set_reviews_status(f"Всего отзывов: {len(items)}")

        for item in items:
            author_name = item.get("author_name") or "Анонимный пользователь"
            author_company = item.get("author_company") or "—"
            author_inn = item.get("author_inn") or "—"
            rating = item.get("rating") or "—"
            verdict = item.get("verdict") or "—"
            review_text = item.get("review_text") or "Без текста"
            updated_at = self._format_review_datetime(item.get("updated_at"))

            card = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                height=dp(180),
                padding=dp(12),
                spacing=dp(8),
            )

            with card.canvas.before:
                Color(0.98, 0.98, 0.99, 1)
                card._bg_rect = RoundedRectangle(pos=card.pos, size=card.size, radius=[12])

            def update_bg(instance, *args):
                instance._bg_rect.pos = instance.pos
                instance._bg_rect.size = instance.size

            card.bind(pos=update_bg, size=update_bg)

            header = Label(
                text=str(author_name),
                size_hint_y=None,
                height=dp(24),
                bold=True,
                color=(0.12, 0.12, 0.15, 1),
                halign="left",
                valign="middle",
            )
            header.bind(size=lambda inst, size: setattr(inst, "text_size", size))

            company = Label(
                text=f"Компания: {author_company} | ИНН: {author_inn}",
                size_hint_y=None,
                height=dp(22),
                color=(0.35, 0.35, 0.40, 1),
                halign="left",
                valign="middle",
            )
            company.bind(size=lambda inst, size: setattr(inst, "text_size", size))

            meta = Label(
                text=f"Рейтинг: {rating} | Вердикт: {verdict} | Дата: {updated_at}",
                size_hint_y=None,
                height=dp(22),
                color=(0.20, 0.20, 0.24, 1),
                halign="left",
                valign="middle",
            )
            meta.bind(size=lambda inst, size: setattr(inst, "text_size", size))

            body = Label(
                text=str(review_text),
                color=(0.15, 0.15, 0.18, 1),
                halign="left",
                valign="top",
            )
            body.bind(size=lambda inst, size: setattr(inst, "text_size", size))

            card.add_widget(header)
            card.add_widget(company)
            card.add_widget(meta)
            card.add_widget(body)

            container.add_widget(card)

    def load_reviews(self):
        counterparty_id = self._get_counterparty_id()
        if not counterparty_id:
            self._safe_set_reviews_status("Не найден id контрагента.")
            return

        self._safe_set_reviews_status("Загружаем отзывы...")

        def worker():
            try:
                r = requests.get(
                    f"{API_BASE_URL}/counterparties/{counterparty_id}/reviews",
                    headers=self._auth_headers(),
                    timeout=10,
                )

                if r.status_code != 200:
                    Clock.schedule_once(
                        lambda dt: self._safe_set_reviews_status("Не удалось загрузить отзывы."),
                        0
                    )
                    return

                data = r.json()
                items = data.get("items", [])

                Clock.schedule_once(lambda dt: self.render_reviews(items), 0)

            except Exception as e:
                Clock.schedule_once(
                    lambda dt: self._safe_set_reviews_status(f"Ошибка загрузки отзывов: {e}"),
                    0
                )

        threading.Thread(target=worker, daemon=True).start()

    def open_review_popup(self):
        popup = ReviewPopup()
        popup.detail_screen = self

        user_data = (self.db_data or {}).get("user_data") or {}

        popup.ids.review_verdict.text = str(user_data.get("verdict") or "unknown")
        popup.ids.review_rating.text = str(user_data.get("rating") or "5")
        popup.ids.review_text.text = str(user_data.get("review_text") or "")
        popup.ids.review_anonymous.active = bool(user_data.get("is_anonymous") or False)

        popup.open()

    def load_counterparty_from_backend(self):
        inn = str(self.current_data.get("ИНН", "")).strip()
        headers = self._auth_headers()

        if not inn or not headers:
            return

        def worker():
            try:
                r = requests.get(
                    f"{API_BASE_URL}/counterparties/by-inn/{inn}",
                    headers=headers,
                    timeout=10,
                )

                if r.status_code != 200:
                    return

                data = r.json()

                def apply(dt):
                    self.db_data = data or {}
                    cp = self.db_data.get("counterparty") or {}
                    self.counterparty_id = cp.get("id")
                    self._render()
                    self.load_reviews()

                Clock.schedule_once(apply, 0)

            except Exception as e:
                print("DETAIL LOAD ERROR:", e)

        threading.Thread(target=worker, daemon=True).start()

    def save_review(self, verdict_text, rating_text, review_text, is_anonymous, popup):
        counterparty_id = self._get_counterparty_id()
        if not counterparty_id:
            self._safe_set_status("Не найден id контрагента.")
            return

        try:
            rating = int(rating_text)
        except Exception:
            self._safe_set_status("Некорректный рейтинг.")
            return

        payload = {
            "verdict": verdict_text,
            "rating": rating,
            "review_text": (review_text or "").strip() or None,
            "is_anonymous": bool(is_anonymous),
        }

        self._safe_set_status("Сохраняем отзыв...")

        def worker():
            try:
                r = requests.put(
                    f"{API_BASE_URL}/counterparties/{counterparty_id}/review",
                    headers=self._auth_headers(),
                    json=payload,
                    timeout=10,
                )

                if r.status_code != 200:
                    try:
                        detail = r.json().get("detail", "Не удалось сохранить отзыв.")
                    except Exception:
                        detail = "Не удалось сохранить отзыв."

                    Clock.schedule_once(lambda dt: self._safe_set_status(detail), 0)
                    return

                def apply(dt):
                    if popup:
                        popup.dismiss()

                    self._safe_set_status("Отзыв сохранён.")

                    # ВАЖНО: не затираем self.db_data ответом review-роута
                    self.load_counterparty_from_backend()
                    self.load_reviews()

                Clock.schedule_once(apply, 0)

            except Exception as e:
                Clock.schedule_once(
                    lambda dt: self._safe_set_status(f"Ошибка сохранения отзыва: {e}"),
                    0
                )

        threading.Thread(target=worker, daemon=True).start()

    def load_egrul_data(self):
        inn = str(self.current_data.get("ИНН", "")).strip()

        if not inn or inn in {"—", "nan", "None", "<NA>"}:
            self._safe_set_status("Не найден корректный ИНН.")
            return

        try:
            self._safe_set_status("Загружается выписка ЕГРЮЛ...")

            out_dir = Path("downloads")
            out_dir.mkdir(exist_ok=True)

            pdf_path = out_dir / f"egrul_{inn}.pdf"
            self.pdf_path = get_pdf_by_inn(inn, str(pdf_path))
            self.egrul_data = parse_egrul_pdf(self.pdf_path)

            self._safe_set_status("Данные ЕГРЮЛ успешно загружены.")
            self._render()

        except Exception as e:
            self._safe_set_status(f"Ошибка загрузки ЕГРЮЛ: {e}")

    def download_pdf(self):
        if self.pdf_path:
            self._safe_set_status(f"PDF сохранён: {self.pdf_path}")
            webbrowser.open(f"file://{os.path.abspath(self.pdf_path)}")
        else:
            self._safe_set_status("Сначала загрузите данные ЕГРЮЛ.")

    def _render(self):
        cp = self.db_data.get("counterparty") or {}
        user_data = self.db_data.get("user_data") or {}
        agg = self.db_data.get("agg") or {}

        title = (
            cp.get("name")
            or self.current_data.get("Название компании")
            or cp.get("full_name")
            or "Карточка контрагента"
        )

        self.ids.detail_title.text = self._format_title(title)

        self._render_main_info(cp, user_data, agg)
        self._render_egrul_info()
        self._render_flags()

    def _format_title(self, value):
        text = str(value or "").strip()
        if not text:
            return "Карточка контрагента"

        text = " ".join(text.split())
        return text

    def _render_main_info(self, cp: dict, user_data: dict, agg: dict):
        container = self.ids.main_info_grid
        container.clear_widgets()

        pairs = [
            ("ИНН", self._format_value(cp.get("inn") or self.current_data.get("ИНН"))),
            ("КПП", self._format_value(cp.get("kpp"))),
            ("ОГРН", self._format_value(cp.get("ogrn"))),
            ("Статус", self._format_value(cp.get("status"))),
            ("Дата регистрации", self._format_value(cp.get("reg_date"))),
            ("Адрес", self._format_value(cp.get("address"))),
            ("ОКВЭД", self._format_value(cp.get("okved_main"))),
            ("Руководитель", self._format_value(cp.get("ceo_name"))),
            ("Сумма начислений", self._format_number(self.current_data.get("Сумма начислений"))),
            ("Дата первого контракта", self._format_value(user_data.get("first_contract_date") or self.current_data.get("Дата первого контракта"))),
            ("Пользовательский вердикт", self._format_value(user_data.get("verdict"))),
            ("Средний рейтинг", self._format_value(agg.get("avg_rating"))),
            ("Число отзывов", self._format_value(agg.get("reviews_count"))),
            ("Процент доходов", self._format_value(self.current_data.get("Процент доходов"))),
            ("Разница дат в днях", self._format_value(self.current_data.get("Разница дат в днях"))),
            ("Доход на сотрудника", self._format_number(self.current_data.get("Доход на сотрудника"))),
            ("Критерий: Процент дохода", self._format_value(self.current_data.get("Критерий: Процент дохода"))),
            ("Критерий: Разница дат", self._format_value(self.current_data.get("Критерий: Разница дат"))),
            ("Критерий: доход/сотрудник", self._format_value(self.current_data.get("Критерий: доход/сотрудник"))),
            ("Итоговая подозрительность", self._format_value(self.current_data.get("Итоговая подозрительность"))),
            ("Ваш рейтинг", self._format_value(user_data.get("rating"))),
            ("Ваш отзыв", self._format_value(user_data.get("review_text"))),
        ]

        self._fill_pairs_grid(container, pairs)

    def _render_egrul_info(self):
        container = self.ids.egrul_info_grid
        container.clear_widgets()

        pairs = [
            ("ОГРН", self.egrul_data.get("ОГРН", "—")),
            ("Дата регистрации", self.egrul_data.get("Дата регистрации", "—")),
            ("Регистрирующий орган", self.egrul_data.get("Регистрирующий орган", "—")),
            ("Руководитель", self.egrul_data.get("Руководитель", "—")),
            ("Должность", self.egrul_data.get("Должность", "—")),
            ("Уставный капитал", self.egrul_data.get("Уставный капитал", "—")),
            ("Количество изменений", self.egrul_data.get("Количество изменений", "—")),
            ("Есть реорганизация", "Да" if self.egrul_data.get("Есть реорганизация") else "Нет"),
            ("Есть исправления", "Да" if self.egrul_data.get("Есть исправления") else "Нет"),
            ("Риск ЕГРЮЛ", self.egrul_data.get("Риск ЕГРЮЛ", "—")),
        ]

        self._fill_pairs_grid(container, pairs)
    def load_ai_summary(self):
        counterparty_id = self._get_counterparty_id()
        if not counterparty_id:
            self._safe_set_status("Не найден id контрагента.")
            return

        self._safe_set_status("Генерируем AI-анализ...")

        def worker():
            try:
                raw_first_contract_date = self.current_data.get("Дата первого контракта")

                if hasattr(raw_first_contract_date, "isoformat"):
                    first_contract_date = raw_first_contract_date.isoformat()
                else:
                    first_contract_date = raw_first_contract_date

                payload = {
                    "total_paid": self._json_safe(self.current_data.get("Сумма начислений")),
                    "first_contract_date": self._json_safe(self.current_data.get("Дата первого контракта")),
                    "income_2024": self._json_safe(self.current_data.get("Доход в 2024")),
                    "staff_count": self._json_safe(self.current_data.get("Количество сотрудников")),
                    "income_share": self._json_safe(self.current_data.get("Процент доходов")),
                    "date_diff_days": self._json_safe(self.current_data.get("Разница дат в днях")),
                    "income_per_staff": self._json_safe(self.current_data.get("Доход на сотрудника")),
                    "final_score": self._json_safe(self.current_data.get("Итоговая подозрительность")),
                    "egrul_flags": self.egrul_data.get("Флаги ЕГРЮЛ", []),
                    "egrul_risk": self._json_safe(self.egrul_data.get("Риск ЕГРЮЛ")),
                }
                print("AI PAYLOAD =", payload)
                r = requests.post(
                    f"{API_BASE_URL}/counterparties/{counterparty_id}/ai-summary",
                    headers=self._auth_headers(),
                    json=payload,
                    timeout=60,
                )
                if r.status_code != 200:
                    try:
                        detail = r.json().get("detail", "Не удалось получить AI-анализ.")
                    except Exception:
                        detail = "Не удалось получить AI-анализ."

                    Clock.schedule_once(lambda dt: self._safe_set_status(detail), 0)
                    return

                data = r.json()
                summary = data.get("summary") or "Пустой ответ."

                def apply(dt):
                    self.ids.ai_summary_label.text = summary
                    self._safe_set_status("AI-анализ готов.")

                Clock.schedule_once(apply, 0)

            except Exception as e:
                err_text = f"Ошибка AI-анализа: {e}"
                Clock.schedule_once(lambda dt: self._safe_set_status(err_text), 0)

        threading.Thread(target=worker, daemon=True).start()
    def _render_flags(self):
        flags_label = self.ids.egrul_flags_label
        flags = self.egrul_data.get("Флаги ЕГРЮЛ", [])

        if not flags:
            flags_label.text = "Флаги ЕГРЮЛ: не выявлены"
            return

        if isinstance(flags, str):
            flags_label.text = f"Флаги ЕГРЮЛ: {flags}"
            return

        flags_label.text = "Флаги ЕГРЮЛ: " + "; ".join(map(str, flags))

    def _fill_pairs_grid(self, container, pairs):
        for key, value in pairs:
            left = Label(
                text=str(key),
                color=(0.30, 0.30, 0.35, 1),
                bold=True,
                halign="left",
                valign="middle",
                size_hint_y=None,
                height=42,
            )
            left.bind(size=lambda instance, size: setattr(instance, "text_size", size))

            right = Label(
                text=str(value),
                color=(0.12, 0.12, 0.15, 1),
                halign="left",
                valign="middle",
                size_hint_y=None,
                height=42,
            )
            right.bind(size=lambda instance, size: setattr(instance, "text_size", size))

            container.add_widget(left)
            container.add_widget(right)

    def _fill_review_fields(self):
        pass