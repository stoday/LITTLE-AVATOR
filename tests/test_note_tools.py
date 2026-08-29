from p2026_little_avator.note_tools import create_note_tools
from p2026_little_avator.notes import NoteStore
import pytest


def test_create_note_tool_creates_a_markdown_note(tmp_path) -> None:
    store = NoteStore(tmp_path / "momo-notes.md")
    tools = {tool.name: tool for tool in create_note_tools(store)}

    result = tools["create_note"].invoke({"content": "我喜歡無糖茶。"})

    assert result.startswith("Created note ")
    assert [note.content for note in store.list_notes()] == ["我喜歡無糖茶。"]
def test_update_note_tool_preserves_an_existing_reminder_when_omitted(tmp_path) -> None:
    store = NoteStore(tmp_path / "momo-notes.md")
    note = store.create_note("original", reminder={"kind": "daily", "time": "15:00"})
    tools = {tool.name: tool for tool in create_note_tools(store)}

    tools["update_note"].invoke({"note_id": note.note_id, "content": "changed"})

    assert store.list_notes()[0].reminder == {
        "kind": "daily",
        "time": "15:00",
        "enabled": True,
        "last_handled_occurrence": None,
    }


def test_create_note_tool_normalises_a_model_one_time_reminder(tmp_path) -> None:
    store = NoteStore(tmp_path / "momo-notes.md")
    tools = {tool.name: tool for tool in create_note_tools(store)}

    tools["create_note"].invoke(
        {
            "content": "stand up and stretch",
            "reminder": {"time": "2026-08-28T15:33:00+08:00", "text": "stand up and stretch"},
        }
    )

    assert store.list_notes()[0].reminder == {
        "kind": "once",
        "due_at": "2026-08-28T15:33:00+08:00",
        "enabled": True,
        "last_handled_occurrence": None,
    }


def test_create_note_tool_rejects_an_unsupported_reminder_before_writing(tmp_path) -> None:
    store = NoteStore(tmp_path / "momo-notes.md")
    tools = {tool.name: tool for tool in create_note_tools(store)}

    with pytest.raises(ValueError, match="reminder"):
        tools["create_note"].invoke({"content": "stretch", "reminder": {"kind": "weekly", "time": "15:33"}})

    assert store.list_notes() == []
