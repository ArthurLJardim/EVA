from __future__ import annotations

import os

os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .models import AcademicItem, AcademicNews
from .news import clean_title, is_relevant_news


SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.announcements.readonly",
    "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly",
]


def _credentials(settings) -> Credentials | None:
    token_file: Path = settings.classroom_token_file
    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_file.write_text(creds.to_json(), encoding="utf-8")
    if not creds or not creds.valid:
        print(
            "Google Classroom: nenhum token valido encontrado. "
            "Rode 'python -m bot_faculdade classroom-auth' uma vez para autorizar "
            "(o sync automatico nao abre o navegador para nao travar)."
        )
        return None
    return creds


def authorize_classroom(settings) -> bool:
    token_file: Path = settings.classroom_token_file
    secret_file: Path = settings.google_client_secret_file
    if not secret_file.exists():
        print(f"Google Classroom: arquivo de credenciais nao encontrado: {secret_file}")
        return False
    flow = InstalledAppFlow.from_client_secrets_file(str(secret_file), SCOPES)
    creds = flow.run_local_server(port=0)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    print(f"Google Classroom autorizado. Token salvo em: {token_file}")
    return True


def _list_all(resource, request):
    items = []
    while request is not None:
        response = request.execute()
        for key in ("courses", "courseWork", "announcements", "courseWorkMaterial"):
            items.extend(response.get(key, []))
        request = resource.list_next(previous_request=request, previous_response=response)
    return items


def _due_at(work: dict, timezone: str) -> datetime | None:
    due_date = work.get("dueDate")
    if not due_date:
        return None
    due_time = work.get("dueTime") or {}
    tz = ZoneInfo(timezone)
    return datetime(
        due_date["year"],
        due_date["month"],
        due_date["day"],
        due_time.get("hours", 23),
        due_time.get("minutes", 59),
        tzinfo=tz,
    )


def _kind(text: str, work_type: str = "") -> str:
    low = f"{work_type}\n{text}".lower()
    if any(word in low for word in ["prova", "avaliacao", "avaliação", "quiz", "exam", "teste"]):
        return "prova"
    return "atividade"


def _published_at(value: str | None) -> datetime:
    if not value:
        return datetime.now().astimezone()
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).astimezone()
    except ValueError:
        return datetime.now().astimezone()


def fetch_classroom_data(settings) -> tuple[list[AcademicItem], list[AcademicNews]]:
    if not settings.classroom_enabled:
        return [], []
    creds = _credentials(settings)
    if creds is None:
        return [], []

    service = build("classroom", "v1", credentials=creds)
    courses_resource = service.courses()
    courses = _list_all(courses_resource, courses_resource.list(courseStates=["ACTIVE"]))
    if settings.classroom_course_ids:
        allowed = set(settings.classroom_course_ids)
        courses = [course for course in courses if course.get("id") in allowed]

    items: list[AcademicItem] = []
    news: list[AcademicNews] = []

    for course in courses:
        course_id = course["id"]
        course_name = course.get("name", "Google Classroom")

        try:
            coursework_resource = service.courses().courseWork()
            works = _list_all(
                coursework_resource,
                coursework_resource.list(courseId=course_id, orderBy="dueDate asc"),
            )
        except Exception:
            works = []
        for work in works:
            title = work.get("title") or "Atividade do Google Classroom"
            description = work.get("description") or ""
            text = f"{title}\n{description}"
            due_at = _due_at(work, settings.timezone)
            if due_at:
                items.append(
                    AcademicItem(
                        title=title,
                        due_at=due_at,
                        course=course_name,
                        kind=_kind(text, work.get("workType", "")),
                        source="google_classroom",
                        url=work.get("alternateLink", ""),
                        description=f"Google Classroom - {course_name}\n\n{description}",
                    )
                )
            elif is_relevant_news(text, settings.news_keywords):
                news.append(
                    AcademicNews(
                        title=clean_title(text, fallback=title),
                        published_at=_published_at(work.get("creationTime")),
                        source="google_classroom",
                        url=work.get("alternateLink", ""),
                        description=f"Google Classroom - {course_name}\n\n{description}",
                    )
                )

        try:
            announcements_resource = service.courses().announcements()
            announcements = _list_all(
                announcements_resource,
                announcements_resource.list(courseId=course_id, orderBy="updateTime desc"),
            )
        except Exception:
            announcements = []
        for announcement in announcements:
            text = announcement.get("text") or ""
            if not is_relevant_news(text, settings.news_keywords):
                continue
            news.append(
                AcademicNews(
                    title=clean_title(text, fallback=f"Comunicado - {course_name}"),
                    published_at=_published_at(announcement.get("creationTime")),
                    source="google_classroom",
                    url=announcement.get("alternateLink", ""),
                    description=f"Google Classroom - {course_name}\n\n{text}",
                )
            )

    deduped_items = {item.uid: item for item in items}
    deduped_news = {item.uid: item for item in news}
    return list(deduped_items.values()), list(deduped_news.values())
