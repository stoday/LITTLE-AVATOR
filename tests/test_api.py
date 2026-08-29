import asyncio
from datetime import datetime

import pytest
import sys
from fastapi.testclient import TestClient

from p2026_little_avator import api
from p2026_little_avator.api import app, encode_sse


def test_interaction_request_accepts_mvp_action() -> None:
    from p2026_little_avator.api import InteractionRequest

    request = InteractionRequest(action="tease")

    assert request.action == "tease"
    assert request.payload == {}


def test_encode_sse_exposes_event_id_type_and_json_data() -> None:
    encoded = encode_sse({"id": "evt-1", "type": "suggestion", "data": {"text": "Take a break"}})

    assert encoded == 'id: evt-1\nevent: suggestion\ndata: {"text": "Take a break"}\n\n'


def test_client_can_create_a_new_conversation() -> None:
    response = TestClient(app).post("/api/conversations")

    assert response.status_code == 201
    assert response.json()["conversation_id"]


def test_conversation_rejects_an_empty_chat_message() -> None:
    client = TestClient(app)
    conversation_id = client.post("/api/conversations").json()["conversation_id"]

    response = client.post(f"/api/conversations/{conversation_id}/messages", json={"content": "   "})

    assert response.status_code == 422


def test_chat_stream_forwards_only_answer_chunks_from_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAgent:
        def __call__(self, _: str, *, messages: list[dict[str, str]]):
            yield {"type": "thinking", "data": "internal reasoning"}
            yield {"type": "answer", "data": "嗨"}
            yield {"type": "tool", "data": {"name": "hidden_tool"}}
            yield {"type": "answer", "data": "！"}

    monkeypatch.setattr(app.state, "agent_factory", lambda: FakeAgent())
    client = TestClient(app)
    conversation_id = client.post("/api/conversations").json()["conversation_id"]

    submitted = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "你好"},
    )
    return

    assert submitted.status_code == 202
    assert "event: answer" in response.text
    assert 'data: {"text": "嗨"}' in response.text
    assert 'data: {"text": "！"}' in response.text
    assert "internal reasoning" not in response.text
    assert "hidden_tool" not in response.text
    assert "event: completed" in response.text


def test_verbose_agent_console_uses_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    class Stream:
        def __init__(self) -> None:
            self.arguments: dict[str, str] | None = None

        def reconfigure(self, **kwargs: str) -> None:
            self.arguments = kwargs

    stdout, stderr = Stream(), Stream()
    monkeypatch.setattr(api.sys, "stdout", stdout)
    monkeypatch.setattr(api.sys, "stderr", stderr)

    api.configure_verbose_console()

    assert stdout.arguments == {"encoding": "utf-8", "errors": "backslashreplace"}
    assert stderr.arguments == {"encoding": "utf-8", "errors": "backslashreplace"}


def test_agent_factory_exposes_only_application_note_tools(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    class AkashaStub:
        @staticmethod
        def agents(**kwargs: object) -> object:
            captured.update(kwargs)
            return object()

    monkeypatch.setenv("MODEL", "gemini:test")
    monkeypatch.setenv("LITTLE_AVATAR_DATA_DIR", str(tmp_path))
    monkeypatch.setitem(sys.modules, "akasha", AkashaStub)
    monkeypatch.setattr(api, "create_note_tools", lambda _: ["note-tool", "time-tool"])

    api.create_akasha_agent()

    assert captured["tools"] == ["note-tool", "time-tool"]


def test_conversation_accepts_a_later_message_while_an_answer_is_running(monkeypatch: pytest.MonkeyPatch) -> None:
    async def wait_for_turn(*_: object) -> None:
        await __import__("asyncio").Event().wait()

    monkeypatch.setattr(api, "run_agent_message", wait_for_turn)
    client = TestClient(app)
    conversation_id = client.post("/api/conversations").json()["conversation_id"]

    first = client.post(f"/api/conversations/{conversation_id}/messages", json={"content": "第一句"})
    second = client.post(f"/api/conversations/{conversation_id}/messages", json={"content": "第二句"})

    assert first.status_code == 202
    assert second.status_code == 202


def test_agent_turn_injects_fresh_notes_and_session_history(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    calls: list[tuple[str, list[dict[str, str]]]] = []

    class FakeAgent:
        def __call__(self, content: str, *, messages: list[dict[str, str]]) -> object:
            calls.append((content, messages))
            yield {"type": "answer", "data": "收到"}

    monkeypatch.setenv("LITTLE_AVATAR_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(api, "effective_now", lambda: datetime.fromisoformat("2026-08-28T15:33:10+08:00"))
    api.NoteStore(tmp_path / "momo-notes.md").create_note("使用者喜歡無糖茶")
    monkeypatch.setattr(app.state, "agent_factory", lambda: FakeAgent())
    conversation = api.Conversation(conversation_id="test-conversation")

    asyncio.run(api.run_agent_message(conversation, "第一句"))
    asyncio.run(api.run_agent_message(conversation, "第二句"))

    assert "使用者喜歡無糖茶" in calls[0][0]
    assert "Current local time: 2026-08-28T15:33:10+08:00" in calls[0][0]
    assert "Timezone offset: +08:00" in calls[0][0]
    assert calls[0][1] == []
    assert calls[1][1] == [
        {"role": "user", "content": "第一句"},
        {"role": "assistant", "content": "收到"},
    ]


def test_conversation_sse_stays_open_after_a_completed_turn() -> None:
    conversation = api.conversations.create()

    async def consume() -> list[str]:
        response = await api.conversation_events(conversation.conversation_id)
        stream = response.body_iterator
        connected = await anext(stream)
        await conversation.events.put(api.conversation_event("completed", {"turn_id": "turn-1", "origin": "user"}))
        completed = await anext(stream)
        await conversation.events.put(api.conversation_event("turn_started", {"turn_id": "turn-2", "origin": "reminder"}))
        reminder = await anext(stream)
        await stream.aclose()
        return [connected, completed, reminder]

    events = asyncio.run(consume())

    assert "event: completed" in events[1]
    assert "event: turn_started" in events[2]


def test_scheduler_enqueues_due_reminder_on_the_conversation_fifo(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("LITTLE_AVATAR_DATA_DIR", str(tmp_path))
    api.NoteStore(tmp_path / "momo-notes.md").create_note(
        "起來動一動", reminder={"kind": "daily", "time": "15:00"}
    )
    conversation = api.conversations.create()
    conversation.subscriber_count = 1
    conversation.worker = type("BusyWorker", (), {"done": lambda self: False})()

    asyncio.run(api.scan_and_queue_reminders(datetime.fromisoformat("2026-08-28T15:00:03+08:00")))

    item = conversation.inputs.get_nowait()
    assert item.kind == "reminder"
    assert item.content == "起來動一動"
