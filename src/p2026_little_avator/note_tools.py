"""The deliberately small Tool surface Momo receives for note management."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import akasha

from .notes import NoteStore


def normalise_reminder(reminder: dict[str, Any] | None) -> dict[str, Any] | None:
    """Accept only the reminder shapes the scheduler can execute."""
    if reminder is None:
        return None
    kind = reminder.get("kind")
    time_value = reminder.get("time")
    if kind == "daily" or (kind is None and isinstance(time_value, str) and "T" not in time_value):
        if not isinstance(time_value, str):
            raise ValueError("daily reminder requires time in HH:MM format")
        try:
            datetime.strptime(time_value, "%H:%M")
        except ValueError as exc:
            raise ValueError("daily reminder requires time in HH:MM format") from exc
        return {"kind": "daily", "time": time_value}

    due_at = reminder.get("due_at")
    if kind == "once":
        due_at = due_at or time_value
    elif kind is None and isinstance(time_value, str) and "T" in time_value:
        due_at = time_value
    if due_at is not None:
        if not isinstance(due_at, str) or "T" not in due_at:
            raise ValueError("one-time reminder requires an ISO date and time")
        try:
            due = datetime.fromisoformat(due_at)
        except ValueError as exc:
            raise ValueError("one-time reminder requires an ISO date and time") from exc
        if due.tzinfo is None:
            due = due.astimezone()
        return {"kind": "once", "due_at": due.isoformat()}

    raise ValueError("reminder must be daily HH:MM or a one-time ISO date and time")


def create_note_tools(store: NoteStore) -> list[Any]:
    """Return only the application-owned note and time Tools for one Agent."""

    def create_note(content: str, reminder: dict[str, Any] | None = None) -> str:
        """Create a durable note; reminders must be daily HH:MM or one-time ISO date/time."""
        note = store.create_note(content, normalise_reminder(reminder))
        return f"Created note {note.note_id}."

    def update_note(
        note_id: str,
        content: str,
        reminder: dict[str, Any] | None = None,
        clear_reminder: bool = False,
    ) -> str:
        """Update one unambiguous note; omit reminder to preserve it, or clear it explicitly."""
        if clear_reminder:
            note = store.update_note(note_id, content, None)
        elif reminder is None:
            note = store.update_note(note_id, content)
        else:
            note = store.update_note(note_id, content, normalise_reminder(reminder))
        return f"Updated note {note.note_id}."

    def delete_note(note_id: str) -> str:
        """Delete one unambiguous note identified by its id."""
        store.delete_note(note_id)
        return f"Deleted note {note_id}."

    def get_current_time() -> str:
        """Return the current local time for interpreting time-related questions."""
        return datetime.now().astimezone().isoformat(timespec="seconds")

    return [
        akasha.create_tool(
            "Create a Momo Markdown note. For reminders use only daily {'kind':'daily','time':'HH:MM'} or one-time {'kind':'once','due_at':'ISO date-time'}. Use for durable facts, preferences, commitments, or requested reminders.",
            create_note,
            tool_name="create_note",
        ),
        akasha.create_tool(
            "Update exactly one known Momo note. Ask for clarification if the target is ambiguous.",
            update_note,
            tool_name="update_note",
        ),
        akasha.create_tool(
            "Delete exactly one known Momo note. Ask for clarification if the target is ambiguous.",
            delete_note,
            tool_name="delete_note",
        ),
        akasha.create_tool(
            "Read the current local time when the user asks a time-related question.",
            get_current_time,
            tool_name="get_current_time",
        ),
    ]
