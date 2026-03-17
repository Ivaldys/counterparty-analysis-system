import re
from datetime import datetime
from typing import Any
from collections import Counter

from pypdf import PdfReader


DATE_RE = r"\d{2}\.\d{2}\.\d{4}"


def extract_text_from_pdf(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _search(pattern: str, text: str, flags: int = re.MULTILINE | re.DOTALL) -> str | None:
    m = re.search(pattern, text, flags)
    if not m:
        return None
    if m.lastindex:
        return m.group(1).strip()
    return m.group(0).strip()


def _to_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d.%m.%Y")
    except Exception:
        return None


def parse_egrul_basic(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}

    result["ОГРН"] = _search(r"\bОГРН\s+(\d{13})\b", text)

    result["ИНН юрлица"] = (
        _search(r"ИНН юридического лица\s+(\d{10})", text)
        or _search(r"\bИНН\s+(\d{10})\b", text)
    )

    result["Дата регистрации"] = (
        _search(r"\bДата регистрации\s+(" + DATE_RE + r")", text)
        or _search(r"Дата регистрации до 1 июля 2002 года\s+(" + DATE_RE + r")", text)
        or _search(r"Дата присвоения ОГРН\s+(" + DATE_RE + r")", text)
    )

    result["Дата постановки на учет"] = _search(
        r"Дата постановки на учет(?: в налоговом\s+органе)?\s+(" + DATE_RE + r")",
        text
    )

    result["Регистрирующий орган"] = _search(
        r"Наименование регистрирующего органа\s+(.*?)\n\d+\s",
        text
    )

    fio = re.search(
        r"Фамилия\s*Имя\s*Отчество\s*([А-ЯЁA-Z\-]+)\s*([А-ЯЁA-Z\-]+)\s*([А-ЯЁA-Z\-]+)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    result["Руководитель"] = (
        f"{fio.group(1)} {fio.group(2)} {fio.group(3)}" if fio else None
    )

    result["ИНН руководителя"] = (
        _search(r"21 ИНН\s+(\d{10,12})", text)
        or _search(r"ИНН\s+(\d{10,12})", text)
    )

    result["Должность"] = extract_position(text)

    result["Уставный капитал"] = (
        _search(r"Размер \(в рублях\)\s+([\d ]+)", text)
        or _search(r"Размер уставного капитала\s+(.*?)\n\d+\s", text)
    )

    return result


def parse_egrul_history(text: str) -> dict[str, Any]:
    reasons = re.findall(
        r"Причина внесения записи в ЕГРЮЛ\s+(.*?)\n\d+\s",
        text,
        re.MULTILINE | re.DOTALL,
    )
    reasons = [r.strip() for r in reasons if r.strip()]
    lower_reasons = [r.lower() for r in reasons]

    result: dict[str, Any] = {}
    result["Количество изменений"] = len(reasons)
    result["Есть реорганизация"] = any(
        ("реорганизац" in r or "присоединени" in r or "слияни" in r)
        for r in lower_reasons
    )
    result["Есть исправления"] = any(
        ("ошибк" in r or "исправлен" in r)
        for r in lower_reasons
    )

    result["Топ причин изменений"] = Counter(reasons).most_common(10)
    return result


def build_egrul_flags(parsed: dict[str, Any]) -> dict[str, Any]:
    score = 0.0
    flags: list[str] = []

    capital_raw = parsed.get("Уставный капитал")
    if capital_raw:
        digits = re.sub(r"[^\d]", "", str(capital_raw))
        if digits:
            cap = int(digits)
            parsed["Уставный капитал"] = cap
            if cap <= 10000:
                score += 1.0
                flags.append("Минимальный уставный капитал")

    if parsed.get("Есть реорганизация"):
        score += 1.0
        flags.append("Есть записи о реорганизации")

    if parsed.get("Есть исправления"):
        score += 0.5
        flags.append("Есть записи об исправлениях/ошибках")

    changes_count = parsed.get("Количество изменений", 0) or 0
    if changes_count >= 50:
        score += 1.0
        flags.append("Очень большая история изменений")
    elif changes_count >= 20:
        score += 0.5
        flags.append("Большое число регистрационных изменений")

    reg_date = _to_date(parsed.get("Дата регистрации"))
    if reg_date:
        days = (datetime.now() - reg_date).days
        parsed["Возраст компании (дней)"] = days
        if days < 180:
            score += 1.0
            flags.append("Очень молодая компания")
        elif days < 365:
            score += 0.5
            flags.append("Молодая компания")

    parsed["Риск ЕГРЮЛ"] = round(score, 2)
    parsed["Флаги ЕГРЮЛ"] = flags
    return parsed


def parse_egrul_pdf(pdf_path: str) -> dict[str, Any]:
    text = normalize_text(extract_text_from_pdf(pdf_path))
    result = {}
    result.update(parse_egrul_basic(text))
    result.update(parse_egrul_history(text))
    result = build_egrul_flags(result)
    return result

def extract_position(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]

    bad_fragments = [
        "Страница ",
        "Выписка из ЕГРЮЛ",
        "ГРН и дата внесения",
        "Пол ",
        "Гражданство",
    ]

    for i, line in enumerate(lines):
        clean = " ".join(line.split())

        m = re.search(r"(?:^\d+\s+)?Должность\s+(.+)$", clean)
        if m:
            value = m.group(1).strip()
            if value and not any(fragment in value for fragment in bad_fragments):
                return value
        if re.fullmatch(r"(?:\d+\s+)?Должность", clean):
            for j in range(i + 1, min(i + 6, len(lines))):
                value = " ".join(lines[j].split()).strip()

                if not value:
                    continue

                if any(fragment in value for fragment in bad_fragments):
                    continue

                if re.fullmatch(r"\d+", value):
                    continue

                return value

    return None