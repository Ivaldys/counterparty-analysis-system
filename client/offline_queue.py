import json
from pathlib import Path
from typing import Dict, List

from storage import APP_DIR

QUEUE_PATH = APP_DIR / "feedback_queue.json"

def _read() -> List[Dict]:
    if not QUEUE_PATH.exists():
        return []
    try:
        return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

def _write(items: List[Dict]) -> None:
    QUEUE_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

def enqueue(feedback: Dict) -> None:
    items = _read()
    items.append(feedback)
    _write(items)

def dequeue_all() -> List[Dict]:
    items = _read()
    _write([])
    return items

def size() -> int:
    return len(_read())