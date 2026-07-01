from __future__ import annotations

from .calendar_google import delete_google_events, sync_google_calendar
from .calendar_outlook import delete_outlook_events, sync_outlook_calendar


def sync_calendars(settings, rows, storage, removed_rows=None) -> dict[str, int]:
    provider = settings.calendar_provider
    removed_rows = removed_rows or []
    result = {"google": 0, "outlook": 0, "google_deleted": 0, "outlook_deleted": 0}
    if provider in {"google", "both"}:
        result["google_deleted"] = delete_google_events(settings, removed_rows, storage)
        result["google"] = sync_google_calendar(settings, rows, storage)
    if provider in {"outlook", "both"}:
        result["outlook_deleted"] = delete_outlook_events(settings, removed_rows, storage)
        result["outlook"] = sync_outlook_calendar(settings, rows, storage)
    return result
