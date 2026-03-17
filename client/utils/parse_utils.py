def parse_start_row(text: str) -> int:
    text = (text or "").strip()
    if not text:
        return 0
    if text.isdigit():
        n = int(text)
        if n >= 1:
            return n - 1
    return 0

def parse_delete_rows(text: str) -> list[int]:
    if not text.strip():
        return []

    result = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if chunk.isdigit():
            n = int(chunk)
            if n >= 1:
                result.append(n - 1)
    return result

def parse_delete_cols(text: str, df) -> list[str]:
    if not text.strip():
        return []

    cols_to_drop = []
    parts = [p.strip() for p in text.split(",") if p.strip()]

    for part in parts:
        if part.isdigit():
            idx = int(part)
            if 0 <= idx < len(df.columns):
                cols_to_drop.append(df.columns[idx])
        else:
            for col in df.columns:
                if str(col).strip() == part:
                    cols_to_drop.append(col)
                    break

    unique_cols = []
    seen = set()
    for col in cols_to_drop:
        if col not in seen:
            unique_cols.append(col)
            seen.add(col)
    return unique_cols