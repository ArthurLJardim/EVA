from __future__ import annotations

from datetime import datetime, timedelta
import shutil

from icalendar import Calendar, Event, Alarm


def export_ics(settings, rows) -> None:
    settings.ics_output_path.parent.mkdir(parents=True, exist_ok=True)
    cal = Calendar()
    cal.add("prodid", "-//Bot Faculdade//SIGAA Agenda//PT")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "Faculdade SIGAA")

    for row in rows:
        start = datetime.fromisoformat(row["due_at"])
        event = Event()
        event.add("uid", f"{row['uid']}@bot-faculdade")
        event.add("summary", row["title"])
        event.add("dtstart", start)
        event.add("dtend", start + timedelta(minutes=30))
        event.add("description", row["description"] or "")
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", f"Prazo chegando: {row['title']}")
        alarm.add("trigger", timedelta(days=-settings.alert_days_before))
        event.add_component(alarm)
        cal.add_component(event)

    settings.ics_output_path.write_bytes(cal.to_ical())
    if settings.ics_backup_enabled:
        settings.ics_backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = settings.ics_backup_dir / f"agenda_faculdade-{timestamp}.ics"
        shutil.copy2(settings.ics_output_path, backup_path)
