from __future__ import annotations

from email.message import EmailMessage
import logging
import smtplib
from urllib.parse import urlencode
from urllib.request import urlopen


logger = logging.getLogger(__name__)


def send_email(settings, subject: str, body: str) -> bool:
    if not settings.smtp_host or not settings.smtp_username or not settings.smtp_password or not settings.notify_to:
        return False
    msg = EmailMessage()
    msg["From"] = settings.smtp_username
    msg["To"] = settings.notify_to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception:
        logger.exception("Falha ao enviar notificacao por e-mail")
        return False


def send_telegram(settings, text: str) -> bool:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return False
    payload = urlencode({"chat_id": settings.telegram_chat_id, "text": text[:3900]})
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        with urlopen(url, data=payload.encode("utf-8"), timeout=20) as response:
            return 200 <= response.status < 300
    except Exception:
        logger.exception("Falha ao enviar notificacao por Telegram")
        return False


def send_all(settings, subject: str, body: str) -> bool:
    sent_email = send_email(settings, subject, body)
    sent_telegram = send_telegram(settings, f"{subject}\n\n{body}")
    return sent_email or sent_telegram
