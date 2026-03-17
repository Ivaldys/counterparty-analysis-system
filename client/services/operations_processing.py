import pandas as pd

from utils.text_utils import norm_name


def _find_column(df: pd.DataFrame, keywords: list[str]):
    for col in df.columns:
        name = str(col).lower()
        for k in keywords:
            if k in name:
                return col
    return None


def _split_analytics_column(df: pd.DataFrame, source_col: str, prefix: str) -> pd.DataFrame:
    """
    Разбивает колонку аналитики по переносам строк и вставляет новые колонки на её место.
    """
    split_df = df[source_col].astype(str).str.split("\n", expand=True)
    split_df = split_df.add_prefix(prefix)
    insert_at = df.columns.get_loc(source_col)

    return pd.concat(
        [
            df.iloc[:, :insert_at],
            split_df,
            df.iloc[:, insert_at + 1:]
        ],
        axis=1
    )


def _detect_counterparty_column(df_filtered: pd.DataFrame) -> str:
    """
    Определяет колонку контрагента среди Аналитика Кт_*.
    Игнорирует служебные значения вроде <...>, nan, пустые строки.
    Предпочитает колонку, где больше уникальных осмысленных названий
    и/или встречаются маркеры юрлиц.
    """
    kt_cols = [c for c in df_filtered.columns if str(c).startswith("Аналитика Кт_")]
    if not kt_cols:
        raise ValueError(
            "Не удалось определить колонки аналитики Кт. "
            f"Доступные колонки: {list(df_filtered.columns)}"
        )

    legal_markers = ["ООО", "АО", "ПАО", "ЗАО", "ИП", "LLC", "LTD"]
    bad_values = {"", "nan", "<...>", "...", "-", "none", "null"}

    best_col = None
    best_score = -1

    for col in kt_cols:
        series = (
            df_filtered[col]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        # убираем мусорные значения
        clean = series[
            ~series.str.lower().isin({v.lower() for v in bad_values})
        ]

        if clean.empty:
            continue

        unique_count = clean.nunique()

        marker_count = clean.str.upper().apply(
            lambda x: any(marker in x for marker in legal_markers)
        ).sum()

        # штрафуем колонку, если там слишком много <...>
        bad_count = series.str.lower().isin({v.lower() for v in bad_values}).sum()

        # формула оценки
        score = unique_count + marker_count * 10 - bad_count * 0.1

        if score > best_score:
            best_score = score
            best_col = col

    if best_col is None:
        raise ValueError("Не удалось определить колонку контрагента в аналитике Кт.")

    return best_col


def process_operations_card(df: pd.DataFrame) -> pd.DataFrame:
    """
    Обрабатывает карточку счета 60 и возвращает агрегированную таблицу по контрагентам.
    Ожидается, что df уже имеет правильную строку заголовков.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    # 1. Удалить полностью пустые колонки
    df = df.dropna(axis=1, how="all")

    # 2. Удалить явно лишние колонки, если они есть
    cols_to_remove = [c for c in ["Текущее сальдо", "Unnamed: 11"] if c in df.columns]
    if cols_to_remove:
        df = df.drop(columns=cols_to_remove, errors="ignore")

    # 3. Удалить полностью пустые строки
    df = df.dropna(how="all").reset_index(drop=True)

    # 4. Переименовать технические колонки
    rename_map = {}
    if "Дебет" in df.columns:
        rename_map["Дебет"] = "Дебет счет"
    if "column_5" in df.columns:
        rename_map["column_5"] = "Дебет сумма"
    if "Кредит" in df.columns:
        rename_map["Кредит"] = "Кредит счет"
    if "column_8" in df.columns:
        rename_map["column_8"] = "Кредит сумма"

    df = df.rename(columns=rename_map)

    # 5. Проверка / поиск обязательных колонок
    period_col = _find_column(df, ["период", "дата"])
    credit_sum_col = _find_column(df, ["кредит сумма"])
    credit_acc_col = _find_column(df, ["кредит счет"])

    if period_col is None and "Период" in df.columns:
        period_col = "Период"
    if credit_sum_col is None and "Кредит сумма" in df.columns:
        credit_sum_col = "Кредит сумма"
    if credit_acc_col is None and "Кредит счет" in df.columns:
        credit_acc_col = "Кредит счет"

    if period_col is None:
        raise ValueError(f"Не найдена колонка даты. Доступные колонки: {list(df.columns)}")

    if credit_sum_col is None:
        raise ValueError(f"Не найдена колонка суммы кредита. Доступные колонки: {list(df.columns)}")

    if credit_acc_col is None:
        raise ValueError(f"Не найден счет кредита. Доступные колонки: {list(df.columns)}")

    df = df.rename(columns={
        period_col: "Период",
        credit_sum_col: "Кредит сумма",
        credit_acc_col: "Кредит счет"
    })

    if "Аналитика Кт" not in df.columns:
        raise ValueError(f"Не найдена колонка 'Аналитика Кт'. Доступные колонки: {list(df.columns)}")

    # 6. Приведение типов
    if "Дебет сумма" in df.columns:
        df["Дебет сумма"] = pd.to_numeric(df["Дебет сумма"], errors="coerce").fillna(0)

    df["Кредит сумма"] = pd.to_numeric(df["Кредит сумма"], errors="coerce").fillna(0)
    df["Период"] = pd.to_datetime(df["Период"], dayfirst=True, errors="coerce")

    # 7. Год / месяц
    df["Год"] = df["Период"].dt.year
    df["Месяц"] = df["Период"].dt.month

    # 8. Фильтр проводок
    exclude_debet = {"19.01", "19.02", "19.03", "19.04"}

    if "Дебет счет" in df.columns:
        mask_debet = ~df["Дебет счет"].astype(str).isin(exclude_debet)
    else:
        mask_debet = pd.Series(True, index=df.index)

    mask_kredit = df["Кредит счет"].astype(str).str.startswith("60", na=False)

    df_filtered = df[mask_debet & mask_kredit].copy()

    if df_filtered.empty:
        raise ValueError("После фильтрации по счетам не осталось данных.")

    # 9. Разделение аналитики
    df_filtered = _split_analytics_column(df_filtered, "Аналитика Кт", "Аналитика Кт_")

    if "Аналитика Дт" in df_filtered.columns:
        df_filtered = _split_analytics_column(df_filtered, "Аналитика Дт", "Аналитика Дт_")

    # 10. Определяем колонку контрагента
    counterparty_col = _detect_counterparty_column(df_filtered)

    # 11. Агрегация
    years = [2023, 2024, 2025]

    total_sums = (
        df_filtered.groupby(counterparty_col)["Кредит сумма"]
        .sum()
        .reset_index(name="Кредит_сумма")
    )

    min_dates = (
        df_filtered.groupby(counterparty_col)["Период"]
        .min()
        .reset_index(name="Ранняя_дата")
    )

    yearly_sums = (
        df_filtered.pivot_table(
            index=counterparty_col,
            columns="Год",
            values="Кредит сумма",
            aggfunc="sum",
            fill_value=0
        )
        .reindex(columns=years, fill_value=0)
        .reset_index()
    )

    result = (
        total_sums
        .merge(min_dates, on=counterparty_col)
        .merge(yearly_sums, on=counterparty_col)
    )

    result["Ранняя_дата"] = pd.to_datetime(result["Ранняя_дата"], errors="coerce").dt.date
    result["name_norm"] = result[counterparty_col].apply(norm_name)
    print("СТРОК ДО ОБРАБОТКИ:", len(df))
    print("КОЛОНКИ:", list(df.columns))

    print("СТРОК ПОСЛЕ ФИЛЬТРАЦИИ:", len(df_filtered))
    print("КОЛОНКИ ПОСЛЕ SPLIT:", list(df_filtered.columns))
    print("ВЫБРАННАЯ КОЛОНКА КОНТРАГЕНТА:", counterparty_col)
    if counterparty_col:
        print(df_filtered[counterparty_col].value_counts(dropna=False).head(20))
    return result