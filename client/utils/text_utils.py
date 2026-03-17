import pandas as pd
import re

def safe_text(value) -> str:
    if value is None:
        return ""
    return str(value)

def norm_name(x: str) -> str:
    if pd.isna(x):
        return ""
    x = str(x).upper().strip()
    x = re.sub(r"[«»\"']", " ", x)
    x = re.sub(r"\s+", " ", x).strip()
    return x