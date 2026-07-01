from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

from .models import AcademicItem, AcademicNews
from .priority import classify_priority


class Storage:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.database_path)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS academic_items (
                uid TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                due_at TEXT NOT NULL,
                course TEXT,
                kind TEXT,
                source TEXT,
                url TEXT,
                description TEXT,
                google_event_id TEXT,
                notified_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._add_column("academic_items", "stable_key", "TEXT")
        self._add_column("academic_items", "priority", "TEXT DEFAULT 'baixa'")
        self._add_column("academic_items", "outlook_event_id", "TEXT")
        self._add_column("academic_items", "removed_at", "TEXT")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS academic_news (
                uid TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                published_at TEXT NOT NULL,
                source TEXT,
                url TEXT,
                sender TEXT,
                description TEXT,
                notified_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._add_column("academic_news", "priority", "TEXT DEFAULT 'baixa'")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_uid TEXT NOT NULL,
                reminder_days INTEGER NOT NULL,
                sent_at TEXT NOT NULL,
                UNIQUE(item_uid, reminder_days)
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS change_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_uid TEXT NOT NULL,
                title TEXT NOT NULL,
                field_name TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS study_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_uid TEXT NOT NULL,
                message_id TEXT,
                filename TEXT NOT NULL,
                saved_path TEXT NOT NULL,
                source_subject TEXT,
                sender TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(exam_uid, message_id, filename)
            )
            """
        )
        self.conn.commit()

    def _add_column(self, table: str, column: str, definition: str) -> None:
        columns = [row["name"] for row in self.conn.execute(f"PRAGMA table_info({table})")]
        if column not in columns:
            try:
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise

    def upsert_items(self, items: list[AcademicItem]) -> dict:
        new_count = 0
        new_items = []
        changed_items = []
        now = datetime.now().isoformat()
        for item in items:
            priority = classify_priority(f"{item.title}\n{item.description}\n{item.course}", item.kind)
            existing = self.conn.execute("SELECT uid FROM academic_items WHERE uid = ?", (item.uid,)).fetchone()
            stable_existing = None
            if existing is None:
                stable_existing = self.conn.execute(
                    "SELECT * FROM academic_items WHERE stable_key = ?",
                    (item.stable_key,),
                ).fetchone()

            if stable_existing is not None:
                changes = self._detect_item_changes(stable_existing, item)
                self.conn.execute(
                    """
                    UPDATE academic_items
                    SET uid = ?, title = ?, due_at = ?, course = ?, kind = ?, source = ?,
                        url = ?, description = ?, stable_key = ?, priority = ?, removed_at = NULL, updated_at = ?
                    WHERE uid = ?
                    """,
                    (
                        item.uid,
                        item.title,
                        item.due_at.isoformat(),
                        item.course,
                        item.kind,
                        item.source,
                        item.url,
                        item.description,
                        item.stable_key,
                        priority,
                        now,
                        stable_existing["uid"],
                    ),
                )
                for field_name, old_value, new_value in changes:
                    self._insert_change(item.uid, item.title, field_name, old_value, new_value, now)
                if changes:
                    changed_items.append({"item": item, "changes": changes})
                continue

            self.conn.execute(
                """
                INSERT INTO academic_items (
                    uid, title, due_at, course, kind, source, url, description, stable_key, priority, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(uid) DO UPDATE SET
                    title = excluded.title,
                    due_at = excluded.due_at,
                    course = excluded.course,
                    kind = excluded.kind,
                    source = excluded.source,
                    url = excluded.url,
                    description = excluded.description,
                    stable_key = excluded.stable_key,
                    priority = excluded.priority,
                    removed_at = NULL,
                    updated_at = excluded.updated_at
                """,
                (
                    item.uid,
                    item.title,
                    item.due_at.isoformat(),
                    item.course,
                    item.kind,
                    item.source,
                    item.url,
                    item.description,
                    item.stable_key,
                    priority,
                    now,
                    now,
                ),
            )
            if existing is None:
                new_count += 1
                new_items.append(item)
        self.conn.commit()
        return {"new": new_count, "new_items": new_items, "changed": changed_items}

    def _detect_item_changes(self, row: sqlite3.Row, item: AcademicItem) -> list[tuple[str, str, str]]:
        checks = [
            ("title", row["title"] or "", item.title),
            ("due_at", row["due_at"] or "", item.due_at.isoformat()),
            ("course", row["course"] or "", item.course),
            ("kind", row["kind"] or "", item.kind),
            ("description", row["description"] or "", item.description),
        ]
        return [(field, old, new) for field, old, new in checks if old != new]

    def _insert_change(self, uid: str, title: str, field_name: str, old_value: str, new_value: str, now: str) -> None:
        self.conn.execute(
            """
            INSERT INTO change_log (item_uid, title, field_name, old_value, new_value, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (uid, title, field_name, old_value, new_value, now),
        )

    def list_items(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM academic_items WHERE removed_at IS NULL ORDER BY due_at ASC"
            ).fetchall()
        )

    def mark_missing_items_removed(self, source_stable_keys: dict[str, set[str]]) -> list[sqlite3.Row]:
        removed = []
        now = datetime.now().astimezone().isoformat()
        for source, stable_keys in source_stable_keys.items():
            if not stable_keys:
                continue
            placeholders = ",".join("?" for _ in stable_keys)
            rows = self.conn.execute(
                f"""
                SELECT * FROM academic_items
                WHERE source = ?
                  AND removed_at IS NULL
                  AND stable_key NOT IN ({placeholders})
                """,
                (source, *stable_keys),
            ).fetchall()
            for row in rows:
                self.conn.execute(
                    "UPDATE academic_items SET removed_at = ?, updated_at = ? WHERE uid = ?",
                    (now, now, row["uid"]),
                )
            removed.extend(rows)
        self.conn.commit()
        return removed

    def upsert_news(self, news: list[AcademicNews]) -> dict:
        changed = 0
        new_news = []
        now = datetime.now().isoformat()
        for item in news:
            priority = classify_priority(f"{item.title}\n{item.description}", "noticia")
            existing = self.conn.execute("SELECT uid FROM academic_news WHERE uid = ?", (item.uid,)).fetchone()
            self.conn.execute(
                """
                INSERT INTO academic_news (
                    uid, title, published_at, source, url, sender, description, priority, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(uid) DO UPDATE SET
                    title = excluded.title,
                    published_at = excluded.published_at,
                    source = excluded.source,
                    url = excluded.url,
                    sender = excluded.sender,
                    description = excluded.description,
                    priority = excluded.priority,
                    updated_at = excluded.updated_at
                """,
                (
                    item.uid,
                    item.title,
                    item.published_at.isoformat(),
                    item.source,
                    item.url,
                    item.sender,
                    item.description,
                    priority,
                    now,
                    now,
                ),
            )
            if existing is None:
                changed += 1
                new_news.append(item)
        self.conn.commit()
        return {"new": changed, "new_news": new_news}

    def list_news(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM academic_news ORDER BY published_at DESC"
            ).fetchall()
        )

    def pending_news_notifications(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT * FROM academic_news
                WHERE notified_at IS NULL
                ORDER BY published_at DESC
                """
            ).fetchall()
        )

    def pending_notification_items(self, reminder_days: tuple[int, ...]) -> list[dict]:
        now = datetime.now().astimezone()
        pending = []
        for days_before in reminder_days:
            limit = now + timedelta(days=days_before)
            rows = self.conn.execute(
                """
                SELECT * FROM academic_items
                WHERE due_at >= ?
                  AND due_at <= ?
                  AND NOT EXISTS (
                      SELECT 1 FROM notification_log
                      WHERE notification_log.item_uid = academic_items.uid
                        AND notification_log.reminder_days = ?
                  )
                ORDER BY due_at ASC
                """,
                (now.isoformat(), limit.isoformat(), days_before),
            ).fetchall()
            pending.extend({"row": row, "reminder_days": days_before} for row in rows)
        return pending

    def mark_notified(self, uid: str, reminder_days: int) -> None:
        self.conn.execute(
            "UPDATE academic_items SET notified_at = ? WHERE uid = ?",
            (datetime.now().astimezone().isoformat(), uid),
        )
        self.conn.execute(
            """
            INSERT OR IGNORE INTO notification_log (item_uid, reminder_days, sent_at)
            VALUES (?, ?, ?)
            """,
            (uid, reminder_days, datetime.now().astimezone().isoformat()),
        )
        self.conn.commit()

    def mark_news_notified(self, uid: str) -> None:
        self.conn.execute(
            "UPDATE academic_news SET notified_at = ? WHERE uid = ?",
            (datetime.now().astimezone().isoformat(), uid),
        )
        self.conn.commit()

    def set_google_event_id(self, uid: str, event_id: str) -> None:
        self.conn.execute(
            "UPDATE academic_items SET google_event_id = ? WHERE uid = ?",
            (event_id, uid),
        )
        self.conn.commit()

    def set_outlook_event_id(self, uid: str, event_id: str) -> None:
        self.conn.execute(
            "UPDATE academic_items SET outlook_event_id = ? WHERE uid = ?",
            (event_id, uid),
        )
        self.conn.commit()

    def upcoming_items(self, days_ahead: int) -> list[sqlite3.Row]:
        now = datetime.now().astimezone()
        limit = now + timedelta(days=days_ahead)
        return list(
            self.conn.execute(
                """
                SELECT * FROM academic_items
                WHERE due_at >= ? AND due_at <= ?
                ORDER BY due_at ASC
                """,
                (now.isoformat(), limit.isoformat()),
            ).fetchall()
        )

    def recent_news(self, days_back: int = 7) -> list[sqlite3.Row]:
        since = datetime.now().astimezone() - timedelta(days=days_back)
        return list(
            self.conn.execute(
                """
                SELECT * FROM academic_news
                WHERE published_at >= ?
                ORDER BY published_at DESC
                """,
                (since.isoformat(),),
            ).fetchall()
        )

    def recent_changes(self, limit: int = 20) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT * FROM change_log
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        )

    def upcoming_exams(self, days_ahead: int = 120) -> list[sqlite3.Row]:
        now = datetime.now().astimezone()
        limit = now + timedelta(days=days_ahead)
        return list(
            self.conn.execute(
                """
                SELECT * FROM academic_items
                WHERE due_at >= ?
                  AND due_at <= ?
                  AND lower(kind) LIKE '%prova%'
                ORDER BY due_at ASC
                """,
                (now.isoformat(), limit.isoformat()),
            ).fetchall()
        )

    def material_exists(self, exam_uid: str, message_id: str, filename: str) -> bool:
        row = self.conn.execute(
            """
            SELECT id FROM study_materials
            WHERE exam_uid = ? AND message_id = ? AND filename = ?
            """,
            (exam_uid, message_id, filename),
        ).fetchone()
        return row is not None

    def record_material(
        self,
        exam_uid: str,
        message_id: str,
        filename: str,
        saved_path: str,
        source_subject: str,
        sender: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO study_materials (
                exam_uid, message_id, filename, saved_path, source_subject, sender, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exam_uid,
                message_id,
                filename,
                saved_path,
                source_subject,
                sender,
                datetime.now().astimezone().isoformat(),
            ),
        )
        self.conn.commit()

    def list_materials(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT study_materials.*, academic_items.title AS exam_title, academic_items.due_at
                FROM study_materials
                LEFT JOIN academic_items ON academic_items.uid = study_materials.exam_uid
                ORDER BY academic_items.due_at ASC, study_materials.created_at DESC
                """
            ).fetchall()
        )
