import pandas as pd
from kivy.metrics import dp
from kivy.uix.label import Label

from utils.text_utils import safe_text


def _make_cell(text: str, bold: bool = False, width: int = 150, height: int = 34) -> Label:
    return Label(
        text=text,
        bold=bold,
        size_hint=(None, None),
        size=(dp(width), dp(height)),
        color=(0.10, 0.10, 0.12, 1) if bold else (0.15, 0.15, 0.18, 1),
        halign="center",
        valign="middle",
        text_size=(dp(width - 10), dp(height)),
        shorten=True,
        shorten_from="right",
    )


def fill_preview_table(preview_table, df: pd.DataFrame, start_row: int = 0, n: int = 5):
    preview_table.clear_widgets()

    if df is None or df.empty:
        preview_table.cols = 1
        preview_table.add_widget(
            _make_cell("Файл пустой.", bold=False, width=300, height=34)
        )
        return

    start_row = max(0, min(start_row, len(df) - 1))
    head = df.iloc[start_row:start_row + n].copy()

    if head.empty:
        preview_table.cols = 1
        preview_table.add_widget(
            _make_cell("Нет строк для предпросмотра.", bold=False, width=300, height=34)
        )
        return

    cols = list(head.columns[:8])
    preview_table.cols = len(cols)

    # Заголовки
    for col in cols:
        preview_table.add_widget(
            _make_cell(str(col), bold=True, width=150, height=36)
        )

    # Данные
    for _, row in head.iterrows():
        for col in cols:
            preview_table.add_widget(
                _make_cell(safe_text(row[col]), bold=False, width=150, height=34)
            )