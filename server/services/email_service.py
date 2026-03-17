import os
import smtplib
from email.message import EmailMessage

SMTP_HOST = ''
SMTP_PORT = 0
SMTP_USER = ''
SMTP_PASSWORD = ''
SMTP_FROM = ''


def send_email_smtp(to_email: str, subject: str, body: str) -> None:
    """
    Отправка письма через SMTP STARTTLS (обычно порт 587).
    """
    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD):
        raise RuntimeError("SMTP не настроен: проверь SMTP_HOST/SMTP_USER/SMTP_PASSWORD")

    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)