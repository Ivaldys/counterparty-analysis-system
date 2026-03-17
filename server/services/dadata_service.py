from dadata import Dadata
from typing import Optional
from datetime import datetime
import os

DADATA_TOKEN = os.getenv("DADATA_TOKEN") or ""
DADATA_SECRET = os.getenv("DADATA_SECRET") or ""

dadata_client: Optional[Dadata] = None
if DADATA_TOKEN and DADATA_SECRET and "ВСТАВЬ_СЮДА" not in DADATA_TOKEN:
    dadata_client = Dadata(DADATA_TOKEN, DADATA_SECRET)

DADATA_FIN_CACHE: dict[str, dict] = {}


def get_dadata_finance_cached(inn: str):
    if inn in DADATA_FIN_CACHE:
        return DADATA_FIN_CACHE[inn]

    out = {
        "registration_date": None,
        "staff_count": None,
        "income_last": None,
        "finance_year": None,
        "party_raw": None,
    }

    if not dadata_client:
        DADATA_FIN_CACHE[inn] = out
        return out

    try:
        res = dadata_client.find_by_id("party", inn)

        if res:
            item = res[0]
            data = item.get("data") or {}
            state = data.get("state") or {}

            out["party_raw"] = item

            reg_ms = state.get("registration_date")
            if reg_ms:
                dt = datetime.fromtimestamp(reg_ms / 1000.0)
                out["registration_date"] = dt.date().isoformat()

            out["staff_count"] = data.get("employee_count")

            finance = data.get("finance")
            if isinstance(finance, dict):
                out["finance_year"] = finance.get("year")
                income = finance.get("income")
                if income is not None:
                    out["income_last"] = float(income)

    except Exception as e:
        print("DADATA ERROR:", e)

    DADATA_FIN_CACHE[inn] = out
    return out