from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import subprocess
import sys

import pytest

from p2026_little_avator.skills import load_skill_runtime


def runtime(tmp_path: Path):
    return load_skill_runtime("momo-notes").create_runtime(data_directory=tmp_path)


def test_existing_sqlite_notes_schema_remains_readable(tmp_path: Path) -> None:
    writer = runtime(tmp_path)
    created = writer.store.create_note("existing note", {"kind": "daily", "time": "15:00"})
    assert runtime(tmp_path).store.list_notes() == [created]


def test_schedule_is_read_from_the_avatar_local_markdown_file(tmp_path: Path) -> None:
    (tmp_path / "schedule.md").write_text(
        "# Evening schedule\n\n- Wednesday 18:00 | busy\n- Wednesday 19:00 | available\n",
        encoding="utf-8",
    )

    assert runtime(tmp_path).read_schedule() == (
        "# Evening schedule\n\n- Wednesday 18:00 | busy\n- Wednesday 19:00 | available\n"
    )


def test_skill_cli_exposes_the_local_schedule_to_a_communicator(tmp_path: Path) -> None:
    (tmp_path / "schedule.md").write_text("- Thursday 19:00 | available\n", encoding="utf-8")
    command = Path(__file__).parents[1] / "scripts" / "note_cli.py"

    result = subprocess.run(
        [sys.executable, str(command), "--data-directory", str(tmp_path), "read-schedule"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == "- Thursday 19:00 | available\n"


def test_search_filters_keyword_and_reminder_kind(tmp_path: Path) -> None:
    store = runtime(tmp_path).store
    daily = store.create_note("buy green tea", {"kind": "daily", "time": "15:00"})
    store.create_note("buy coffee", {"kind": "once", "due_at": "2026-08-31T16:00:00+08:00"})
    assert store.search_notes("green", "daily") == [daily]
    assert store.search_notes("buy", "once")[0].content == "buy coffee"


def test_deletion_requires_a_later_turn(tmp_path: Path) -> None:
    store = runtime(tmp_path).store
    note = store.create_note("remove me")
    store.request_deletion(note.note_id, "turn-1")
    with pytest.raises(ValueError, match="later user turn"):
        store.confirm_deletion(note.note_id, "turn-1")
    store.confirm_deletion(note.note_id, "turn-2")
    assert store.list_notes() == []


def test_due_daily_reminder_is_queued_once(tmp_path: Path) -> None:
    skill = runtime(tmp_path)
    note = skill.store.create_note("stretch", {"kind": "daily", "time": "15:00"})
    now = datetime.fromisoformat("2026-08-28T15:00:03+08:00")
    assert [(item.note_id, item.occurrence, item.prose) for item in skill.scan_reminders(now=now, has_subscriber=True)] == [
        (note.note_id, "2026-08-28T15:00:00+08:00", "stretch")
    ]
    assert skill.scan_reminders(now=now, has_subscriber=True) == []


def test_concurrent_creation_preserves_every_note(tmp_path: Path) -> None:
    with ThreadPoolExecutor(max_workers=3) as executor:
        list(executor.map(lambda index: runtime(tmp_path).store.create_note(f"note-{index}"), range(3)))
    assert {note.content for note in runtime(tmp_path).store.list_notes()} == {"note-0", "note-1", "note-2"}
