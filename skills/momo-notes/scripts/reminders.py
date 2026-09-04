"""Deterministic due detection owned by the notes Skill."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .note_service import ActivityLog, Note, NoteStore


@dataclass(frozen=True)
class DueReminder:
    note_id: str
    occurrence: str
    prose: str


class ReminderScanner:
    def __init__(self, store: NoteStore, activity_log: ActivityLog) -> None:
        self.store = store
        self.activity_log = activity_log

    def scan(self, *, now: datetime, has_subscriber: bool) -> list[DueReminder]:
        due: list[DueReminder] = []
        try:
            notes = self.store.list_notes()
        except Exception as exc:
            self.activity_log.append("notes_parse_error", source="scheduler", error=type(exc).__name__)
            return due
        for note in notes:
            try:
                occurrence, outcome = self._occurrence(note, now)
                if occurrence is None or outcome is None:
                    continue
                self.store.mark_reminder_handled(note.note_id, occurrence)
                if outcome == "missed":
                    self.activity_log.append("skipped_missed", note_id=note.note_id, occurrence=occurrence, source="scheduler")
                elif not has_subscriber:
                    self.activity_log.append("skipped_no_client", note_id=note.note_id, occurrence=occurrence, source="scheduler")
                else:
                    due.append(DueReminder(note.note_id, occurrence, note.content))
            except Exception as exc:
                self.activity_log.append("notes_parse_error", note_id=note.note_id, source="scheduler", error=type(exc).__name__)
        return due

    @staticmethod
    def _occurrence(note: Note, now: datetime) -> tuple[str | None, str | None]:
        reminder = note.reminder
        if not reminder or not reminder.get("enabled", True):
            return None, None
        if reminder.get("kind") == "daily":
            due = datetime.strptime(str(reminder["time"]), "%H:%M").time()
            scheduled = now.replace(hour=due.hour, minute=due.minute, second=0, microsecond=0)
            occurrence = scheduled.isoformat()
            if reminder.get("last_handled_occurrence") == occurrence or now < scheduled:
                return None, None
            return occurrence, "due" if now.strftime("%H:%M") == reminder["time"] else "missed"
        if reminder.get("kind") == "once":
            scheduled = datetime.fromisoformat(str(reminder["due_at"]))
            if scheduled.tzinfo is None:
                raise ValueError("once reminder must be timezone-aware")
            occurrence = scheduled.isoformat()
            if reminder.get("last_handled_occurrence") == occurrence or now < scheduled:
                return None, None
            return occurrence, "due" if now.strftime("%Y-%m-%dT%H:%M") == scheduled.strftime("%Y-%m-%dT%H:%M") else "missed"
        raise ValueError("unsupported reminder kind")
