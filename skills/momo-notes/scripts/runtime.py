"""Public application runtime for the momo-notes Skill."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .note_service import ActivityLog, NoteStore
from .reminders import DueReminder, ReminderScanner


@dataclass
class NoteRuntime:
    store: NoteStore
    activity_log: ActivityLog
    schedule_path: Path

    def read_document(self) -> str:
        return self.store.read_document()

    def read_schedule(self) -> str:
        """Read this avatar's local, user-editable schedule Markdown document."""
        if not self.schedule_path.exists():
            return "# 晚間行程\n"
        return self.schedule_path.read_text(encoding="utf-8")

    def scan_reminders(self, *, now: datetime, has_subscriber: bool) -> list[DueReminder]:
        return ReminderScanner(self.store, self.activity_log).scan(now=now, has_subscriber=has_subscriber)

    def append_activity(self, event_type: str, **data: str) -> None:
        self.activity_log.append(event_type, **data)


def create_runtime(
    *,
    data_directory: Path,
    conversation_id: str | None = None,
    turn_id: str | None = None,
) -> NoteRuntime:
    # Reserved for per-conversation auditing without making the host construct a
    # Skill-specific context type.
    del conversation_id, turn_id
    data = data_directory
    activity_log = ActivityLog(data / "momo-activity.jsonl")
    return NoteRuntime(
        NoteStore(data / "momo-notes.db", activity_log=activity_log),
        activity_log,
        data / "schedule.md",
    )
