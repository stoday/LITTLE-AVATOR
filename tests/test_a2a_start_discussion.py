from __future__ import annotations

from fastapi.testclient import TestClient
import requests

from p2026_little_avator.api import app
from p2026_little_avator.collaboration import CollaborationModule


class _PeerResponse:
    def __init__(self, context_id: str) -> None:
        self._context_id = context_id

    status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "message": {
                "messageId": "peer-message-001",
                "contextId": self._context_id,
                "role": "ROLE_AGENT",
                "parts": [{"text": "I recommend Tuesday afternoon."}],
            }
        }


def test_local_user_can_start_an_a2a_discussion_with_a_configured_peer(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("LITTLE_AVATAR_A2A_DB", str(tmp_path / "a2a.db"))
    monkeypatch.setenv("LITTLE_AVATAR_A2A_AGENT_ID", "agent-a")
    monkeypatch.setenv(
        "LITTLE_AVATAR_A2A_OUTBOUND_PEERS",
        '{"agent-b":{"url":"http://peer.example/a2a","credential":"peer-secret"}}',
    )
    def peer_post(url: str, **kwargs) -> _PeerResponse:
        assert url == "http://peer.example/a2a/message:send"
        assert kwargs["headers"]["Authorization"] == "Bearer peer-secret"
        return _PeerResponse(kwargs["json"]["message"]["contextId"])

    monkeypatch.setattr("requests.post", peer_post)

    response = TestClient(app).post(
        "/api/collaborations",
        json={"peerAgentId": "agent-b", "content": "What time works for you?"},
    )

    assert response.status_code == 202
    assert response.json()["peer_agent_id"] == "agent-b"
    assert response.json()["reply"] == "I recommend Tuesday afternoon."
    assert response.json()["context_id"]


def test_initiator_controls_a_bounded_second_peer_turn(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LITTLE_AVATAR_A2A_DB", str(tmp_path / "a2a.db"))
    monkeypatch.setenv("LITTLE_AVATAR_A2A_AGENT_ID", "agent-a")
    monkeypatch.setenv(
        "LITTLE_AVATAR_A2A_OUTBOUND_PEERS",
        '{"agent-b":{"url":"http://peer.example/a2a","credential":"peer-secret"}}',
    )
    calls: list[dict] = []

    def peer_post(url: str, **kwargs) -> _PeerResponse:
        calls.append(kwargs["json"])
        return _PeerResponse(kwargs["json"]["message"]["contextId"])

    monkeypatch.setattr("requests.post", peer_post)
    monkeypatch.setattr(
        app.state,
        "a2a_decider",
        lambda peer_reply, rounds: "Can you clarify the afternoon?" if rounds == 1 else None,
        raising=False,
    )

    response = TestClient(app).post(
        "/api/collaborations",
        json={"peerAgentId": "agent-b", "content": "What time works for you?"},
    )

    assert response.status_code == 202
    assert len(calls) == 2
    assert calls[1]["message"]["parts"] == [{"text": "Can you clarify the afternoon?"}]


def test_discussion_task_persists_one_context_across_two_outbound_a2a_turns(
    monkeypatch, tmp_path
) -> None:
    database_path = tmp_path / "a2a.db"
    monkeypatch.setenv("LITTLE_AVATAR_A2A_AGENT_ID", "agent-a")
    monkeypatch.setenv(
        "LITTLE_AVATAR_A2A_OUTBOUND_PEERS",
        '{"agent-b":{"url":"http://peer.example/a2a","credential":"peer-secret"}}',
    )
    calls: list[dict] = []

    def peer_post(url: str, **kwargs) -> _PeerResponse:
        calls.append(kwargs["json"])
        return _PeerResponse(kwargs["json"]["message"]["contextId"])

    monkeypatch.setattr("requests.post", peer_post)
    module = CollaborationModule(database_path, {})

    task = module.create_discussion_task("agent-b", "Mia", "Arrange a time")
    context_id = task["context_id"]
    assert module.get_discussion_task(context_id)["status"] == "queued"

    assert module.send_discussion_turn("agent-b", context_id, "Can Tuesday work?")
    assert module.send_discussion_turn("agent-b", context_id, "How about Wednesday instead?")
    module.update_discussion_task(context_id, status="completed", rounds=2, result="Wednesday works")
    module.finish_discussion_task(context_id)

    assert [call["message"]["contextId"] for call in calls] == [context_id, context_id]
    assert [item["text"] for item in module.discussion_transcript(context_id)] == [
        "Can Tuesday work?",
        "I recommend Tuesday afternoon.",
        "How about Wednesday instead?",
        "I recommend Tuesday afternoon.",
    ]
    completed = module.get_discussion_task(context_id)
    assert completed["status"] == "completed"
    assert completed["rounds"] == 2


def test_discussion_stops_before_a_second_turn_when_token_budget_is_used(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("LITTLE_AVATAR_A2A_DB", str(tmp_path / "a2a.db"))
    monkeypatch.setenv("LITTLE_AVATAR_A2A_AGENT_ID", "agent-a")
    monkeypatch.setenv(
        "LITTLE_AVATAR_A2A_OUTBOUND_PEERS",
        '{"agent-b":{"url":"http://peer.example/a2a","credential":"peer-secret"}}',
    )
    monkeypatch.setattr(
        "p2026_little_avator.collaboration.MAX_DISCUSSION_TOKEN_BUDGET", 5
    )
    calls: list[dict] = []

    def peer_post(url: str, **kwargs) -> _PeerResponse:
        calls.append(kwargs["json"])
        return _PeerResponse(kwargs["json"]["message"]["contextId"])

    monkeypatch.setattr("requests.post", peer_post)
    monkeypatch.setattr(
        app.state,
        "a2a_decider",
        lambda peer_reply, rounds: "one more local turn",
        raising=False,
    )

    response = TestClient(app).post(
        "/api/collaborations",
        json={"peerAgentId": "agent-b", "content": "initial discussion"},
    )

    assert response.status_code == 202
    assert len(calls) == 1


def test_discussion_stops_before_a_second_turn_when_time_limit_expires(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("LITTLE_AVATAR_A2A_DB", str(tmp_path / "a2a.db"))
    monkeypatch.setenv("LITTLE_AVATAR_A2A_AGENT_ID", "agent-a")
    monkeypatch.setenv(
        "LITTLE_AVATAR_A2A_OUTBOUND_PEERS",
        '{"agent-b":{"url":"http://peer.example/a2a","credential":"peer-secret"}}',
    )
    calls: list[dict] = []

    def peer_post(url: str, **kwargs) -> _PeerResponse:
        calls.append(kwargs["json"])
        return _PeerResponse(kwargs["json"]["message"]["contextId"])

    timestamps = iter((0.0, 0.0, 61.0))
    monkeypatch.setattr("requests.post", peer_post)
    monkeypatch.setattr(
        "p2026_little_avator.collaboration.current_monotonic", lambda: next(timestamps)
    )
    monkeypatch.setattr(
        app.state,
        "a2a_decider",
        lambda peer_reply, rounds: "one more local turn",
        raising=False,
    )

    response = TestClient(app).post(
        "/api/collaborations",
        json={"peerAgentId": "agent-b", "content": "initial discussion"},
    )

    assert response.status_code == 202
    assert len(calls) == 1


def test_second_active_discussion_reports_that_the_peer_is_busy(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "a2a.db"
    monkeypatch.setenv("LITTLE_AVATAR_A2A_DB", str(database_path))
    monkeypatch.setenv(
        "LITTLE_AVATAR_A2A_OUTBOUND_PEERS",
        '{"agent-b":{"url":"http://peer.example/a2a","credential":"peer-secret"}}',
    )
    CollaborationModule(database_path, {})._begin_outbound_discussion("agent-b")

    response = TestClient(app).post(
        "/api/collaborations",
        json={"peerAgentId": "agent-b", "content": "Do not queue this."},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "A2A peer is busy: agent-b"


def test_unreachable_peer_is_sent_once_by_default(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LITTLE_AVATAR_A2A_DB", str(tmp_path / "a2a.db"))
    monkeypatch.setenv(
        "LITTLE_AVATAR_A2A_OUTBOUND_PEERS",
        '{"agent-b":{"url":"http://peer.example/a2a","credential":"peer-secret"}}',
    )
    calls: list[None] = []

    def unreachable(*args, **kwargs):
        calls.append(None)
        raise requests.ConnectionError("peer is unreachable")

    monkeypatch.setattr("requests.post", unreachable)
    response = TestClient(app).post(
        "/api/collaborations",
        json={"peerAgentId": "agent-b", "content": "Hello"},
    )

    assert response.status_code == 502
    assert len(calls) == 1


def test_outbound_device_proof_sends_the_local_device_key_when_required(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("LITTLE_AVATAR_A2A_DB", str(tmp_path / "a2a.db"))
    monkeypatch.setenv("LITTLE_AVATAR_A2A_REQUIRE_DEVICE_PROOF", "true")
    monkeypatch.setenv("LITTLE_AVATAR_A2A_DEVICE_KEY", "agent-a-device-key")
    monkeypatch.setenv(
        "LITTLE_AVATAR_A2A_OUTBOUND_PEERS",
        '{"agent-b":{"url":"http://peer.example/a2a","credential":"peer-secret"}}',
    )

    def peer_post(url: str, **kwargs) -> _PeerResponse:
        assert kwargs["headers"]["X-Little-Avator-Device-Key"] == "agent-a-device-key"
        return _PeerResponse(kwargs["json"]["message"]["contextId"])

    monkeypatch.setattr("requests.post", peer_post)
    response = TestClient(app).post(
        "/api/collaborations",
        json={"peerAgentId": "agent-b", "content": "What is your view?"},
    )

    assert response.status_code == 202, response.json()


def test_local_retry_policy_is_bounded_to_three_retries(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LITTLE_AVATAR_A2A_DB", str(tmp_path / "a2a.db"))
    monkeypatch.setenv("LITTLE_AVATAR_A2A_RETRY_ATTEMPTS", "99")
    monkeypatch.setenv(
        "LITTLE_AVATAR_A2A_OUTBOUND_PEERS",
        '{"agent-b":{"url":"http://peer.example/a2a","credential":"peer-secret"}}',
    )
    calls: list[None] = []

    def unreachable(*args, **kwargs):
        calls.append(None)
        raise requests.ConnectionError("peer is unreachable")

    monkeypatch.setattr("requests.post", unreachable)
    monkeypatch.setattr("p2026_little_avator.collaboration.time.sleep", lambda seconds: None)
    response = TestClient(app).post(
        "/api/collaborations",
        json={"peerAgentId": "agent-b", "content": "Hello"},
    )

    assert response.status_code == 502
    assert len(calls) == 4


def test_stopping_a_discussion_prevents_the_next_peer_call(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "a2a.db"
    module = CollaborationModule(database_path, {})
    monkeypatch.setenv("LITTLE_AVATAR_A2A_AGENT_ID", "agent-a")
    monkeypatch.setenv(
        "LITTLE_AVATAR_A2A_OUTBOUND_PEERS",
        '{"agent-b":{"url":"http://peer.example/a2a","credential":"peer-secret"}}',
    )
    monkeypatch.setattr("p2026_little_avator.collaboration.uuid.uuid4", lambda: "stop-context")
    calls: list[dict] = []

    def peer_post(url: str, **kwargs) -> _PeerResponse:
        calls.append(kwargs["json"])
        return _PeerResponse("stop-context")

    monkeypatch.setattr("requests.post", peer_post)

    result = module.start_discussion(
        "agent-b",
        "Initial turn",
        decider=lambda reply, round_number: (
            module.stop_discussion("stop-context") or "Must not be sent"
        ),
    )

    assert len(calls) == 1
    assert result["reply"] == "I recommend Tuesday afternoon."
