import math
import pandas as pd
from kivy.app import App
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ObjectProperty, StringProperty, DictProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
import requests
from tqdm import tqdm
from models.popups import UploadPopup, InnDirectoryPopup
from services.file_loader import try_read_table, prepare_dataframe_from_start_row
from services.inn_directory import prepare_inn_directory
from services.operations_processing import process_operations_card
from services.preview_builder import fill_preview_table
from utils.parse_utils import parse_start_row, parse_delete_rows, parse_delete_cols
from utils.text_utils import safe_text
from kivy.uix.gridlayout import GridLayout
from kivy.graphics import Color, RoundedRectangle
import numpy as np
import xlrd, xlsxwriter
import re
from storage import load_token
from kivy.uix.behaviors import ButtonBehavior
from threading import Thread
from kivy.clock import Clock
from kivy.uix.modalview import ModalView
from kivy.properties import ListProperty, DictProperty

BASE_URL = "http://127.0.0.1:8000"

class ClickableRow(ButtonBehavior, GridLayout):
    pass
class WeightsPopup(ModalView):
    pass

class SortPopup(ModalView):
    pass

class FilterPopup(ModalView):
    pass

class MainScreen(Screen):
    operations_raw_df = ObjectProperty(None, rebind=True)
    operations_df = ObjectProperty(None, rebind=True)
    inn_raw_df = ObjectProperty(None, rebind=True)
    inn_df = ObjectProperty(None, rebind=True)
    processed_df = ObjectProperty(None, rebind=True)
    raw_df = ObjectProperty(None, rebind=True)
    hide_sensitive = BooleanProperty(True)
    current_entity_filter = StringProperty("all")
    dashboard_stats = DictProperty({})
    COL_WIDTH = dp(180)
    ROW_HEIGHT = dp(52)
    HEADER_HEIGHT = dp(42)
    TABLE_SPACING = dp(6)
    weight_income_staff = 20
    weight_income_diff = 40
    weight_date_diff = 40
    current_sort = DictProperty({})
    current_filters = ListProperty([])

    def on_pre_enter(self, *args):
        self.set_message("")
        self._calculate_dashboard_stats()
        self._render_dashboard_stats()
        self.refresh_table()

    def _auth_headers(self):
        token = load_token()
        if not token:
            return None
        return {"Authorization": f"Bearer {token}"}

    def _format_date_value(self, value):
        if value is None or value == "" or pd.isna(value):
            return "—"

        try:
            dt = pd.to_datetime(value, errors="coerce")
            if pd.isna(dt):
                return str(value)
            return dt.strftime("%d.%m.%Y")
        except Exception:
            return str(value)
    def get_sortable_columns(self):
        if self.processed_df is None or self.processed_df.empty:
            return []

        preferred = [
            "Название компании",
            "ИНН",
            "Сумма начислений",
            "Дата первого контракта",
            "Доход в 2024",
            "Количество сотрудников",
            "Дата регистрации",
            "Процент доходов",
            "Разница дат в днях",
            "Доход на сотрудника",
            "Итоговая подозрительность",
        ]
        return [c for c in preferred if c in self.processed_df.columns]
    def _format_number_value(self, value, decimals=2, strip_zeros=True):
        if value is None or value == "" or pd.isna(value):
            return "—"

        try:
            num = float(value)

            if math.isclose(num, round(num), rel_tol=0, abs_tol=1e-9):
                return f"{int(round(num)):,}".replace(",", " ")

            text = f"{num:,.{decimals}f}".replace(",", " ")

            if strip_zeros:
                text = text.rstrip("0").rstrip(".")

            return text
        except Exception:
            return str(value)
    def _get_column_type(self, column_name: str) -> str:
        numeric_cols = {
            "Сумма начислений",
            "Доход в 2024",
            "Количество сотрудников",
            "Процент доходов",
            "Разница дат в днях",
            "Доход на сотрудника",
            "Итоговая подозрительность",
            "Критерий: Процент дохода",
            "Критерий: Разница дат",
            "Критерий: доход/сотрудник",
            "Кредит в 2023",
            "Кредит в 2024",
            "Кредит в 2025",
        }

        date_cols = {
            "Дата первого контракта",
            "Дата регистрации",
        }

        if column_name in numeric_cols:
            return "number"
        if column_name in date_cols:
            return "date"
        return "text"

    def _get_filter_operators_for_column(self, column_name: str) -> list[str]:
        col_type = self._get_column_type(column_name)

        if col_type == "text":
            return ["содержит", "равно", "пусто", "не пусто"]

        if col_type in {"number", "date"}:
            return [">=", "<=", "между", "равно", "пусто", "не пусто"]

        return ["содержит", "равно"]
    def _detect_entity_type(self, row):
        name = str(row.get("Название компании") or "").strip().lower()
        inn = str(row.get("ИНН") or "").strip()

        if not inn:
            return "Неизвестно"

        if len(inn) == 12:
            return "ИП / самозанятые"

        return "Юрлица"
    def update_filter_popup_state(self, popup, column_name: str):
        if not popup:
            return

        operators = self._get_filter_operators_for_column(column_name)
        popup.ids.filter_operator.values = operators
        popup.ids.filter_operator.text = operators[0] if operators else ""

        col_type = self._get_column_type(column_name)

        hint1 = "Введите значение"
        hint2 = "Введите второе значение"

        if col_type == "number":
            hint1 = "Например: 100000"
            hint2 = "Например: 500000"
        elif col_type == "date":
            hint1 = "Например: 2024-01-01"
            hint2 = "Например: 2024-12-31"
        elif col_type == "text":
            hint1 = "Введите текст"
            hint2 = "Для текста обычно не нужно"

        popup.ids.filter_value1.hint_text = hint1
        popup.ids.filter_value2.hint_text = hint2

        operator = popup.ids.filter_operator.text
        popup.ids.filter_value2.disabled = operator != "между"
        popup.ids.filter_value2.opacity = 1 if operator == "между" else 0.5

    def _enrich_entity_types(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        df = df.copy()

        if "Тип контрагента" not in df.columns:
            df["Тип контрагента"] = df.apply(self._detect_entity_type, axis=1)

        return df

    def _get_filtered_df(self, df: pd.DataFrame | None = None) -> pd.DataFrame:
        if df is None:
            df = self.processed_df

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()

        filter_map = {
            "all": None,
            "legal": "Юрлица",
            "ip": "ИП / самозанятые",
        }

        target = filter_map.get(self.current_entity_filter)

        if target is None:
            return df

        if "Тип контрагента" not in df.columns:
            return df

        return df[df["Тип контрагента"] == target].copy()

    def _calculate_dashboard_stats(self):
        df = self.processed_df

        if df is None or df.empty:
            self.dashboard_stats = {
                "total": 0,
                "legal": 0,
                "ip": 0,
                "avg_risk": "—",
                "high_risk": 0,
                "missing_data": 0,
            }
            return

        df = df.copy()

        if "Тип контрагента" not in df.columns:
            df = self._enrich_entity_types(df)

        total = len(df)
        legal_count = int((df["Тип контрагента"] == "Юрлица").sum())
        ip_count = int((df["Тип контрагента"] == "ИП / самозанятые").sum())

        risk_series = pd.to_numeric(df.get("Итоговая подозрительность"), errors="coerce")
        avg_risk = risk_series.mean()
        high_risk = int((risk_series >= 3.5).sum()) if not risk_series.empty else 0

        missing_cols = [
            c for c in ["Доход в 2024", "Количество сотрудников", "Дата регистрации"]
            if c in df.columns
        ]
        if missing_cols:
            missing_data = int(df[missing_cols].isna().any(axis=1).sum())
        else:
            missing_data = 0

        self.dashboard_stats = {
            "total": total,
            "legal": legal_count,
            "ip": ip_count,
            "avg_risk": "—" if pd.isna(avg_risk) else f"{avg_risk:.2f}",
            "high_risk": high_risk,
            "missing_data": missing_data,
        }

    def _render_dashboard_stats(self):
        stats = self.dashboard_stats or {}

        mapping = {
            "stat_total": stats.get("total", 0),
            "stat_legal": stats.get("legal", 0),
            "stat_ip": stats.get("ip", 0),
            "stat_avg_risk": stats.get("avg_risk", "—"),
            "stat_high_risk": stats.get("high_risk", 0),
            "stat_missing": stats.get("missing_data", 0),
        }

        for widget_id, value in mapping.items():
            if widget_id in self.ids:
                self.ids[widget_id].text = str(value)

    def set_entity_filter(self, filter_value: str):
        self.current_entity_filter = filter_value
        self.refresh_table()

        buttons = {
            "all": "tab_all",
            "legal": "tab_legal",
            "ip": "tab_ip",
        }

        for key, btn_id in buttons.items():
            if btn_id in self.ids:
                self.ids[btn_id].state = "down" if key == filter_value else "normal"
    def _format_cell_value(self, col_name, value):
        date_cols = {
            "Дата первого контракта",
            "Дата регистрации",
        }

        int_like_cols = {
            "Количество сотрудников",
            "Кредит в 2023",
            "Кредит в 2024",
            "Кредит в 2025",
        }

        money_like_cols = {
            "Сумма начислений",
            "Доход в 2024",
            "Доход на сотрудника",
        }

        score_like_cols = {
            "Итоговая подозрительность",
            "Процент доходов",
            "Разница дат в днях",
            "Критерий: Процент дохода",
            "Критерий: Разница дат",
            "Критерий: доход/сотрудник",
        }

        if col_name in date_cols:
            return self._format_date_value(value)

        if col_name in int_like_cols:
            return self._format_number_value(value, decimals=0)

        if col_name in money_like_cols:
            return self._format_number_value(value, decimals=2)

        if col_name in score_like_cols:
            return self._format_number_value(value, decimals=2)

        return safe_text(value)

    def sync_counterparties_to_backend(self, final_df: pd.DataFrame):
        headers = self._auth_headers()
        if not headers:
            self.set_progress_message("Не найден токен. Сохранение контрагентов в БД пропущено.", error=True)
            return

        session = requests.Session()
        session.headers.update(headers)

        for _, row in final_df.iterrows():
            try:
                payload = {
                    "inn": str(row.get("ИНН") or "").strip(),
                    "name": row.get("Название компании"),
                    "total_paid": float(row["Сумма начислений"]) if pd.notna(row.get("Сумма начислений")) else None,
                    "tx_count": None,
                    "first_contract_date": str(row.get("Дата первого контракта")) if pd.notna(row.get("Дата первого контракта")) else None,
                    "last_contract_date": None,
                    "active_months_count": None,
                    "verdict": "suspicious" if pd.notna(row.get("Итоговая подозрительность")) and float(row["Итоговая подозрительность"]) >= 3 else "ok",
                }

                if not payload["inn"]:
                    continue

                r = session.post(
                    f"{BASE_URL}/counterparties/upsert-me",
                    json=payload,
                    timeout=15,
                )
                r.raise_for_status()

            except Exception as e:
                print("SYNC COUNTERPARTY ERROR:", e)
    def set_message(self, text: str, error: bool = True):
        lbl = self.ids.get("main_msg")
        if lbl:
            lbl.text = text
            lbl.color = (0.85, 0.20, 0.20, 1) if error else (0.15, 0.55, 0.20, 1)

    def on_search(self, text: str):
        self.refresh_table(search_text=text)
    def set_progress_message(self, text: str, error: bool = False):
        Clock.schedule_once(lambda dt: self.set_message(text, error=error), 0)

    def refresh_table_safe(self):
        Clock.schedule_once(lambda dt: self.refresh_table(), 0)
    def on_profile(self):
        self.manager.current = "profile"

    def open_weights_popup(self):
        popup = WeightsPopup()
        popup.ids.weight_income_staff_input.text = str(self.weight_income_staff)
        popup.ids.weight_income_diff_input.text = str(self.weight_income_diff)
        popup.ids.weight_date_diff_input.text = str(self.weight_date_diff)
        popup.open()

    def apply_weights(self, income_staff_text, income_diff_text, date_diff_text, popup):
        try:
            w1 = float(income_staff_text.replace(",", "."))
            w2 = float(income_diff_text.replace(",", "."))
            w3 = float(date_diff_text.replace(",", "."))
            total = w1 + w2 + w3
            if abs(total - 100.0) > 0.001:
                self.set_message("Сумма весов должна быть равна 100.", error=True)
                return
            self.weight_income_staff = w1
            self.weight_income_diff = w2
            self.weight_date_diff = w3
            if popup:
                popup.dismiss()
            self.set_message(
                f"Новые веса сохранены: доход/сотрудник={w1}%, разница доходов={w2}%, разница дат={w3}%",
                error=False
            )
            self.recalculate_scores()
        except Exception:
            self.set_message("Введите корректные числовые веса.", error=True)

    def recalculate_scores(self):
        if self.processed_df is None or self.processed_df.empty:
            return
        df = self.processed_df.copy()
        needed_cols = [
            "Критерий: доход/сотрудник",
            "Критерий: Процент дохода",
            "Критерий: Разница дат",
        ]
        if not all(col in df.columns for col in needed_cols):
            self.refresh_table()
            return
        weights = {
            "Критерий: доход/сотрудник": self.weight_income_staff / 100.0,
            "Критерий: Процент дохода": self.weight_income_diff / 100.0,
            "Критерий: Разница дат": self.weight_date_diff / 100.0,
        }
        def total_suspicion(row):
            total_score = 0.0
            weight_sum = 0.0
            for col, w in weights.items():
                val = row[col]
                if isinstance(val, (int, float)) and not pd.isna(val):
                    total_score += val * w
                    weight_sum += w
            if weight_sum == 0:
                return np.nan
            return total_score / weight_sum
        df["Итоговая подозрительность"] = df.apply(total_suspicion, axis=1)
        df = df.sort_values(by="Итоговая подозрительность", ascending=False, na_position="last")
        self.processed_df = df
        self.refresh_table()

    def on_filter(self):
        if self.processed_df is None or self.processed_df.empty:
            self.set_message("Сначала загрузите файл.")
            return

        popup = FilterPopup()
        columns = self.get_sortable_columns()

        popup.ids.filter_column.values = columns
        popup.ids.filter_column.text = columns[0] if columns else ""

        if columns:
            self.update_filter_popup_state(popup, columns[0])

        popup.open()

    def on_filter_operator_change(self, popup, operator_text: str):
        if not popup:
            return

        popup.ids.filter_value2.disabled = operator_text != "между"
        popup.ids.filter_value2.opacity = 1 if operator_text == "между" else 0.5

    def apply_filter(self, column_name, operator_text, value1, value2="", popup=None):
        if not column_name:
            self.set_message("Выберите столбец для фильтра.")
            return

        col_type = self._get_column_type(column_name)
        if operator_text not in {"пусто", "не пусто"}:
            if not str(value1).strip():
                self.set_message("Введите значение для фильтра.")
                return

        if operator_text == "между" and not str(value2).strip():
            self.set_message("Для фильтра 'между' нужно второе значение.")
            return
        # запретить нелогичные операторы для текста
        if col_type == "text" and operator_text in {">=", "<=", "между"}:
            self.set_message("Для текстовых столбцов доступны только текстовые фильтры.")
            return
        self.current_filters = [{
            "column": column_name,
            "operator": operator_text,
            "value1": (value1 or "").strip(),
            "value2": (value2 or "").strip(),
        }]
        if popup:
            popup.dismiss()
        self.refresh_table()
        self.set_message(f"Фильтр применён: {column_name} {operator_text}", error=False)
    def clear_filters(self):
        self.current_filters = []
        self.refresh_table()
        self.set_message("Фильтры сброшены.", error=False)
    def _apply_advanced_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        result = df.copy()

        for filt in self.current_filters:
            col = filt.get("column")
            op = filt.get("operator")
            v1 = filt.get("value1")
            v2 = filt.get("value2")

            if col not in result.columns:
                continue

            series = result[col]

            if op == "пусто":
                result = result[series.isna() | (series.astype(str).str.strip() == "")]
                continue

            if op == "не пусто":
                result = result[~series.isna() & (series.astype(str).str.strip() != "")]
                continue

            numeric_series = pd.to_numeric(series, errors="coerce")
            date_series = pd.to_datetime(series, errors="coerce")

            is_numeric_filter = op in {">=", "<=", "между"} and numeric_series.notna().any()

            if is_numeric_filter:
                try:
                    n1 = float(v1.replace(",", "."))
                except Exception:
                    n1 = None

                try:
                    n2 = float(v2.replace(",", ".")) if v2 else None
                except Exception:
                    n2 = None

                if op == ">=" and n1 is not None:
                    result = result[numeric_series >= n1]
                elif op == "<=" and n1 is not None:
                    result = result[numeric_series <= n1]
                elif op == "между" and n1 is not None and n2 is not None:
                    result = result[(numeric_series >= min(n1, n2)) & (numeric_series <= max(n1, n2))]
                continue

            if op in {">=", "<=", "между"} and date_series.notna().any():
                d1 = pd.to_datetime(v1, errors="coerce")
                d2 = pd.to_datetime(v2, errors="coerce") if v2 else pd.NaT

                if op == ">=" and pd.notna(d1):
                    result = result[date_series >= d1]
                elif op == "<=" and pd.notna(d1):
                    result = result[date_series <= d1]
                elif op == "между" and pd.notna(d1) and pd.notna(d2):
                    left, right = min(d1, d2), max(d1, d2)
                    result = result[(date_series >= left) & (date_series <= right)]
                continue

            text_series = series.astype(str).str.strip().str.lower()

            if op == "равно":
                result = result[text_series == str(v1).strip().lower()]
            elif op == "содержит":
                result = result[text_series.str.contains(str(v1).strip().lower(), na=False)]

        return result

    def _apply_sorting(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        sort_col = self.current_sort.get("column")
        ascending = self.current_sort.get("ascending", True)

        if not sort_col or sort_col not in df.columns:
            return df

        series = df[sort_col]

        numeric_series = pd.to_numeric(series, errors="coerce")
        if numeric_series.notna().any():
            temp_df = df.copy()
            temp_df["_sort_key"] = numeric_series
            temp_df = temp_df.sort_values(by="_sort_key", ascending=ascending, na_position="last")
            return temp_df.drop(columns=["_sort_key"])

        date_series = pd.to_datetime(series, errors="coerce")
        if date_series.notna().any():
            temp_df = df.copy()
            temp_df["_sort_key"] = date_series
            temp_df = temp_df.sort_values(by="_sort_key", ascending=ascending, na_position="last")
            return temp_df.drop(columns=["_sort_key"])

        return df.sort_values(by=sort_col, ascending=ascending, na_position="last")
    def clear_sort(self):
        self.current_sort = {}
        self.refresh_table()
        self.set_message("Сортировка сброшена.", error=False)
    def on_sort(self):
        if self.processed_df is None or self.processed_df.empty:
            self.set_message("Сначала загрузите файл.")
            return

        popup = SortPopup()
        columns = self.get_sortable_columns()

        popup.ids.sort_column.values = columns
        popup.ids.sort_column.text = (
            self.current_sort.get("column")
            if self.current_sort.get("column") in columns
            else (columns[0] if columns else "")
        )
        popup.ids.sort_direction.text = (
            "По убыванию" if not self.current_sort.get("ascending", True) else "По возрастанию"
        )
        popup.open()

    def apply_sort(self, column_name, direction_text, popup=None):
        if not column_name:
            self.set_message("Выберите столбец для сортировки.")
            return

        ascending = direction_text == "По возрастанию"

        self.current_sort = {
            "column": column_name,
            "ascending": ascending,
        }

        if popup:
            popup.dismiss()

        self.refresh_table()
        self.set_message(f"Сортировка: {column_name}, {'↑' if ascending else '↓'}", error=False)

    def on_toggle_sensitive(self, state: str):
        self.hide_sensitive = (state == "normal")
        self.refresh_table()

    def open_upload_popup(self):
        popup = UploadPopup()
        popup.open()

    def open_inn_popup(self):
        popup = InnDirectoryPopup()
        popup.open()

    def preview_selected_file(self, selection):
        if not selection:
            return
        file_path = selection[0]
        try:
            raw_df = try_read_table(file_path)
            self.raw_df = raw_df
            self.operations_raw_df = raw_df
            preview_table = self._get_preview_table_widget()
            if preview_table is None:
                return
            start_row = 0
            popup = self._get_upload_popup()
            if popup and "preview_start_row" in popup.ids:
                start_row = parse_start_row(popup.ids.preview_start_row.text)
            prepared_df = prepare_dataframe_from_start_row(raw_df, start_row)
            prepared_df = prepared_df.dropna(axis=1, how="all")
            fill_preview_table(preview_table, prepared_df, n=5)
            self._set_upload_msg("")
        except Exception as e:
            self._set_upload_msg(f"Ошибка чтения файла: {e}")

    def update_preview_from_input(self, start_row_text: str):
        if self.operations_raw_df is None:
            return
        preview_table = self._get_preview_table_widget()
        if preview_table is None:
            return
        start_row = parse_start_row(start_row_text)
        prepared_df = prepare_dataframe_from_start_row(self.operations_raw_df, start_row)
        prepared_df = prepared_df.dropna(axis=1, how="all")
        fill_preview_table(preview_table, prepared_df, n=5)

    def confirm_operations_file(self, selection, start_row_text, rows_text, cols_text, popup):
        if not selection:
            self._set_upload_msg("Сначала выберите файл.")
            return
        file_path = selection[0]
        try:
            raw_df = try_read_table(file_path)
            start_row = parse_start_row(start_row_text)
            df = prepare_dataframe_from_start_row(raw_df, start_row)
            rows_to_drop = parse_delete_rows(rows_text)
            rows_to_drop = [i for i in rows_to_drop if 0 <= i < len(df)]
            if rows_to_drop:
                df = df.drop(index=rows_to_drop)
            cols_to_drop = parse_delete_cols(cols_text, df)
            if cols_to_drop:
                df = df.drop(columns=cols_to_drop, errors="ignore")
            df = df.reset_index(drop=True)
            processed_ops = process_operations_card(df)
            self.operations_raw_df = raw_df
            self.operations_df = processed_ops
            self.processed_df = processed_ops.copy()
            if popup:
                popup.dismiss()
            self.open_inn_popup()
        except Exception as e:
            self._set_upload_msg(f"Ошибка обработки файла: {e}")

    def preview_selected_inn_file(self, selection):
        if not selection:
            return
        file_path = selection[0]
        try:
            raw_df = try_read_table(file_path)
            self.inn_raw_df = raw_df
            popup = self._get_inn_popup()
            if popup is None:
                return
            preview_table = popup.ids.get("inn_preview_table")
            if preview_table is None:
                return
            prepared_df = prepare_inn_directory(raw_df)
            fill_preview_table(preview_table, prepared_df, n=5)
            self._set_inn_upload_msg("")
        except Exception as e:
            self._set_inn_upload_msg(f"Ошибка чтения справочника: {e}")

    def confirm_inn_file(self, selection, popup):
        if not selection:
            self._set_inn_upload_msg("Сначала выберите файл справочника.")
            return

        file_path = selection[0]

        try:
            raw_df = try_read_table(file_path)
            prepared_df = prepare_inn_directory(raw_df)

            self.inn_raw_df = raw_df
            self.inn_df = prepared_df

            self.merge_operations_with_inn()

            if popup:
                popup.dismiss()

            self.set_message("Начинается загрузка данных с сервера...", error=False)

            Thread(target=self.use_server, daemon=True).start()

        except Exception as e:
            self._set_inn_upload_msg(f"Ошибка обработки справочника: {e}")

    def use_server(self):
        if self.operations_df is None or self.operations_df.empty:
            return

        if self.inn_df is None or self.inn_df.empty:
            self.processed_df = self.operations_df.copy()
            self.refresh_table_safe()
            return

        try:
            onetime = self.processed_df.copy()

            def flatten_metric(m: dict) -> dict:
                return {
                    "ИНН": m.get("inn"),
                    "sum_dohod": m.get("sum_dohod"),
                    "staff_count": m.get("staff_count"),
                    "registration_date": m.get("registration_date"),
                }

            inn_series = (
                onetime["ИНН"]
                .astype(str)
                .str.strip()
            )

            inn_series = inn_series[
                ~inn_series.isin(["", "nan", "None", "none", "<NA>"])
            ]
            inn_series = inn_series[inn_series.str.fullmatch(r"\d+")]

            unique_inns = sorted(inn_series.unique())
            total = len(unique_inns)

            if total == 0:
                self.set_progress_message("Не найдено корректных ИНН для запроса к серверу.", error=True)
                return

            session = requests.Session()
            metrics_rows = []

            for idx, inn in enumerate(unique_inns, start=1):
                self.set_progress_message(f"Обработано {idx} из {total} контрагентов", error=False)

                try:
                    r = session.get(f"{BASE_URL}/metrics/by-inn/{inn}", timeout=20)
                    r.raise_for_status()
                    data = r.json()

                    if isinstance(data, list) and len(data) > 0:
                        metrics_rows.append(flatten_metric(data[0]))
                    else:
                        metrics_rows.append({"ИНН": inn})
                except Exception:
                    metrics_rows.append({"ИНН": inn})

            metrics_df = pd.DataFrame(metrics_rows)

            onetime["ИНН"] = (
                onetime["ИНН"]
                .astype(str)
                .str.strip()
                .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "none": pd.NA})
            )

            metrics_df["ИНН"] = (
                metrics_df["ИНН"]
                .astype(str)
                .str.strip()
                .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "none": pd.NA})
            )

            cols_to_drop = [
                "sum_dohod", "staff_count", "registration_date",
                "sum_dohod_x", "staff_count_x", "registration_date_x",
                "sum_dohod_y", "staff_count_y", "registration_date_y",
            ]
            cols_to_drop += [
                c for c in onetime.columns
                if isinstance(c, str) and (c.startswith("income_") or c.startswith("revenue_"))
            ]

            onetime = onetime.drop(columns=[c for c in cols_to_drop if c in onetime.columns])
            onetime = onetime.merge(metrics_df, on="ИНН", how="left")

            onetime["Разница доходов"] = onetime[2024] / onetime["sum_dohod"]

            def critery1(x):
                if pd.isna(x):
                    return 0
                if 0.8 < x < 1:
                    return 5
                elif 0.6 < x < 0.8:
                    return 4
                elif 0.4 < x < 0.6:
                    return 3
                elif 0.2 < x < 0.4:
                    return 2
                return 0

            onetime["Критерий: Разница доходов"] = onetime["Разница доходов"].apply(critery1)

            onetime["registration_date"] = pd.to_datetime(
                onetime["registration_date"],
                errors="coerce"
            ).dt.date

            onetime["Ранняя_дата"] = pd.to_datetime(
                onetime["Ранняя_дата"],
                errors="coerce"
            ).dt.date

            onetime["Разница дат (дней)"] = (
                pd.to_datetime(onetime["Ранняя_дата"], errors="coerce") -
                pd.to_datetime(onetime["registration_date"], errors="coerce")
            ).dt.days
            print(onetime[["ИНН", "registration_date", "Ранняя_дата", "Разница дат (дней)"]].head(20))
            def critery2(x):
                if pd.isna(x):
                    return 0
                if 0 < x < 30:
                    return 5
                elif 30 < x < 90:
                    return 4
                elif 90 < x < 180:
                    return 3
                elif 180 < x < 365:
                    return 2
                return 0

            onetime["Критерий: Разница дат"] = onetime["Разница дат (дней)"].apply(critery2)

            onetime["Доход на сотрудника"] = np.where(
                onetime["sum_dohod"].notna() &
                onetime["staff_count"].notna() &
                (onetime["staff_count"] > 0),
                onetime["sum_dohod"] / onetime["staff_count"],
                np.nan
            )

            onetime["log_income_per_staff"] = np.log1p(onetime["Доход на сотрудника"])
            mean = onetime["log_income_per_staff"].mean()
            std = onetime["log_income_per_staff"].std()

            onetime["z_income_per_staff"] = (
                onetime["log_income_per_staff"] - mean
            ) / std

            def critery3(z):
                if pd.isna(z):
                    return 0
                if z < 0.5:
                    return 0
                elif z < 1:
                    return 2
                elif z < 1.5:
                    return 3
                elif z < 2:
                    return 4
                return 5

            onetime["Критерий: доход/сотрудник"] = onetime["z_income_per_staff"].apply(critery3)

            criteria_weights = {
                "Критерий: доход/сотрудник": self.weight_income_staff / 100.0,
                "Критерий: Разница доходов": self.weight_income_diff / 100.0,
                "Критерий: Разница дат": self.weight_date_diff / 100.0,
            }

            def total_suspicion(row):
                total_score = 0.0
                weight_sum = 0.0
                for col, w in criteria_weights.items():
                    val = row[col]
                    if isinstance(val, (int, float)) and not pd.isna(val):
                        total_score += val * w
                        weight_sum += w
                if weight_sum == 0:
                    return np.nan
                return total_score / weight_sum

            onetime["Итоговая подозрительность"] = onetime.apply(total_suspicion, axis=1)

            onetime = onetime.rename(columns={
                "Аналитика Кт_1": "Название компании",
                "Кредит_сумма": "Сумма начислений",
                "Ранняя_дата": "Дата первого контракта",
                2023: "Кредит в 2023",
                2024: "Кредит в 2024",
                2025: "Кредит в 2025",
                "sum_dohod": "Доход в 2024",
                "staff_count": "Количество сотрудников",
                "registration_date": "Дата регистрации",
                "Критерий: Разница доходов": "Критерий: Процент дохода",
                "Разница доходов": "Процент доходов",
                "Критерий: Разница дат": "Критерий: Разница дат",
                "Разница дат (дней)": "Разница дат в днях",
                "Доход на сотрудника": "Доход на сотрудника",
                "Критерий: доход/сотрудник": "Критерий: доход/сотрудник",
                "Итоговая подозрительность": "Итоговая подозрительность",
            })

            cols_to_keep = [
                "Название компании",
                "Сумма начислений",
                "Дата первого контракта",
                "Кредит в 2023",
                "Кредит в 2024",
                "Кредит в 2025",
                "ИНН",
                "Доход в 2024",
                "Количество сотрудников",
                "Дата регистрации",
                "Критерий: Процент дохода",
                "Процент доходов",
                "Критерий: Разница дат",
                "Разница дат в днях",
                "Доход на сотрудника",
                "Критерий: доход/сотрудник",
                "Итоговая подозрительность",
            ]

            final_df = onetime[cols_to_keep].sort_values(
                by="Итоговая подозрительность",
                ascending=False,
                na_position="last"
            )
            final_df = self._enrich_entity_types(final_df)
            self.sync_counterparties_to_backend(final_df)
            self.processed_df = final_df
            self._calculate_dashboard_stats()
            Clock.schedule_once(lambda dt: self._render_dashboard_stats(), 0)
            self.refresh_table_safe()
            self.set_progress_message(f"Готово: обработано {total} из {total} контрагентов", error=False)

        except Exception as e:
            self.set_progress_message(f"Ошибка при загрузке данных с сервера: {e}", error=True)


    def refresh_table(self, search_text: str = ""):
        table = self.ids.get("counterparties_table")
        if table is None:
            return

        table.clear_widgets()

        if self.processed_df is None or self.processed_df.empty:
            self._refresh_header([])
            table.add_widget(self._build_empty_row("Нет данных. Загрузите файл."))
            return

        df = self._get_filtered_df()

        search_text = (search_text or "").strip().lower()
        if search_text:
            mask = pd.Series(False, index=df.index)
            for col in df.columns:
                mask = mask | df[col].astype(str).str.lower().str.contains(search_text, na=False)
            df = df[mask]

        df = self._apply_advanced_filters(df)
        df = self._apply_sorting(df)

        preferred_cols = [
            "Название компании",
            "Тип контрагента",
            "ИНН",
            "Сумма начислений",
            "Дата первого контракта",
            "Доход в 2024",
            "Итоговая подозрительность",
        ]
        visible_cols = [col for col in preferred_cols if col in df.columns]

        self._refresh_header(visible_cols)

        if df.empty:
            table.add_widget(self._build_empty_row("Ничего не найдено."))
            return

        for _, row in df.iterrows():
            values = [self._format_cell_value(col, row[col]) for col in visible_cols]

            if self.hide_sensitive:
                for i, col in enumerate(visible_cols):
                    if col in ["Название компании", "ИНН"]:
                        values[i] = "Скрыто"

            table.add_widget(self._build_data_row(values, row.to_dict()))

    def open_detail(self, row_data: dict):
        detail_screen = self.manager.get_screen("detail")
        detail_screen.set_data(row_data)
        self.manager.current = "detail"

    def _refresh_header(self, columns: list[str]):
        header = self.ids.get("table_header")
        if header is None:
            return

        header.clear_widgets()
        cols = list(columns)

        if not cols:
            header.cols = 1
            header.size_hint = (None, None)
            header.width = 0
            header.height = 0
            return

        col_width = self._get_effective_col_width(len(cols))
        header.cols = len(cols)
        header.size_hint = (None, None)
        header.width = len(cols) * col_width + max(0, len(cols) - 1) * self.TABLE_SPACING
        header.height = self.HEADER_HEIGHT

        for col_name in cols:
            lbl = Label(
                text=str(col_name),
                size_hint=(None, 1),
                width=col_width,
                color=(0.10, 0.10, 0.12, 1),
                bold=True,
                halign="center",
                valign="middle",
                shorten=True,
                shorten_from="right",
            )
            lbl.bind(size=lambda instance, value: setattr(instance, "text_size", value))
            header.add_widget(lbl)
    def merge_operations_with_inn(self):
        if self.operations_df is None or self.operations_df.empty:
            return
        if self.inn_df is None or self.inn_df.empty:
            self.processed_df = self.operations_df.copy()
            return
        inn_df = self.inn_df.copy()
        inn_df["ИНН"] = (
            inn_df["ИНН"]
            .astype(str)
            .str.strip()
            .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "none": pd.NA})
        )
        merged = self.operations_df.merge(
            inn_df[["Название_norm", "ИНН"]],
            left_on="name_norm",
            right_on="Название_norm",
            how="left"
        )
        if "Название_norm" in merged.columns:
            merged = merged.drop(columns=["Название_norm"], errors="ignore")

        self.processed_df = merged

    def _build_empty_row(self, text: str):
        row = BoxLayout(
            size_hint_y=None,
            height=dp(52),
            padding=[dp(8), 0, dp(8), 0],
        )
        row.add_widget(
            Label(
                text=text,
                color=(0.4, 0.4, 0.45, 1),
                halign="center",
                valign="middle",
            )
        )
        return row

    def _build_data_row(self, values: list[str], row_data: dict):
        cols_count = max(1, len(values))
        col_width = self._get_effective_col_width(cols_count)
        row = ClickableRow(
            cols=cols_count,
            size_hint=(None, None),
            width=cols_count * col_width + max(0, cols_count - 1) * self.TABLE_SPACING,
            height=self.ROW_HEIGHT,
            spacing=self.TABLE_SPACING,
            padding=[dp(8), 0, dp(8), 0],
        )
        row.row_data = row_data
        row.bind(on_release=lambda instance: self.open_detail(instance.row_data))
        with row.canvas.before:
            Color(0.98, 0.98, 0.99, 1)
            row._bg_rect = RoundedRectangle(pos=row.pos, size=row.size, radius=[10])
        def update_bg(instance, *args):
            instance._bg_rect.pos = instance.pos
            instance._bg_rect.size = instance.size
        row.bind(pos=update_bg, size=update_bg)
        for value in values:
            lbl = Label(
                text=safe_text(value),
                size_hint=(None, 1),
                width=col_width,
                color=(0.15, 0.15, 0.18, 1),
                halign="center",
                valign="middle",
                shorten=True,
                shorten_from="right",
            )
            lbl.bind(size=lambda instance, size: setattr(instance, "text_size", size))
            row.add_widget(lbl)
        return row

    def _get_preview_table_widget(self):
        app = App.get_running_app()
        for child in app.root_window.children:
            if isinstance(child, UploadPopup):
                return child.ids.get("preview_table")
        return None

    def _get_upload_popup(self):
        app = App.get_running_app()
        for child in app.root_window.children:
            if isinstance(child, UploadPopup):
                return child
        return None

    def _get_effective_col_width(self, cols_count: int) -> float:
        if cols_count <= 0:
            return self.COL_WIDTH

        scroll = self.ids.get("results_scroll")
        if scroll is None:
            return self.COL_WIDTH

        available_width = scroll.width - dp(24)  # запас под padding/scrollbar
        adaptive_width = available_width / cols_count
        return max(dp(140), adaptive_width)
    def _get_inn_popup(self):
        app = App.get_running_app()
        for child in app.root_window.children:
            if isinstance(child, InnDirectoryPopup):
                return child
        return None

    def _set_inn_upload_msg(self, text: str):
        popup = self._get_inn_popup()
        if popup:
            lbl = popup.ids.get("inn_upload_msg")
            if lbl:
                lbl.text = text
                lbl.color = (0.85, 0.20, 0.20, 1)

    def _set_upload_msg(self, text: str):
        app = App.get_running_app()
        for child in app.root_window.children:
            if isinstance(child, UploadPopup):
                lbl = child.ids.get("upload_msg")
                if lbl:
                    lbl.text = text
                    lbl.color = (0.85, 0.20, 0.20, 1)
                break