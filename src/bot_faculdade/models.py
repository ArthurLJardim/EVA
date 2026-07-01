from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256


@dataclass(frozen=True)
class AcademicItem:
    title: str
    due_at: datetime
    course: str = ""
    kind: str = "atividade"
    source: str = ""
    url: str = ""
    description: str = ""

    @property
    def uid(self) -> str:
        raw = "|".join(
            [
                self.title.strip().lower(),
                self.due_at.isoformat(),
                self.course.strip().lower(),
                self.kind.strip().lower(),
                self.source.strip().lower(),
            ]
        )
        return sha256(raw.encode("utf-8")).hexdigest()

    @property
    def stable_key(self) -> str:
        raw = "|".join(
            [
                self.url.strip().lower(),
                self.title.strip().lower(),
                self.course.strip().lower(),
                self.kind.strip().lower(),
                self.source.strip().lower(),
            ]
        )
        return sha256(raw.encode("utf-8")).hexdigest()

    @property
    def calendar_title(self) -> str:
        label = "Prova" if "prova" in self.kind.lower() else "Atividade"
        course = f" - {self.course}" if self.course else ""
        return f"{label}: {self.title}{course}"


@dataclass(frozen=True)
class AcademicNews:
    title: str
    published_at: datetime
    source: str = ""
    url: str = ""
    sender: str = ""
    description: str = ""

    @property
    def uid(self) -> str:
        raw = "|".join(
            [
                self.title.strip().lower(),
                self.published_at.date().isoformat(),
                self.source.strip().lower(),
                self.url.strip().lower(),
                self.description.strip().lower()[:300],
            ]
        )
        return sha256(raw.encode("utf-8")).hexdigest()
