import os
from openai import OpenAI



client = OpenAI(api_key="")


def build_counterparty_prompt(card: dict) -> str:
    return f"""
Ты аналитик по рискам контрагентов.

Ниже карточка контрагента.
Нужно:
1. Кратко оценить риск.
2. Объяснить, какие признаки выглядят подозрительно.
3. Объяснить, какие признаки выглядят нейтрально или нормально.
4. Дать итог: low / medium / high.
5. Ответить строго на русском языке.
6. Не выдумывать факты, опираться только на переданные данные.

Карточка:
Название: {card.get("name")}
ИНН: {card.get("inn")}
Тип контрагента: {card.get("entity_type")}
Сумма начислений: {card.get("total_paid")}
Дата первого контракта: {card.get("first_contract_date")}
Дата регистрации: {card.get("reg_date")}
Доход в 2024: {card.get("income_2024")}
Количество сотрудников: {card.get("staff_count")}
Процент доходов: {card.get("income_share")}
Разница дат в днях: {card.get("date_diff_days")}
Доход на сотрудника: {card.get("income_per_staff")}
Итоговая подозрительность: {card.get("final_score")}
Пользовательский вердикт: {card.get("user_verdict")}
Средний рейтинг: {card.get("avg_rating")}
Число отзывов: {card.get("reviews_count")}
Флаги ЕГРЮЛ: {card.get("egrul_flags")}
Риск ЕГРЮЛ: {card.get("egrul_risk")}

Верни ответ в таком виде:

Итоговый риск: ...
Ключевые причины:
- ...
- ...
Что снижает риск:
- ...
- ...
Краткий вывод:
...
""".strip()


def generate_counterparty_ai_summary(card: dict) -> str:

    prompt = build_counterparty_prompt(card)

    response = client.responses.create(
        model="gpt-5-nano",
        input=prompt,
    )

    return response.output_text.strip()