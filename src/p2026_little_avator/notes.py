"""Markdown-backed notes owned by the Little Avatar application."""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

_NOTE_PATTERN = re.compile(
    r"^## Note (?P<id>[0-9a-f-]{36})\n"
    r"(?P<content>.*?)\n"
    r"<!-- momo-note: (?P<metadata>\{[^\n]*\}) -->$",
    re.MULTILINE | re.DOTALL,
)
_UNSET = object()


@dataclass(frozen=True)
class Note:
    note_id: str
    content: str
    reminder: dict[str, Any] | None


class NoteStore:
    """Read and write the complete small Markdown note collection."""

    def __init__(self, path: Path, activity_log: ActivityLog | None = None) -> None:
        self.path = path
        self.activity_log = activity_log

    def create_note(self, content: str, reminder: dict[str, Any] | None = None) -> Note:
        note = Note(
            note_id=str(uuid.uuid4()),
            content=content.strip(),
            reminder=self._normalise_reminder(reminder),
        )
        document = self._read_document()
        if not document:
            document = "# Momo notes\n"
        self._write_document(f"{document.rstrip()}\n\n{self._render_note(note)}\n")
        self._record("note_created", note.note_id)
        return note

    def list_notes(self) -> list[Note]:
        return [
            Note(
                note_id=match["id"],
                content=match["content"].strip(),
                reminder=json.loads(match["metadata"]).get("reminder"),
            )
            for match in _NOTE_PATTERN.finditer(self._read_document())
        ]

    def read_document(self) -> str:
        """Return the complete current Markdown source, including direct edits."""
        return self._read_document()

    def update_note(
        self,
        note_id: str,
        content: str,
        reminder: dict[str, Any] | None | object = _UNSET,
    ) -> Note:
        existing = next((note for note in self.list_notes() if note.note_id == note_id), None)
        if existing is None:
            raise KeyError(f"Unknown note: {note_id}")
        updated = Note(
            note_id=existing.note_id,
            content=content.strip(),
            reminder=existing.reminder if reminder is _UNSET else self._normalise_reminder(reminder),
        )
        document = _NOTE_PATTERN.sub(
            lambda match: self._render_note(updated) if match["id"] == note_id else match[0],
            self._read_document(),
        )
        self._write_document(document)
        self._record("note_updated", updated.note_id)
        return updated

    def delete_note(self, note_id: str) -> None:
        deleted = False

        def remove(match: re.Match[str]) -> str:
            nonlocal deleted
            if match["id"] == note_id:
                deleted = True
                return ""
            return match[0]

        document = _NOTE_PATTERN.sub(remove, self._read_document())
        if not deleted:
            raise KeyError(f"Unknown note: {note_id}")
        self._write_document(document.rstrip() + "\n")
        self._record("note_deleted", note_id)

    def mark_reminder_handled(self, note_id: str, occurrence: str) -> None:
        """Persist scheduler state without recording it as a user note edit."""
        existing = next((note for note in self.list_notes() if note.note_id == note_id), None)
        if existing is None or existing.reminder is None:
            raise KeyError(f"Unknown reminder note: {note_id}")
        reminder = {**existing.reminder, "last_handled_occurrence": occurrence}
        updated = Note(note_id=note_id, content=existing.content, reminder=reminder)
        document = _NOTE_PATTERN.sub(
            lambda match: self._render_note(updated) if match["id"] == note_id else match[0],
            self._read_document(),
        )
        self._write_document(document)

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

    def _read_document(self) -> str:
        if not self.path.exists():
            return ""
        return self.path.read_text(encoding="utf-8")

    def _write_document(self, document: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(document, encoding="utf-8")
        os.replace(temporary, self.path)

    @staticmethod
    def _render_note(note: Note) -> str:
        metadata = json.dumps(
            {"id": note.note_id, "reminder": note.reminder},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return f"## Note {note.note_id}\n{note.content}\n<!-- momo-note: {metadata} -->"


class ActivityLog:
    """Append only, product-level note and reminder activity."""

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
