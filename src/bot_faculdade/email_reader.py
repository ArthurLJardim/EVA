from __future__ import annotations

from datetime import datetime, timedelta
from email import message_from_bytes
from email.header import decode_header
from email.message import Message
from email.utils import parsedate_to_datetime
from imaplib import IMAP4_SSL
import logging
import re

from .date_parser import parse_due_date
from .models import AcademicItem, AcademicNews
from .news import clean_title, is_relevant_news


logger = logging.getLogger(__name__)


def _decode(value: str | None) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    result = ""
    for payload, encoding in parts:
        if isinstance(payload, bytes):
            result += payload.decode(encoding or "utf-8", errors="replace")
        else:
            result += payload
    return result


def _body(message: Message) -> str:
    if message.is_multipart():
        chunks = []
        for part in message.walk():
            content_type = part.get_content_type()
            if content_type not in {"text/plain", "text/html"}:
                continue
            payload = part.get_payload(decode=True)
            if payload:
                chunks.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
        return "\n".join(chunks)
    payload = message.get_payload(decode=True)
    if not payload:
        return ""
    return payload.decode(message.get_content_charset() or "utf-8", errors="replace")


def _guess_kind(text: str) -> str:
    low = text.lower()
    if any(word in low for word in ["prova", "avaliacao", "avaliação", "exame"]):
        return "prova"
    return "atividade"


def _guess_title(subject: str, body: str) -> str:
    candidates = [subject]
    for line in body.splitlines():
        stripped = line.strip()
        if 8 <= len(stripped) <= 120 and re.search(r"(atividade|tarefa|prova|avaliacao|avaliação)", stripped, re.I):
            candidates.append(stripped)
            break
    title = candidates[-1] or "Atualizacao do SIGAA"
    return re.sub(r"\s+", " ", title).strip()


def fetch_email_items(settings) -> list[AcademicItem]:
    items, _ = fetch_email_data(settings)
    return items


def fetch_email_data(settings) -> tuple[list[AcademicItem], list[AcademicNews]]:
    if not settings.email_imap_host or not settings.email_username or not settings.email_password:
        return [], []

    since = (datetime.now() - timedelta(days=settings.email_lookback_days)).strftime("%d-%b-%Y")
    items: list[AcademicItem] = []
    news: list[AcademicNews] = []
    try:
        with IMAP4_SSL(settings.email_imap_host, settings.email_imap_port) as imap:
            imap.login(settings.email_username, settings.email_password)
            imap.select(settings.email_folder)
            criteria = f'(SINCE "{since}")'
            if settings.email_sigaa_from:
                criteria = f'(SINCE "{since}" FROM "{settings.email_sigaa_from}")'
            _, data = imap.search(None, criteria)
            ids = data[0].split()
            for msg_id in ids:
                _, msg_data = imap.fetch(msg_id, "(RFC822)")
                raw = msg_data[0][1]
                message = message_from_bytes(raw)
                subject = _decode(message.get("Subject"))
                sender = _decode(message.get("From"))
                body = _body(message)
                combined = f"{subject}\n{body}"
                if "sigaa" not in combined.lower() and "sigaa" not in sender.lower():
                    continue
                try:
                    published_at = parsedate_to_datetime(message.get("Date")).astimezone()
                except Exception:
                    published_at = datetime.now().astimezone()
                due_at = parse_due_date(combined, settings.timezone)
                if due_at:
                    items.append(
                        AcademicItem(
                            title=_guess_title(subject, body),
                            due_at=due_at,
                            kind=_guess_kind(combined),
                            source="email",
                            description=f"Encontrado no e-mail academico.\n\nRemetente: {sender}\nAssunto: {subject}",
                        )
                    )
                if is_relevant_news(combined, settings.news_keywords):
                    news.append(
                        AcademicNews(
                            title=clean_title(subject or body, fallback="Noticia do SIGAA"),
                            published_at=published_at,
                            source="email",
                            sender=sender,
                            description=f"Remetente: {sender}\nAssunto: {subject}\n\n{body[:1500]}",
                        )
                    )
    except Exception:
        logger.exception("Falha ao ler e-mail academico via IMAP")
    return items, news
