from __future__ import annotations

from email.message import EmailMessage
import json
import logging
import re
import smtplib
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


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


def build_whatsapp_payload(settings, text: str) -> dict:
    # Texto livre so chega se voce escreveu para o numero nas ultimas 24h; fora
    # disso a Meta responde 200 e a entrega falha depois (erro 131047). Por isso
    # so usamos template aprovado. Parametros nao aceitam quebra de linha/tab.
    message = text.strip().rstrip(".!? ")
    parameters = [
        {"type": "text", "text": re.sub(r"\s+", " ", param.replace("{mensagem}", message)).strip()[:900] or "-"}
        for param in settings.whatsapp_template_params
    ]
    return {
        "messaging_product": "whatsapp",
        "to": re.sub(r"\D", "", settings.whatsapp_to),
        "type": "template",
        "template": {
            "name": settings.whatsapp_template_name,
            "language": {"code": settings.whatsapp_template_language},
            "components": [{"type": "body", "parameters": parameters}],
        },
    }


def send_whatsapp(settings, text: str) -> bool:
    if not (
        settings.whatsapp_api_token
        and settings.whatsapp_phone_number_id
        and settings.whatsapp_to
        and settings.whatsapp_template_name
    ):
        return False
    request = Request(
        f"https://graph.facebook.com/{settings.whatsapp_api_version}/{settings.whatsapp_phone_number_id}/messages",
        data=json.dumps(build_whatsapp_payload(settings, text)).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.whatsapp_api_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            return 200 <= response.status < 300
    except HTTPError as error:
        logger.error(
            "Falha ao enviar WhatsApp: HTTP %s - %s", error.code, error.read().decode("utf-8", errors="replace")
        )
        return False
    except Exception:
        logger.exception("Falha ao enviar notificacao por WhatsApp")
        return False


def send_all(settings, subject: str, body: str, whatsapp_text: str | None = None) -> bool:
    sent_email = send_email(settings, subject, body)
    sent_telegram = send_telegram(settings, f"{subject}\n\n{body}")
    sent_whatsapp = send_whatsapp(settings, whatsapp_text) if whatsapp_text else False
    return sent_email or sent_telegram or sent_whatsapp
