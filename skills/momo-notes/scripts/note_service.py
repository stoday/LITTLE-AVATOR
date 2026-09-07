"""Durable note, reminder, activity, search, and staged-deletion logic."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


_UNSET = object()


@dataclass(frozen=True)
class Note:
    note_id: str
    content: str
    reminder: dict[str, Any] | None


class ActivityLog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, event_type: str, **data: str) -> None:
        record = {
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "type": event_type,
            **data,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]


class NoteStore:
    """Transactional SQLite storage that preserves the original notes schema."""

    def __init__(self, path: Path, activity_log: ActivityLog | None = None) -> None:
        self.path = path
        self.activity_log = activity_log
        self._initialise()

    def create_note(self, content: str, reminder: dict[str, Any] | None = None) -> Note:
        note = Note(str(uuid.uuid4()), content.strip(), self._normalise_reminder(reminder))
        with self._write_connection() as connection:
            connection.execute(
                "INSERT INTO notes (note_id, content, reminder_json) VALUES (?, ?, ?)",
                (note.note_id, note.content, self._encode_reminder(note.reminder)),
            )
        self._record("note_created", note.note_id)
        return note

    def list_notes(self) -> list[Note]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT note_id, content, reminder_json FROM notes ORDER BY created_order"
            ).fetchall()
        return [self._note_from_row(row) for row in rows]

    def search_notes(self, query: str, reminder_kind: str | None = None) -> list[Note]:
        text = query.strip().casefold()
        if reminder_kind not in (None, "daily", "once"):
            raise ValueError("reminder kind must be daily or once")
        return [
            note
            for note in self.list_notes()
            if (not text or text in note.content.casefold())
            and (reminder_kind is None or (note.reminder or {}).get("kind") == reminder_kind)
        ]

    def read_document(self) -> str:
        notes = self.list_notes()
        if not notes:
            return "# Momo 筆記\n"
        return "# Momo 筆記\n\n" + "\n\n".join(self._render_note(note) for note in notes) + "\n"

    def update_note(self, note_id: str, content: str, reminder: dict[str, Any] | None | object = _UNSET) -> Note:
        with self._write_connection() as connection:
            existing = self._existing_note(connection, note_id)
            updated = Note(
                note_id=existing.note_id,
                content=content.strip(),
                reminder=existing.reminder if reminder is _UNSET else self._normalise_reminder(reminder),
            )
            connection.execute(
                "UPDATE notes SET content = ?, reminder_json = ? WHERE note_id = ?",
                (updated.content, self._encode_reminder(updated.reminder), note_id),
            )
        self._record("note_updated", note_id)
        return updated

    def request_deletion(self, note_id: str, turn_id: str) -> Note:
        if not turn_id:
            raise ValueError("a trusted user turn ID is required")
        with self._write_connection() as connection:
            note = self._existing_note(connection, note_id)
            connection.execute("DELETE FROM pending_note_deletions WHERE note_id = ?", (note_id,))
            connection.execute(
                "INSERT INTO pending_note_deletions (note_id, requested_turn_id) VALUES (?, ?)",
                (note_id, turn_id),
            )
        self._record("note_delete_requested", note_id)
        return note

    def confirm_deletion(self, note_id: str, turn_id: str) -> None:
        with self._write_connection() as connection:
            row = connection.execute(
                "SELECT requested_turn_id FROM pending_note_deletions WHERE note_id = ?", (note_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"No pending deletion: {note_id}")
            if not turn_id or turn_id == row[0]:
                raise ValueError("deletion confirmation must come from a later user turn")
            result = connection.execute("DELETE FROM notes WHERE note_id = ?", (note_id,))
            if result.rowcount != 1:
                raise KeyError(f"Unknown note: {note_id}")
            connection.execute("DELETE FROM pending_note_deletions WHERE note_id = ?", (note_id,))
        self._record("note_deleted", note_id)

    def mark_reminder_handled(self, note_id: str, occurrence: str) -> None:
        with self._write_connection() as connection:
            note = self._existing_note(connection, note_id, reminder=True)
            reminder = {**note.reminder, "last_handled_occurrence": occurrence}
            connection.execute(
                "UPDATE notes SET reminder_json = ? WHERE note_id = ?",
                (self._encode_reminder(reminder), note_id),
            )

    def _initialise(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    created_order INTEGER PRIMARY KEY AUTOINCREMENT,
                    note_id TEXT NOT NULL UNIQUE,
                    content TEXT NOT NULL,
                    reminder_json TEXT
                );
                CREATE TABLE IF NOT EXISTS pending_note_deletions (
                    note_id TEXT PRIMARY KEY,
                    requested_turn_id TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _write_connection(self) -> sqlite3.Connection:
        connection = self._connect()
        connection.execute("BEGIN IMMEDIATE")
        return connection

    def _existing_note(self, connection: sqlite3.Connection, note_id: str, reminder: bool = False) -> Note:
        row = connection.execute(
            "SELECT note_id, content, reminder_json FROM notes WHERE note_id = ?", (note_id,)
        ).fetchone()
        if row is None or (reminder and row[2] is None):
            raise KeyError(f"Unknown {'reminder ' if reminder else ''}note: {note_id}")
        return self._note_from_row(row)

    def _record(self, event_type: str, note_id: str) -> None:
        if self.activity_log is not None:
            self.activity_log.append(event_type, note_id=note_id, source="note_store")

    @staticmethod
    def _normalise_reminder(reminder: dict[str, Any] | None) -> dict[str, Any] | None:
        if reminder is None:
            return None
        return {
            **reminder,
            "enabled": reminder.get("enabled", True),
            "last_handled_occurrence": reminder.get("last_handled_occurrence"),
        }

    @staticmethod
    def _encode_reminder(reminder: dict[str, Any] | None) -> str | None:
        return None if reminder is None else json.dumps(reminder, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _note_from_row(row: tuple[str, str, str | None]) -> Note:
        return Note(note_id=row[0], content=row[1], reminder=json.loads(row[2]) if row[2] else None)

    @staticmethod
    def _render_note(note: Note) -> str:
        metadata = json.dumps({"id": note.note_id, "reminder": note.reminder}, ensure_ascii=False, separators=(",", ":"))
        return f"## Note {note.note_id}\n{note.content}\n<!-- momo-note: {metadata} -->"


def normalise_reminder(reminder: dict[str, Any] | None) -> dict[str, Any] | None:
    if reminder is None:
        return None
    kind, time_value = reminder.get("kind"), reminder.get("time")
    if kind == "daily" or (kind is None and isinstance(time_value, str) and "T" not in time_value):
        if not isinstance(time_value, str):
            raise ValueError("daily reminder requires time in HH:MM format")
        try:
            datetime.strptime(time_value, "%H:%M")
        except ValueError as exc:
            raise ValueError("daily reminder requires time in HH:MM format") from exc
        return {"kind": "daily", "time": time_value}
    due_at = reminder.get("due_at") or (time_value if kind in ("once", None) else None)
    if due_at is None or not isinstance(due_at, str) or "T" not in due_at:
        raise ValueError("one-time reminder requires an ISO date and time")
    try:
        due = datetime.fromisoformat(due_at)
    except ValueError as exc:
        raise ValueError("one-time reminder requires an ISO date and time") from exc
    if due.tzinfo is None:
        raise ValueError("one-time reminder requires a timezone-aware ISO date and time")
    return {"kind": "once", "due_at": due.isoformat()}
