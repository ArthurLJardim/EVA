from __future__ import annotations

from datetime import datetime, timedelta
import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .models import AcademicItem


SCOPES = ["https://www.googleapis.com/auth/calendar"]
logger = logging.getLogger(__name__)


def _credentials(settings) -> Credentials | None:
    token_file: Path = settings.google_token_file
    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_file.write_text(creds.to_json(), encoding="utf-8")
    if not creds or not creds.valid:
        print(
            "Google Calendar: nenhum token valido encontrado. "
            "Rode 'python -m bot_faculdade calendar-auth' uma vez para autorizar "
            "(o sync automatico nao abre o navegador para nao travar)."
        )
        return None
    return creds


def authorize_google_calendar(settings) -> bool:
    token_file: Path = settings.google_token_file
    secret_file: Path = settings.google_client_secret_file
    if not secret_file.exists():
        print(f"Google Calendar: arquivo de credenciais nao encontrado: {secret_file}")
        return False
    flow = InstalledAppFlow.from_client_secrets_file(str(secret_file), SCOPES)
    creds = flow.run_local_server(port=0)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    print(f"Google Calendar autorizado. Token salvo em: {token_file}")
    return True


def sync_google_calendar(settings, rows, storage) -> int:
    creds = _credentials(settings)
    if creds is None:
        return 0

    service = build("calendar", "v3", credentials=creds)
    synced = 0
    for row in rows:
        start = datetime.fromisoformat(row["due_at"])
        now = datetime.now(start.tzinfo) if start.tzinfo else datetime.now()
        if start < now:
            continue
        end = start + timedelta(minutes=30)
        event = {
            "summary": f"{'Prova' if row['kind'] == 'prova' else 'Atividade'}: {row['title']}",
            "description": f"{row['description'] or ''}\n\nOrigem: {row['source']}\nURL: {row['url'] or ''}".strip(),
            "start": {"dateTime": start.isoformat(), "timeZone": settings.timezone},
            "end": {"dateTime": end.isoformat(), "timeZone": settings.timezone},
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": method, "minutes": days * 24 * 60}
                    for days in settings.reminder_days[:2]
                    for method in ("email", "popup")
                ],
            },
            "extendedProperties": {"private": {"bot_faculdade_uid": row["uid"]}},
        }
        event_id = row["google_event_id"]
        if event_id:
            service.events().update(
                calendarId=settings.google_calendar_id,
                eventId=event_id,
                body=event,
            ).execute()
        else:
            created = service.events().insert(
                calendarId=settings.google_calendar_id,
                body=event,
            ).execute()
            storage.set_google_event_id(row["uid"], created["id"])
        synced += 1
    return synced


def delete_google_events(settings, rows, storage) -> int:
    if not rows:
        return 0

    creds = _credentials(settings)
    if creds is None:
        return 0

    service = build("calendar", "v3", credentials=creds)
    deleted = 0
    for row in rows:
        event_id = row["google_event_id"]
        if not event_id:
            continue
        try:
            service.events().delete(
                calendarId=settings.google_calendar_id,
                eventId=event_id,
            ).execute()
            storage.set_google_event_id(row["uid"], None)
            deleted += 1
        except Exception:
            logger.exception("Falha ao remover evento do Google Calendar: %s", event_id)
    return deleted
