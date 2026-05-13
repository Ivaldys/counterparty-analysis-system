import os
import smtplib
from email.message import EmailMessage

SMTP_HOST = 'Ваш хост Smtp'
SMTP_PORT = 465
SMTP_USER = 'Ваша почта'
SMTP_PASSWORD = 'ваш пароль'
SMTP_FROM = 'Ваша почта'


def send_email_smtp(to_email: str, subject: str, body: str) -> None:

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