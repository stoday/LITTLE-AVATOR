from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import p2026_little_avator.api as api
from p2026_little_avator.api import app


def test_admin_delegation_reports_an_unmapped_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITTLE_AVATAR_ADMIN_PROFILE", '{"contacts":{}}')

    from p2026_little_avator.api import communicate_with_contact

    result = json.loads(communicate_with_contact("Mia", "ask her to talk"))

    assert result["status"] == "無此人"
    assert result["contact_name"] == "Mia"
    assert result["available_contacts"] == []


def test_inbound_a2a_message_continues_without_prematurely_reporting_to_the_local_admin(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("LITTLE_AVATAR_A2A_DB", str(tmp_path / "a2a.db"))
    monkeypatch.setenv("LITTLE_AVATAR_A2A_PEERS", '{"agent-a":"secret-a"}')
    monkeypatch.setattr(
        app.state,
        "a2a_responder",
        lambda peer_text, transcript: "I can discuss this with you.",
    )
    client = TestClient(app)

    response = client.post(
        "/a2a/message:send",
        headers={
            "A2A-Version": "1.0",
            "Authorization": "Bearer secret-a",
            "X-Little-Avator-Agent-Id": "agent-a",
        },
        json={
            "message": {
                "messageId": "agent-turn-1",
                "contextId": "agent-to-agent-context",
                "role": "ROLE_USER",
                "parts": [{"text": "Can we discuss the request?"}],
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["message"]["parts"] == [{"text": "I can discuss this with you."}]
    assert client.get("/api/admin/notifications").json() == []


def test_receiver_communicator_reports_a_terminal_outcome_to_its_local_admin(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("LITTLE_AVATAR_A2A_DB", str(tmp_path / "a2a.db"))
    monkeypatch.setenv("LITTLE_AVATAR_A2A_PEERS", '{"agent-a":"secret-a"}')
    monkeypatch.setattr(
        api,
        "run_communicator_turn",
        lambda **_: "雙方暫定週六晚上七點見面。\n[[A2A_STATE:await_local_confirmation]]",
    )
    monkeypatch.setattr(app.state, "a2a_responder", api.respond_to_a2a_peer)
    received_reports: list[object] = []

    def admin_reporter(report: object) -> str:
        received_reports.append(report)
        return "B-admin：雙方暫定週六晚上七點見面，仍需本機使用者確認。"

    monkeypatch.setattr(app.state, "admin_reporter", admin_reporter, raising=False)
    client = TestClient(app)

    response = client.post(
        "/a2a/message:send",
        headers={
            "A2A-Version": "1.0",
            "Authorization": "Bearer secret-a",
            "X-Little-Avator-Agent-Id": "agent-a",
        },
        json={
            "message": {
                "messageId": "terminal-turn-1",
                "contextId": "shared-terminal-context",
                "role": "ROLE_USER",
                "parts": [{"text": "那就暫定週六晚上七點。"}],
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["message"]["parts"] == [{"text": "雙方暫定週六晚上七點見面。"}]
    assert len(received_reports) == 1
    report = received_reports[0]
    assert getattr(report, "context_id") == "shared-terminal-context"
    assert getattr(report, "outcome") == "await_local_confirmation"
    assert getattr(report, "result") == "雙方暫定週六晚上七點見面。"
    assert client.get("/api/admin/notifications").json() == [
        {
            "context_id": "shared-terminal-context",
            "summary": "B-admin：雙方暫定週六晚上七點見面，仍需本機使用者確認。",
        }
    ]
