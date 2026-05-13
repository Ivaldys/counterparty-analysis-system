import time
import requests

BASE = "https://egrul.nalog.ru"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.7,en;q=0.6",
    "Referer": f"{BASE}/index.html",
    "X-Requested-With": "XMLHttpRequest",
}


def get_pdf_by_inn(inn: str, out_path: str = "vypiska.pdf", timeout_sec: int = 60) -> str:
    with requests.Session() as s:
        s.headers.update(HEADERS)

        s.get(f"{BASE}/index.html", timeout=30)

        r = s.post(f"{BASE}/", data={"query": inn}, timeout=30)
        r.raise_for_status()
        search_token = r.json().get("t")
        if not search_token:
            raise RuntimeError(f"Не получили token поиска. Ответ: {r.text}")

        r = s.get(f"{BASE}/search-result/{search_token}", timeout=30)
        r.raise_for_status()
        rows = (r.json().get("rows") or [])
        if not rows:
            raise RuntimeError(f"По ИНН={inn} ничего не найдено. Ответ: {r.text}")

        row_token = rows[0].get("t")
        if not row_token:
            raise RuntimeError(f"Не получили token строки rows[0]['t']. Строка: {rows[0]}")

        r = s.get(f"{BASE}/vyp-request/{row_token}", timeout=30)
        r.raise_for_status()

        t0 = time.time()
        status = None
        while time.time() - t0 < timeout_sec:
            r = s.get(f"{BASE}/vyp-status/{row_token}", timeout=30)
            r.raise_for_status()
            status = (r.json().get("status") or "").lower()
            if status == "ready":
                break
            time.sleep(0.7)

        if status != "ready":
            raise RuntimeError(f"Выписка не стала ready за {timeout_sec}s. Последний status={status}")

        r = s.get(f"{BASE}/vyp-download/{row_token}", stream=True, timeout=60)
        r.raise_for_status()

        ctype = (r.headers.get("Content-Type") or "").lower()
        if "pdf" not in ctype:
            body_head = r.content[:300]
            raise RuntimeError(
                f"Ожидали PDF, но получили Content-Type={ctype}. Начало ответа: {body_head!r}"
            )

        with open(out_path, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)

        return out_path