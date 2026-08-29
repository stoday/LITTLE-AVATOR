from p2026_little_avator.notes import ActivityLog, NoteStore
import pytest


def test_created_daily_reminder_is_readable_by_a_new_store(tmp_path) -> None:
    notes_path = tmp_path / "momo-notes.md"
    writer = NoteStore(notes_path)

    created = writer.create_note(
        "每天三點提醒我起來動一動。",
        reminder={"kind": "daily", "time": "15:00"},
    )

    notes = NoteStore(notes_path).list_notes()

    assert notes == [created]
    assert notes[0].reminder == {
        "kind": "daily",
        "time": "15:00",
        "enabled": True,
        "last_handled_occurrence": None,
    }


def test_note_can_be_updated_by_its_stable_id(tmp_path) -> None:
    store = NoteStore(tmp_path / "momo-notes.md")
    created = store.create_note("下午要寄信。")

    updated = store.update_note(created.note_id, "下午四點要寄信。")

    assert updated.content == "下午四點要寄信。"
    assert NoteStore(store.path).list_notes() == [updated]


def test_note_can_be_deleted_by_its_stable_id(tmp_path) -> None:
    store = NoteStore(tmp_path / "momo-notes.md")
    retained = store.create_note("保留這則筆記。")
    deleted = store.create_note("刪除這則筆記。")

    store.delete_note(deleted.note_id)

    assert NoteStore(store.path).list_notes() == [retained]


def test_activity_log_appends_one_json_object_per_action(tmp_path) -> None:
    log = ActivityLog(tmp_path / "momo-activity.jsonl")

    log.append("note_created", note_id="note-1", source="tool")
    log.append("note_deleted", note_id="note-1", source="tool")

    records = log.read()

    assert [(record["type"], record["note_id"], record["source"]) for record in records] == [
        ("note_created", "note-1", "tool"),
        ("note_deleted", "note-1", "tool"),
    ]
    assert all(record["timestamp"] for record in records)


def test_deleting_an_unknown_note_is_rejected(tmp_path) -> None:
    store = NoteStore(tmp_path / "momo-notes.md")
    store.create_note("保留這則筆記。")

    with pytest.raises(KeyError, match="Unknown note"):
        store.delete_note("00000000-0000-0000-0000-000000000000")


def test_note_mutations_are_recorded_in_the_activity_log(tmp_path) -> None:
    activity = ActivityLog(tmp_path / "momo-activity.jsonl")
    store = NoteStore(tmp_path / "momo-notes.md", activity_log=activity)

    created = store.create_note("記錄這則。")
    store.update_note(created.note_id, "修改這則。")
    store.delete_note(created.note_id)

    assert [record["type"] for record in activity.read()] == [
        "note_created",
        "note_updated",
        "note_deleted",
    ]
