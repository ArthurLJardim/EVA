from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]


def _path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return BASE_DIR / path


@dataclass(frozen=True)
class Settings:
    sigaa_url: str
    sigaa_username: str
    sigaa_password: str
    sigaa_headless: bool
    sigaa_manual_login: bool
    email_imap_host: str
    email_imap_port: int
    email_username: str
    email_password: str
    email_folder: str
    email_lookback_days: int
    email_sigaa_from: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    notify_to: str
    calendar_provider: str
    google_calendar_id: str
    google_client_secret_file: Path
    google_token_file: Path
    outlook_client_id: str
    outlook_tenant_id: str
    outlook_token_cache_file: Path
    outlook_calendar_id: str
    classroom_enabled: bool
    classroom_token_file: Path
    classroom_course_ids: tuple[str, ...]
    database_path: Path
    ics_output_path: Path
    alert_days_before: int
    reminder_days: tuple[int, ...]
    timezone: str
    news_keywords: tuple[str, ...]
    urgent_keywords: tuple[str, ...]
    dashboard_output_path: Path
    ics_backup_dir: Path
    ics_backup_enabled: bool
    summary_days_ahead: int
    study_materials_dir: Path
    study_material_lookback_days: int
    study_material_extensions: tuple[str, ...]
    telegram_bot_token: str
    telegram_chat_id: str


def load_settings() -> Settings:
    load_dotenv(BASE_DIR / ".env")
    reminder_days = tuple(
        sorted(
            {
                int(day.strip())
                for day in os.getenv("REMINDER_DAYS", os.getenv("ALERT_DAYS_BEFORE", "3")).split(",")
                if day.strip()
            },
            reverse=True,
        )
    )
    return Settings(
        sigaa_url=os.getenv("SIGAA_URL", "").rstrip("/"),
        sigaa_username=os.getenv("SIGAA_USERNAME", ""),
        sigaa_password=os.getenv("SIGAA_PASSWORD", ""),
        sigaa_headless=os.getenv("SIGAA_HEADLESS", "true").lower() == "true",
        sigaa_manual_login=os.getenv("SIGAA_MANUAL_LOGIN", "false").lower() == "true",
        email_imap_host=os.getenv("EMAIL_IMAP_HOST", ""),
        email_imap_port=int(os.getenv("EMAIL_IMAP_PORT", "993")),
        email_username=os.getenv("EMAIL_USERNAME", ""),
        email_password=os.getenv("EMAIL_PASSWORD", ""),
        email_folder=os.getenv("EMAIL_FOLDER", "INBOX"),
        email_lookback_days=int(os.getenv("EMAIL_LOOKBACK_DAYS", "30")),
        email_sigaa_from=os.getenv("EMAIL_SIGAA_FROM", ""),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=os.getenv("SMTP_USERNAME", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        notify_to=os.getenv("NOTIFY_TO", ""),
        calendar_provider=os.getenv("CALENDAR_PROVIDER", "outlook").lower(),
        google_calendar_id=os.getenv("GOOGLE_CALENDAR_ID", "primary"),
        google_client_secret_file=_path(os.getenv("GOOGLE_CLIENT_SECRET_FILE", "credentials/google_client_secret.json")),
        google_token_file=_path(os.getenv("GOOGLE_TOKEN_FILE", "credentials/google_token.json")),
        outlook_client_id=os.getenv("OUTLOOK_CLIENT_ID", ""),
        outlook_tenant_id=os.getenv("OUTLOOK_TENANT_ID", "common"),
        outlook_token_cache_file=_path(os.getenv("OUTLOOK_TOKEN_CACHE_FILE", "credentials/outlook_token_cache.bin")),
        outlook_calendar_id=os.getenv("OUTLOOK_CALENDAR_ID", "primary"),
        classroom_enabled=os.getenv("CLASSROOM_ENABLED", "true").lower() == "true",
        classroom_token_file=_path(os.getenv("CLASSROOM_TOKEN_FILE", "credentials/google_classroom_token.json")),
        classroom_course_ids=tuple(
            course_id.strip()
            for course_id in os.getenv("CLASSROOM_COURSE_IDS", "").split(",")
            if course_id.strip()
        ),
        database_path=_path(os.getenv("DATABASE_PATH", "data/bot_faculdade.sqlite3")),
        ics_output_path=_path(os.getenv("ICS_OUTPUT_PATH", "exports/agenda_faculdade.ics")),
        alert_days_before=int(os.getenv("ALERT_DAYS_BEFORE", "3")),
        reminder_days=reminder_days,
        timezone=os.getenv("TIMEZONE", "America/Sao_Paulo"),
        news_keywords=tuple(
            keyword.strip().lower()
            for keyword in os.getenv(
                "NEWS_KEYWORDS",
                "curso,coordenacao,coordenação,matricula,matrícula,estagio,estágio,edital,bolsa,evento,palestra,monitoria,oportunidade",
            ).split(",")
            if keyword.strip()
        ),
        urgent_keywords=tuple(
            keyword.strip().lower()
            for keyword in os.getenv(
                "URGENT_KEYWORDS",
                "cancelamento,cancelado,adiado,matricula,matrícula,prazo final,prova,edital,urgente",
            ).split(",")
            if keyword.strip()
        ),
        dashboard_output_path=_path(os.getenv("DASHBOARD_OUTPUT_PATH", "exports/dashboard.html")),
        ics_backup_dir=_path(os.getenv("ICS_BACKUP_DIR", "exports/backups")),
        ics_backup_enabled=os.getenv("ICS_BACKUP_ENABLED", "true").lower() == "true",
        summary_days_ahead=int(os.getenv("SUMMARY_DAYS_AHEAD", "7")),
        study_materials_dir=_path(os.getenv("STUDY_MATERIALS_DIR", "materials/provas")),
        study_material_lookback_days=int(os.getenv("STUDY_MATERIAL_LOOKBACK_DAYS", "120")),
        study_material_extensions=tuple(
            extension.strip().lower()
            for extension in os.getenv(
                "STUDY_MATERIAL_EXTENSIONS",
                ".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.zip,.rar,.txt,.png,.jpg,.jpeg",
            ).split(",")
            if extension.strip()
        ),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
    )
