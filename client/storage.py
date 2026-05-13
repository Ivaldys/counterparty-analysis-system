import json
from pathlib import Path
from typing import Optional

APP_DIR = Path.home() / ".kivy_diploma_client"
APP_DIR.mkdir(parents=True, exist_ok=True)
TOKEN_PATH = APP_DIR / "token.json"

def save_token(token: str) -> None:
    TOKEN_PATH.write_text(json.dumps({"token": token}, ensure_ascii=False), encoding="utf-8")

def load_token() -> Optional[str]:
    if not TOKEN_PATH.exists():
        return None
    try:
        data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
        return data.get("token")
    except Exception:
        return None

def clear_token() -> None:
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()