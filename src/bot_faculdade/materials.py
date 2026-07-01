from __future__ import annotations

from datetime import datetime, timedelta
from email import message_from_bytes
from email.header import decode_header
from email.message import Message
from imaplib import IMAP4_SSL
from pathlib import Path
import re


MATERIAL_WORDS = (
    "aula",
    "slides",
    "slide",
    "material",
    "apostila",
    "lista",
    "exercicio",
    "exercício",
    "revisao",
    "revisão",
    "conteudo",
    "conteúdo",
    "prova",
    "avaliacao",
    "avaliação",
)


def _decode(value: str | None) -> str:
    if not value:
        return ""
    result = ""
    for payload, encoding in decode_header(value):
        if isinstance(payload, bytes):
            result += payload.decode(encoding or "utf-8", errors="replace")
        else:
            result += payload
    return result


def _body(message: Message) -> str:
    chunks = []
    for part in message.walk() if message.is_multipart() else [message]:
        if part.get_content_type() not in {"text/plain", "text/html"}:
            continue
        payload = part.get_payload(decode=True)
        if payload:
            chunks.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
    return "\n".join(chunks)


def _safe_name(value: str, fallback: str = "prova") -> str:
    value = re.sub(r"[^\w\-. ]+", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip()
    return (value or fallback)[:80]


def _keywords_for_exam(exam) -> set[str]:
    raw = f"{exam['title']} {exam['course'] or ''}"
    words = {
        word.lower()
        for word in re.findall(r"[\wÀ-ÿ]{4,}", raw)
        if word.lower() not in {"prova", "atividade", "avaliacao", "avaliação", "para", "sobre"}
    }
    if exam["course"]:
        words.add(str(exam["course"]).lower())
    return words


def _matches_exam(text: str, exam) -> bool:
    low = text.lower()
    keywords = _keywords_for_exam(exam)
    has_material_shape = any(word in low for word in MATERIAL_WORDS)
    has_exam_keyword = any(keyword and keyword in low for keyword in keywords)
    return has_material_shape and has_exam_keyword


def _attachment_parts(message: Message, extensions: tuple[str, ...]):
    for part in message.walk():
        disposition = (part.get_content_disposition() or "").lower()
        filename = _decode(part.get_filename())
        if disposition != "attachment" and not filename:
            continue
        if not filename:
            continue
        suffix = Path(filename).suffix.lower()
        if extensions and suffix not in extensions:
            continue
        payload = part.get_payload(decode=True)
        if payload:
            yield filename, payload


def archive_exam_materials(settings, storage) -> list[dict]:
    if not settings.email_imap_host or not settings.email_username or not settings.email_password:
        return []

    exams = storage.upcoming_exams(settings.study_material_lookback_days)
    if not exams:
        return []

    settings.study_materials_dir.mkdir(parents=True, exist_ok=True)
    since = (datetime.now() - timedelta(days=settings.study_material_lookback_days)).strftime("%d-%b-%Y")
    archived: list[dict] = []

    with IMAP4_SSL(settings.email_imap_host, settings.email_imap_port) as imap:
        imap.login(settings.email_username, settings.email_password)
        imap.select(settings.email_folder)
        _, data = imap.search(None, f'(SINCE "{since}")')
        for msg_id in data[0].split():
            _, msg_data = imap.fetch(msg_id, "(RFC822)")
            raw = msg_data[0][1]
            message = message_from_bytes(raw)
            subject = _decode(message.get("Subject"))
            sender = _decode(message.get("From"))
            message_id = message.get("Message-ID") or msg_id.decode("ascii", errors="ignore")
            text = f"{subject}\n{sender}\n{_body(message)}"

            for exam in exams:
                if not _matches_exam(text, exam):
                    continue
                exam_dir = settings.study_materials_dir / _safe_name(
                    f"{datetime.fromisoformat(exam['due_at']).strftime('%Y-%m-%d')} {exam['title']}"
                )
                exam_dir.mkdir(parents=True, exist_ok=True)
                for filename, payload in _attachment_parts(message, settings.study_material_extensions):
                    safe_filename = _safe_name(filename, fallback="material")
                    if storage.material_exists(exam["uid"], message_id, safe_filename):
                        continue
                    target = exam_dir / safe_filename
                    counter = 2
                    while target.exists():
                        target = exam_dir / f"{Path(safe_filename).stem}-{counter}{Path(safe_filename).suffix}"
                        counter += 1
                    target.write_bytes(payload)
                    storage.record_material(
                        exam["uid"],
                        message_id,
                        safe_filename,
                        str(target),
                        subject,
                        sender,
                    )
                    archived.append(
                        {
                            "exam_title": exam["title"],
                            "filename": safe_filename,
                            "path": str(target),
                            "subject": subject,
                            "sender": sender,
                        }
                    )
    return archived
