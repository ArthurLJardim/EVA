from bot_faculdade.calendar_sync import sync_calendars


class Settings:
    calendar_provider = "none"


def test_sync_calendars_none_returns_zeroes():
    assert sync_calendars(Settings(), [], None) == {
        "google": 0,
        "outlook": 0,
        "google_deleted": 0,
        "outlook_deleted": 0,
    }
