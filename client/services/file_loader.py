from pathlib import Path
import pandas as pd

def try_read_table(file_path: str) -> pd.DataFrame:
    ext = Path(file_path).suffix.lower()

    if ext == ".csv":
        for enc in ("utf-8", "utf-8-sig", "cp1251", "windows-1251"):
            try:
                return pd.read_csv(file_path, encoding=enc, header=None)
            except Exception:
                pass
        raise ValueError("Не удалось прочитать CSV файл.")
    elif ext in (".xlsx", ".xls"):
        return pd.read_excel(file_path, header=None)
    else:
        raise ValueError("Поддерживаются только .csv, .xlsx, .xls")

def prepare_dataframe_from_start_row(df: pd.DataFrame, start_row: int) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    if start_row < 0:
        start_row = 0
    if start_row >= len(df):
        return pd.DataFrame()

    header_values = df.iloc[start_row].fillna("").astype(str).tolist()

    columns = []
    seen = set()

    for i, value in enumerate(header_values):
        name = str(value).strip()
        if not name:
            name = f"column_{i}"

        base_name = name
        counter = 1
        while name in seen:
            name = f"{base_name}_{counter}"
            counter += 1

        seen.add(name)
        columns.append(name)

    data = df.iloc[start_row + 1:].copy().reset_index(drop=True)
    data.columns = columns
    data = data.dropna(how="all").reset_index(drop=True)

    return data