import pandas as pd
from utils.text_utils import norm_name

def prepare_inn_directory(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["Название", "ИНН", "Название_norm"])

    df = df.iloc[:, :2].copy()
    df.columns = ["Название", "ИНН"]

    df["Название"] = df["Название"].fillna("").astype(str).str.strip()
    df["ИНН"] = df["ИНН"].fillna("").astype(str).str.strip()

    df = df[(df["Название"] != "") | (df["ИНН"] != "")]
    df = df.reset_index(drop=True)

    df["Название_norm"] = df["Название"].apply(norm_name)
    return df