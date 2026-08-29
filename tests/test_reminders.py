from datetime import datetime

from p2026_little_avator.notes import ActivityLog, NoteStore
from p2026_little_avator.reminders import ReminderScanner


def test_due_daily_reminder_is_queued_once_when_a_client_is_connected(tmp_path) -> None:
    activity_log = ActivityLog(tmp_path / "momo-activity.jsonl")
    store = NoteStore(tmp_path / "momo-notes.md", activity_log=activity_log)
    note = store.create_note("起來動一動", reminder={"kind": "daily", "time": "15:00"})
    scanner = ReminderScanner(store, activity_log)
    now = datetime.fromisoformat("2026-08-28T15:00:03+08:00")

    due = scanner.scan(now=now, has_subscriber=True)

    assert [(item.note_id, item.occurrence, item.prose) for item in due] == [
        (note.note_id, "2026-08-28T15:00:00+08:00", "起來動一動")
    ]
    assert scanner.scan(now=now, has_subscriber=True) == []


def test_due_reminder_without_client_is_skipped_and_audited(tmp_path) -> None:
    activity_log = ActivityLog(tmp_path / "momo-activity.jsonl")
    store = NoteStore(tmp_path / "momo-notes.md", activity_log=activity_log)
    note = store.create_note("起來動一動", reminder={"kind": "daily", "time": "15:00"})
    scanner = ReminderScanner(store, activity_log)

    assert scanner.scan(now=datetime.fromisoformat("2026-08-28T15:00:03+08:00"), has_subscriber=False) == []
    assert activity_log.read()[-1] == {
        "timestamp": activity_log.read()[-1]["timestamp"],
        "type": "skipped_no_client",
        "note_id": note.note_id,
        "occurrence": "2026-08-28T15:00:00+08:00",
        "source": "scheduler",
    }
