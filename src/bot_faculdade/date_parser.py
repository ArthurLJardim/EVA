from __future__ import annotations

from datetime import datetime, time
import re
import unicodedata
from zoneinfo import ZoneInfo

from dateutil import parser


MONTHS_PT = {
    "janeiro": "01",
    "fevereiro": "02",
    "marco": "03",
    "abril": "04",
    "maio": "05",
    "junho": "06",
    "julho": "07",
    "agosto": "08",
    "setembro": "09",
    "outubro": "10",
    "novembro": "11",
    "dezembro": "12",
}


def parse_due_date(text: str, timezone: str) -> datetime | None:
    cleaned = " ".join(text.replace("\xa0", " ").split()).lower()
    cleaned = unicodedata.normalize("NFKD", cleaned).encode("ascii", "ignore").decode("ascii")

    for name, number in MONTHS_PT.items():
        cleaned = re.sub(rf"\b{name}\b", number, cleaned)

    time_pattern = r"(\d{1,2}(?::|h)\d{2})"
    patterns = [
        (rf"(\d{{1,2}}/\d{{1,2}}/\d{{2,4}})(?:\s*(?:as)?\s*{time_pattern})?", True),
        (rf"(\d{{1,2}}-\d{{1,2}}-\d{{2,4}})(?:\s*(?:as)?\s*{time_pattern})?", True),
        (rf"(\d{{1,2}}/\d{{1,2}})(?:\s*(?:as)?\s*{time_pattern})?", False),
        (rf"(\d{{1,2}}-\d{{1,2}})(?:\s*(?:as)?\s*{time_pattern})?", False),
        (rf"(\d{{1,2}}\s+de\s+\d{{2}}\s+de\s+\d{{4}})(?:\s*(?:as)?\s*{time_pattern})?", True),
        (rf"(\d{{1,2}}\s+de\s+\d{{2}})(?:\s*(?:as)?\s*{time_pattern})?", False),
    ]
    tz = ZoneInfo(timezone)
    now = datetime.now(tz)
    for pattern, has_year in patterns:
        match = re.search(pattern, cleaned)
        if not match:
            continue
        date_part = match.group(1).replace(" de ", "/").replace("-", "/").replace(" ", "")
        hour_part = (match.group(2) or "23:59").replace("h", ":")
        if not has_year:
            date_part = f"{date_part}/{now.year}"
        try:
            parsed = parser.parse(f"{date_part} {hour_part}", dayfirst=True).replace(tzinfo=tz)
            if not has_year and parsed < now:
                parsed = parsed.replace(year=parsed.year + 1)
            return parsed
        except (ValueError, OverflowError):
            continue

    return None


def end_of_day(dt: datetime, timezone: str) -> datetime:
    return datetime.combine(dt.date(), time(23, 59), tzinfo=ZoneInfo(timezone))
