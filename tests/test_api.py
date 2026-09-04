import asyncio
import builtins
import json
from datetime import datetime

import akasha
import pytest
from fastapi.testclient import TestClient

from p2026_little_avator import api
from p2026_little_avator.api import app, encode_sse


def test_interaction_request_accepts_mvp_action() -> None:
    assert api.InteractionRequest(action="tease").action == "tease"


def test_encode_sse_exposes_event_id_type_and_json_data() -> None:
    assert encode_sse({"id": "evt-1", "type": "suggestion", "data": {"text": "Take a break"}}) == (
        'id: evt-1\nevent: suggestion\ndata: {"text": "Take a break"}\n\n'
    )


def test_client_can_create_a_new_conversation() -> None:
    response = TestClient(app).post("/api/conversations")
    assert response.status_code == 201
    assert response.json()["conversation_id"]


def test_conversation_rejects_an_empty_chat_message() -> None:
    client = TestClient(app)
    conversation_id = client.post("/api/conversations").json()["conversation_id"]
    assert client.post(f"/api/conversations/{conversation_id}/messages", json={"content": "   "}).status_code == 422


def test_regular_agent_receives_the_explicit_momo_notes_skill(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_agents(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setenv("MODEL", "gemini:test")
    monkeypatch.setattr(akasha, "agents", fake_agents)
    api.create_akasha_agent()

    assert captured["tools"] == []
    assert [path.name for path in captured["skills"]] == ["momo-notes"]


def test_communicator_turn_builds_an_agent_with_only_the_explicit_momo_notes_skill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeAgent:
        def __call__(self, prompt: str, *, messages: list[dict[str, str]]):
            captured["delegated_prompt"] = prompt
            yield {"type": "answer", "data": "message for peer"}

    monkeypatch.setenv("MODEL", "gemini:test")
    monkeypatch.setattr(akasha, "agents", lambda **kwargs: captured.update(kwargs) or FakeAgent())

    assert api.run_communicator_turn(
        request="ask the contact to talk", contact_name="Mia", peer_message=None, transcript=[]
    ) == "message for peer"
    assert captured["tools"] == []
    assert [path.name for path in captured["skills"]] == ["momo-notes"]
    assert captured["thinking"] is False
    system_prompt = str(captured["system_prompt"])
    assert "agent-x-communicator" in system_prompt
    assert "Traditional Chinese" in system_prompt
    assert "Simplified Chinese" in system_prompt
    assert "one candidate at a time" in system_prompt
    assert "must not make commitments" in system_prompt
    delegated_prompt = str(captured["delegated_prompt"])
    assert "must load momo-notes and consult the relevant local information" in delegated_prompt
    assert "must not reply with only a notification" in delegated_prompt
    assert "incoming peer message is a live discussion turn, not a notification" in delegated_prompt
    assert "must load momo-notes before deciding how to answer" in delegated_prompt
    assert "confirm, reject, or counter-propose that specific item to the peer" in delegated_prompt
    assert "Never call read_skill_resource for schedule.md" in delegated_prompt
    assert "python_execute with skill='momo-notes', source='scripts/note_cli.py', and args=['read-schedule']" in delegated_prompt


def test_communicator_turn_records_the_transcript_passed_to_akasha(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    class FakeAgent:
        def __call__(self, prompt: str, *, messages: list[dict[str, str]]):
            assert messages == [
                {"role": "assistant", "content": "Can Tuesday work?"},
                {"role": "user", "content": "How about Friday?"},
            ]
            yield {"type": "answer", "data": "I will check Friday locally."}

    monkeypatch.setenv("MODEL", "gemini:test")
    monkeypatch.setenv("LITTLE_AVATAR_A2A_AGENT_ID", "avatar-a")
    monkeypatch.setenv("LITTLE_AVATAR_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(akasha, "agents", lambda **kwargs: FakeAgent())

    assert api.run_communicator_turn(
        request="Arrange a time",
        contact_name="Mia",
        peer_message="How about Friday?",
        transcript=[
            {"speaker": "Local communicator", "text": "Can Tuesday work?"},
            {"speaker": "Peer communicator", "text": "How about Friday?"},
        ],
    ) == "I will check Friday locally."

    records = [json.loads(line) for line in (tmp_path / "a2a-communicator-trace.jsonl").read_text(encoding="utf-8").splitlines()]
    input_record = next(record for record in records if record["event"] == "communicator_input")
    assert input_record["local_agent_id"] == "avatar-a"
    assert input_record["debug_breakpoint_enabled"] is False
    assert input_record["debug_breakpoint_agent_id"] == ""
    assert input_record["python_breakpoint_hook"] is None
    assert input_record["peer_message"] == "How about Friday?"
    assert input_record["transcript"] == [
        {"speaker": "Local communicator", "text": "Can Tuesday work?"},
        {"speaker": "Peer communicator", "text": "How about Friday?"},
    ]


def test_communicator_turn_records_the_answer_output_yielded_by_akasha(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    class FakeAgent:
        def __call__(self, prompt: str, *, messages: list[dict[str, str]]):
            yield {"type": "thinking", "data": "private reasoning"}
            yield {"type": "answer", "data": "週六晚上七點我會先請使用者確認。"}

    monkeypatch.setenv("MODEL", "gemini:test")
    monkeypatch.setenv("LITTLE_AVATAR_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(akasha, "agents", lambda **kwargs: FakeAgent())

    api.run_communicator_turn(
        request="Arrange a time", contact_name="Mia", peer_message="Can Saturday work?", transcript=[]
    )

    records = [json.loads(line) for line in (tmp_path / "a2a-communicator-trace.jsonl").read_text(encoding="utf-8").splitlines()]
    assert records[-1]["event"] == "communicator_completed"
    assert records[-1]["answer"] == "週六晚上七點我會先請使用者確認。"
    assert records[-1]["event_types"] == ["thinking", "answer"]


def test_communicator_turn_records_when_akasha_yields_no_output_and_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    class FakeAgent:
        def __call__(self, prompt: str, *, messages: list[dict[str, str]]):
            raise RuntimeError("LangChain agent returned no final answer")
            yield  # pragma: no cover

    monkeypatch.setenv("MODEL", "gemini:test")
    monkeypatch.setenv("LITTLE_AVATAR_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(akasha, "agents", lambda **kwargs: FakeAgent())

    with pytest.raises(RuntimeError, match="returned no final answer"):
        api.run_communicator_turn(
            request="Arrange a time", contact_name="Mia", peer_message="Can Saturday work?", transcript=[]
        )

    records = [json.loads(line) for line in (tmp_path / "a2a-communicator-trace.jsonl").read_text(encoding="utf-8").splitlines()]
    assert records[-1]["event"] == "communicator_failed"
    assert records[-1]["event_types"] == []
    assert records[-1]["answer"] == ""
    assert records[-1]["error"] == "LangChain agent returned no final answer"


def test_communicator_debug_breakpoint_is_opt_in_and_can_target_one_avatar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pauses: list[object] = []
    monkeypatch.setenv("LITTLE_AVATAR_A2A_BREAKPOINT", "true")
    monkeypatch.setenv("LITTLE_AVATAR_A2A_BREAKPOINT_AGENT_ID", "avatar-a")
    monkeypatch.setenv("LITTLE_AVATAR_A2A_AGENT_ID", "avatar-a")
    monkeypatch.setattr(builtins, "breakpoint", lambda: pauses.append("paused"))

    api.maybe_pause_communicator_debugger("before_agent", {"peer_message": "Friday?"})

    assert pauses == ["paused"]


def test_agent_factory_injects_this_avatar_identity_into_the_system_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setenv("MODEL", "gemini:test")
    monkeypatch.setenv("LITTLE_AVATAR_IDENTITY", "Momo A（邀約者）")
    monkeypatch.setattr(akasha, "agents", lambda **kwargs: captured.update(kwargs) or object())

    api.create_akasha_agent()

    assert "Momo A（邀約者）" in str(captured["system_prompt"])
    assert "When asked who you are" in str(captured["system_prompt"])


def test_agent_turn_injects_fresh_notes_history_and_turn_id(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    calls: list[tuple[str, list[dict[str, str]]]] = []

    class FakeAgent:
        def __call__(self, content: str, *, messages: list[dict[str, str]]):
            calls.append((content, messages))
            yield {"type": "answer", "data": "ok"}

    monkeypatch.setenv("LITTLE_AVATAR_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(api, "effective_now", lambda: datetime.fromisoformat("2026-08-28T15:33:10+08:00"))
    api.note_runtime().store.create_note("user likes tea")
    monkeypatch.setattr(app.state, "agent_factory", lambda: FakeAgent())
    conversation = api.Conversation(conversation_id="test-conversation")

    asyncio.run(api.run_agent_message(conversation, "first"))
    asyncio.run(api.run_agent_message(conversation, "second"))

    assert "user likes tea" in calls[0][0]
    assert "User turn ID:" in calls[0][0]
    assert calls[0][1] == []
    assert calls[1][1] == [{"role": "user", "content": "first"}, {"role": "assistant", "content": "ok"}]


def test_agent_turn_publishes_safe_progress_states_without_exposing_verbose_content(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    class FakeAgent:
        def __call__(self, content: str, *, messages: list[dict[str, str]]):
            yield {"type": "thinking", "data": "private chain of thought"}
            yield {"type": "tool", "data": {"arguments": "private note contents"}}
            yield {"type": "answer", "data": "ok"}

    monkeypatch.setenv("LITTLE_AVATAR_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(app.state, "agent_factory", lambda: FakeAgent())
    conversation = api.Conversation(conversation_id="status-conversation")

    asyncio.run(api.run_agent_message(conversation, "first"))

    events = [conversation.events.get_nowait() for _ in range(conversation.events.qsize())]
    assert [event["data"]["text"] for event in events if event["type"] == "status"] == [
        "正在分析需求",
        "正在使用已授權工具",
    ]
    assert all("private" not in str(event) for event in events)


def test_admin_communicator_tool_starts_a_background_task_without_nesting_a_communicator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITTLE_AVATAR_ADMIN_PROFILE", '{"contacts":{"Mia":"agent-b"}}')

    class FakeModule:
        def create_discussion_task(self, peer_agent_id: str, contact_name: str, request: str):
            assert peer_agent_id == "agent-b"
            assert contact_name == "Mia"
            assert request == "ask her to talk"
            return {"context_id": "ctx-1", "peer_agent_id": peer_agent_id, "status": "queued"}

    monkeypatch.setattr(api.CollaborationModule, "from_environment", lambda: FakeModule())
    started: list[str] = []
    monkeypatch.setattr(api, "start_background_discussion", lambda context_id: started.append(context_id))

    result = json.loads(api.communicate_with_contact("Mia", "ask her to talk"))

    assert result["peer_agent_id"] == "agent-b"
    assert result["context_id"] == "ctx-1"
    assert result["status"] == "started"
    assert started == ["ctx-1"]


def test_background_discussion_runner_continues_after_a_counterproposal_until_local_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITTLE_AVATAR_ADMIN_PROFILE", '{"contacts":{"Mia":"agent-b"}}')
    turns = iter(
        [
            "first communicator message\n[[A2A_STATE:continue]]",
            "second communicator message\n[[A2A_STATE:continue]]",
            "third communicator message\n[[A2A_STATE:await_local_confirmation]]",
        ]
    )

    def fake_turn(**kwargs: object) -> str:
        return next(turns)

    class FakeModule:
        def get_discussion_task(self, context_id: str):
            assert context_id == "ctx-2"
            return {
                "context_id": context_id,
                "peer_agent_id": "agent-b",
                "contact_name": "Mia",
                "request": "ask her to talk",
                "status": "queued",
            }

        def update_discussion_task(self, context_id: str, **changes: object) -> None:
            updates.append((context_id, changes))

        def send_discussion_turn(self, peer_agent_id: str, context_id: str, content: str) -> str:
            sent.append((peer_agent_id, context_id, content))
            return f"peer reply {len(sent)}"

        def discussion_transcript(self, context_id: str):
            return [
                {"speaker": "Local communicator", "text": "first communicator message"},
                {"speaker": "Peer communicator", "text": "first peer reply"},
            ]

        def record_admin_notification(self, context_id: str, summary: str) -> None:
            notifications.append((context_id, summary))

        def finish_discussion_task(self, context_id: str) -> None:
            finished.append(context_id)

    monkeypatch.setattr(api, "run_communicator_turn", fake_turn)
    monkeypatch.setattr(api.CollaborationModule, "from_environment", lambda: FakeModule())
    admin_reports: list[object] = []

    def admin_reporter(report: object) -> str:
        admin_reports.append(report)
        return "A-admin：與 Mia 已暫定時間，仍需本機使用者確認。"

    monkeypatch.setattr(api.app.state, "admin_reporter", admin_reporter, raising=False)
    sent: list[tuple[str, str, str]] = []
    updates: list[tuple[str, dict[str, object]]] = []
    notifications: list[tuple[str, str]] = []
    finished: list[str] = []

    api.run_discussion_task("ctx-2")

    assert sent == [
        ("agent-b", "ctx-2", "first communicator message"),
        ("agent-b", "ctx-2", "second communicator message"),
        ("agent-b", "ctx-2", "third communicator message"),
    ]
    assert any(changes.get("status") == "completed" for _, changes in updates)
    assert len(admin_reports) == 1
    report = admin_reports[0]
    assert getattr(report, "context_id") == "ctx-2"
    assert getattr(report, "outcome") == "await_local_confirmation"
    assert getattr(report, "contact_name") == "Mia"
    assert notifications == [
        ("ctx-2", "A-admin：與 Mia 已暫定時間，仍需本機使用者確認。")
    ]
    assert finished == ["ctx-2"]


def test_background_discussion_runner_reports_when_turn_limit_is_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITTLE_AVATAR_A2A_MAX_OUTBOUND_TURNS", "2")
    monkeypatch.setenv("LITTLE_AVATAR_ADMIN_PROFILE", '{"contacts":{"Mia":"agent-b"}}')

    class FakeModule:
        def get_discussion_task(self, context_id: str):
            return {
                "context_id": context_id,
                "peer_agent_id": "agent-b",
                "contact_name": "Mia",
                "request": "keep discussing",
                "status": "queued",
            }

        def update_discussion_task(self, context_id: str, **changes: object) -> None:
            updates.append((context_id, changes))

        def send_discussion_turn(self, peer_agent_id: str, context_id: str, content: str) -> str:
            sent.append((peer_agent_id, context_id, content))
            return "please make another proposal"

        def discussion_transcript(self, context_id: str):
            return []

        def record_admin_notification(self, context_id: str, summary: str) -> None:
            notifications.append((context_id, summary))

        def finish_discussion_task(self, context_id: str) -> None:
            finished.append(context_id)

    monkeypatch.setattr(
        api,
        "run_communicator_turn",
        lambda **_: "another proposal\n[[A2A_STATE:continue]]",
    )
    monkeypatch.setattr(api.CollaborationModule, "from_environment", lambda: FakeModule())
    admin_reports: list[object] = []

    def admin_reporter(report: object) -> str:
        admin_reports.append(report)
        return "A-admin：協商已達 2 輪上限，目前尚未得到結論。"

    monkeypatch.setattr(api.app.state, "admin_reporter", admin_reporter, raising=False)
    sent: list[tuple[str, str, str]] = []
    updates: list[tuple[str, dict[str, object]]] = []
    notifications: list[tuple[str, str]] = []
    finished: list[str] = []

    api.run_discussion_task("ctx-limit")

    assert len(sent) == 2
    assert any(changes.get("status") == "limit_reached" for _, changes in updates)
    assert len(admin_reports) == 1
    assert getattr(admin_reports[0], "outcome") == "limit_reached"
    assert notifications == [("ctx-limit", "A-admin：協商已達 2 輪上限，目前尚未得到結論。")]
    assert finished == ["ctx-limit"]


def test_background_discussion_failure_is_reported_to_the_local_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeModule:
        def get_discussion_task(self, context_id: str):
            return {
                "context_id": context_id,
                "peer_agent_id": "agent-b",
                "contact_name": "Mia",
                "request": "ask her to talk",
                "status": "queued",
            }

        def update_discussion_task(self, context_id: str, **changes: object) -> None:
            updates.append((context_id, changes))

        def discussion_transcript(self, context_id: str):
            return []

        def record_admin_notification(self, context_id: str, summary: str) -> None:
            notifications.append((context_id, summary))

        def finish_discussion_task(self, context_id: str) -> None:
            finished.append(context_id)

    monkeypatch.setattr(
        api,
        "run_communicator_turn",
        lambda **_: (_ for _ in ()).throw(RuntimeError("communicator unavailable")),
    )
    monkeypatch.setattr(api.CollaborationModule, "from_environment", lambda: FakeModule())
    admin_reports: list[object] = []

    def admin_reporter(report: object) -> str:
        admin_reports.append(report)
        return "A-admin：與 Mia 的協商失敗，目前無法取得結果。"

    monkeypatch.setattr(api.app.state, "admin_reporter", admin_reporter, raising=False)
    updates: list[tuple[str, dict[str, object]]] = []
    notifications: list[tuple[str, str]] = []
    finished: list[str] = []

    api.run_discussion_task("ctx-failed")

    assert any(changes.get("status") == "failed" for _, changes in updates)
    assert len(admin_reports) == 1
    report = admin_reports[0]
    assert getattr(report, "outcome") == "failed"
    assert "communicator unavailable" in getattr(report, "result")
    assert notifications == [("ctx-failed", "A-admin：與 Mia 的協商失敗，目前無法取得結果。")]
    assert finished == ["ctx-failed"]


def test_discussion_turn_limit_defaults_to_thirty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LITTLE_AVATAR_A2A_MAX_OUTBOUND_TURNS", raising=False)

    assert api._discussion_turn_limit() == 30


def test_communicator_message_state_is_removed_before_a2a_delivery() -> None:
    assert api.communicator_message_and_state("討論下一個候選時段。\n[[A2A_STATE:continue]]") == (
        "討論下一個候選時段。",
        "continue",
    )


def test_inbound_communicator_removes_its_private_state_marker_before_replying_to_a_peer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api,
        "run_communicator_turn",
        lambda **_: "暫定週六晚上可行。\n[[A2A_STATE:await_local_confirmation]]",
    )

    assert api.respond_to_a2a_peer("週六晚上可以嗎？", []) == "暫定週六晚上可行。"
    assert api.communicator_message_and_state("暫定週六晚上可行。\n[[A2A_STATE:await_local_confirmation]]") == (
        "暫定週六晚上可行。",
        "await_local_confirmation",
    )


def test_background_completion_is_published_to_connected_desktop_clients() -> None:
    async def receive_notification() -> dict[str, object]:
        queue = api.broker.subscribe()
        api.app.state.event_loop = asyncio.get_running_loop()
        try:
            api.publish_background_admin_notification("ctx-3", "協商已完成，暫定結果已就緒。")
            return await asyncio.wait_for(queue.get(), timeout=1)
        finally:
            api.broker.unsubscribe(queue)

    event = asyncio.run(receive_notification())
    assert event["id"]
    assert event["type"] == "admin_notification"
    assert event["data"] == {
        "title": "協商更新",
        "text": "協商已完成，暫定結果已就緒。",
        "context_id": "ctx-3",
    }


def test_scheduler_enqueues_due_reminder(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("LITTLE_AVATAR_DATA_DIR", str(tmp_path))
    api.note_runtime().store.create_note("stretch", reminder={"kind": "daily", "time": "15:00"})
    conversation = api.conversations.create()
    conversation.subscriber_count = 1
    conversation.worker = type("BusyWorker", (), {"done": lambda self: False})()

    asyncio.run(api.scan_and_queue_reminders(datetime.fromisoformat("2026-08-28T15:00:03+08:00")))

    assert conversation.inputs.get_nowait().content == "stretch"
