"""Controlled command interface used by the momo-notes Agent Skill."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from note_service import ActivityLog, NoteStore, _UNSET, normalise_reminder


def _store(path: Path) -> NoteStore:
    return NoteStore(path, ActivityLog(path.parent / "momo-activity.jsonl"))


def _note(note) -> dict[str, object]:
    return {"note_id": note.note_id, "content": note.content, "reminder": note.reminder}


def main() -> None:
    parser = argparse.ArgumentParser(description="管理已設定本機 SQLite 資料庫中的 Momo 筆記。")
    parser.add_argument("--database", type=Path, default=Path(os.getenv("LITTLE_AVATAR_DATA_DIR", "data")) / "momo-notes.db")
    parser.add_argument("--data-directory", type=Path, default=Path(os.getenv("LITTLE_AVATAR_DATA_DIR", "data")))
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("content")
    create.add_argument("--reminder")
    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--reminder-kind", choices=("daily", "once"))
    search = subparsers.add_parser("search")
    search.add_argument("query")
    search.add_argument("--reminder-kind", choices=("daily", "once"))
    update = subparsers.add_parser("update")
    update.add_argument("note_id")
    update.add_argument("content")
    update.add_argument("--reminder")
    update.add_argument("--clear-reminder", action="store_true")
    request_delete = subparsers.add_parser("request-delete")
    request_delete.add_argument("note_id")
    request_delete.add_argument("--turn-id", required=True)
    confirm_delete = subparsers.add_parser("confirm-delete")
    confirm_delete.add_argument("note_id")
    confirm_delete.add_argument("--turn-id", required=True)
    subparsers.add_parser("read-schedule")
    arguments = parser.parse_args()

    if arguments.command == "read-schedule":
        schedule_path = arguments.data_directory / "schedule.md"
        sys.stdout.write(
            schedule_path.read_text(encoding="utf-8")
            if schedule_path.exists()
            else "# 晚間行程\n"
        )
        return

    store = _store(arguments.database)
    if arguments.command == "create":
        reminder = normalise_reminder(json.loads(arguments.reminder)) if arguments.reminder else None
        result: object = _note(store.create_note(arguments.content, reminder))
    elif arguments.command == "list":
        result = [_note(note) for note in store.search_notes("", arguments.reminder_kind)]
    elif arguments.command == "search":
        result = [_note(note) for note in store.search_notes(arguments.query, arguments.reminder_kind)]
    elif arguments.command == "update":
        if arguments.clear_reminder and arguments.reminder:
            parser.error("--clear-reminder cannot be combined with --reminder")
        reminder = None if arguments.clear_reminder else (normalise_reminder(json.loads(arguments.reminder)) if arguments.reminder else None)
        value = reminder if (arguments.clear_reminder or arguments.reminder) else _UNSET
        result = _note(store.update_note(arguments.note_id, arguments.content, value))
    elif arguments.command == "request-delete":
        result = {"status": "pending_confirmation", "note": _note(store.request_deletion(arguments.note_id, arguments.turn_id))}
    else:
        store.confirm_deletion(arguments.note_id, arguments.turn_id)
        result = {"status": "deleted", "note_id": arguments.note_id}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
