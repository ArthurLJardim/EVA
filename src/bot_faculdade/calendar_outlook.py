from __future__ import annotations

from datetime import datetime, timedelta
import logging

import msal
import requests


SCOPES = ["User.Read", "Calendars.ReadWrite"]
GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
logger = logging.getLogger(__name__)


def _app(settings):
    authority = f"https://login.microsoftonline.com/{settings.outlook_tenant_id or 'common'}"
    cache = msal.SerializableTokenCache()
    if settings.outlook_token_cache_file.exists():
        cache.deserialize(settings.outlook_token_cache_file.read_text(encoding="utf-8"))
    app = msal.PublicClientApplication(
        client_id=settings.outlook_client_id,
        authority=authority,
        token_cache=cache,
    )
    return app, cache


def _save_cache(settings, cache) -> None:
    serialized = cache.serialize()
    if serialized:
        settings.outlook_token_cache_file.parent.mkdir(parents=True, exist_ok=True)
        settings.outlook_token_cache_file.write_text(serialized, encoding="utf-8")


def _access_token(settings) -> str | None:
    if not settings.outlook_client_id:
        return None
    app, cache = _app(settings)
    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
    if not result:
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            error = flow.get("error")
            description = flow.get("error_description") or "sem detalhes"
            print(f"Outlook: nao foi possivel iniciar o login por codigo ({error}): {description}")
            return None
        print(flow["message"])
        result = app.acquire_token_by_device_flow(flow)
    _save_cache(settings, cache)
    if "access_token" not in result:
        error = result.get("error")
        description = result.get("error_description") or result.get("suberror") or "sem detalhes"
        print(f"Outlook: login nao gerou token de acesso ({error}): {description}")
        if error == "invalid_client" and "AADSTS7000218" in description:
            print(
                "Outlook: habilite 'Allow public client flows' no app registration do Microsoft Entra "
                "ou use outro OUTLOOK_CLIENT_ID configurado como aplicativo publico."
            )
        return None
    return result["access_token"]


def _event_url(settings, event_id: str | None = None) -> str:
    if settings.outlook_calendar_id and settings.outlook_calendar_id != "primary":
        base = f"{GRAPH_ROOT}/me/calendars/{settings.outlook_calendar_id}/events"
    else:
        base = f"{GRAPH_ROOT}/me/events"
    return f"{base}/{event_id}" if event_id else base


def _request(method: str, url: str, token: str, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    headers["Content-Type"] = "application/json"
    response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
    if response.status_code == 404 and method.upper() in {"PATCH", "DELETE"}:
        return None
    if response.status_code == 401:
        print(
            "Outlook: token aceito para perfil, mas a conta nao tem calendario Outlook/Exchange acessivel pelo Graph."
        )
        return None
    response.raise_for_status()
    if response.status_code == 204:
        return {}
    return response.json()


def sync_outlook_calendar(settings, rows, storage) -> int:
    token = _access_token(settings)
    if token is None:
        return 0

    synced = 0
    for row in rows:
        start = datetime.fromisoformat(row["due_at"])
        now = datetime.now(start.tzinfo) if start.tzinfo else datetime.now()
        if start < now:
            continue
        end = start + timedelta(minutes=30)
        label = "Prova" if row["kind"] == "prova" else "Atividade"
        event = {
            "subject": f"{label}: {row['title']}",
            "body": {
                "contentType": "text",
                "content": f"{row['description'] or ''}\n\nOrigem: {row['source']}\nURL: {row['url'] or ''}".strip(),
            },
            "start": {"dateTime": start.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": settings.timezone},
            "end": {"dateTime": end.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": settings.timezone},
            "isReminderOn": True,
            "reminderMinutesBeforeStart": max(settings.reminder_days or (3,)) * 24 * 60,
            "singleValueExtendedProperties": [
                {
                    "id": "String {00020329-0000-0000-C000-000000000046} Name bot_faculdade_uid",
                    "value": row["uid"],
                }
            ],
        }
        event_id = row["outlook_event_id"]
        if event_id:
            updated = _request("PATCH", _event_url(settings, event_id), token, json=event)
            if updated is not None:
                synced += 1
                continue
        created = _request("POST", _event_url(settings), token, json=event)
        if created is None:
            continue
        storage.set_outlook_event_id(row["uid"], created["id"])
        synced += 1
    return synced


def delete_outlook_events(settings, rows, storage) -> int:
    if not rows:
        return 0

    token = _access_token(settings)
    if token is None:
        return 0

    deleted = 0
    for row in rows:
        event_id = row["outlook_event_id"]
        if not event_id:
            continue
        try:
            _request("DELETE", _event_url(settings, event_id), token)
            storage.set_outlook_event_id(row["uid"], None)
            deleted += 1
        except Exception:
            logger.exception("Falha ao remover evento do Outlook Calendar: %s", event_id)
    return deleted
