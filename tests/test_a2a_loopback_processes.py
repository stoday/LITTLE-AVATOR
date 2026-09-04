"""Explicit-provider integration test for two real communicator processes."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests


def _free_port() -> int:
    with socket.socket() as handle:
        handle.bind(("127.0.0.1", 0))
        return int(handle.getsockname()[1])


def _start(port: int, data_directory: Path, environment: dict[str, str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "p2026_little_avator.api:app", "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=os.environ | environment | {"PYTHONPATH": str(Path.cwd() / "src"), "LITTLE_AVATAR_DATA_DIR": str(data_directory)},
    )


def _wait_for_health(port: int) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            if requests.get(f"http://127.0.0.1:{port}/health", timeout=0.25).ok:
                return
        except requests.RequestException:
            pass
        time.sleep(0.05)
    raise AssertionError(f"backend on port {port} did not become healthy")


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_A2A_AGENT_TEST") != "true",
    reason="requires a configured live model; run explicitly with RUN_LIVE_A2A_AGENT_TEST=true",
)
def test_two_communicator_agents_complete_two_background_a2a_rounds(tmp_path: Path) -> None:
    port_a, port_b = _free_port(), _free_port()
    for avatar, schedule in (
        (
            "a",
            "# Evening schedule\n\n- Saturday 19:00-20:00 | available\n- Sunday 18:00-21:00 | available\n",
        ),
        (
            "b",
            "# Evening schedule\n\n- Monday 18:00-21:00 | available\n- Saturday 19:00-20:00 | available\n",
        ),
    ):
        directory = tmp_path / avatar
        directory.mkdir()
        (directory / "schedule.md").write_text(schedule, encoding="utf-8")
    instance_b = _start(port_b, tmp_path / "b", {
        "LITTLE_AVATAR_A2A_AGENT_ID": "agent-b",
        "LITTLE_AVATAR_IDENTITY": "小美",
        "LITTLE_AVATAR_A2A_DB": str(tmp_path / "b" / "a2a.db"),
        "LITTLE_AVATAR_A2A_PEERS": '{"agent-a":"secret-a"}',
        "LITTLE_AVATAR_ADMIN_PROFILE": '{"contacts":{}}',
    })
    instance_a = _start(port_a, tmp_path / "a", {
        "LITTLE_AVATAR_A2A_AGENT_ID": "agent-a",
        "LITTLE_AVATAR_IDENTITY": "小王",
        "LITTLE_AVATAR_A2A_DB": str(tmp_path / "a" / "a2a.db"),
        "LITTLE_AVATAR_A2A_OUTBOUND_PEERS": '{"agent-b":{"url":"http://127.0.0.1:' + str(port_b) + '/a2a","credential":"secret-a"}}',
        "LITTLE_AVATAR_ADMIN_PROFILE": '{"contacts":{"小美":"agent-b"}}',
    })
    try:
        _wait_for_health(port_a)
        _wait_for_health(port_b)
        started_at = time.monotonic()
        response = requests.post(
            f"http://127.0.0.1:{port_a}/api/admin/delegations",
            json={
                "contactName": "小美",
                "request": "幫我跟小美約本週日晚上吃晚餐；若她不方便，請協商另一個晚上。",
            },
            timeout=10,
        )

        assert response.status_code == 202, response.text
        assert time.monotonic() - started_at < 10
        started = response.json()
        assert started["peer_agent_id"] == "agent-b"
        assert started["status"] == "started"
        context_id = started["context_id"]

        deadline = time.monotonic() + 120
        task: dict[str, object] = {}
        while time.monotonic() < deadline:
            task_response = requests.get(f"http://127.0.0.1:{port_a}/api/collaborations/{context_id}", timeout=10)
            assert task_response.status_code == 200, task_response.text
            task = task_response.json()
            if task["status"] in {"completed", "failed"}:
                break
            time.sleep(0.25)

        assert task["status"] == "completed", task
        assert task["rounds"] >= 2
        transcript_a = requests.get(f"http://127.0.0.1:{port_a}/api/collaborations/{context_id}/transcript", timeout=10).json()
        assert len(transcript_a) >= 4
        assert [entry["speaker"] for entry in transcript_a[:4]] == [
            "Local communicator", "Peer communicator", "Local communicator", "Peer communicator"
        ]
        assert "Sunday" in transcript_a[0]["text"] or "週日" in transcript_a[0]["text"]
        assert "Saturday" in transcript_a[2]["text"] or "週六" in transcript_a[2]["text"]
        assert "Saturday" in transcript_a[3]["text"] or "週六" in transcript_a[3]["text"]
        assert "確認" in transcript_a[3]["text"]
        assert all("[[A2A_STATE:" not in entry["text"] for entry in transcript_a)
        notifications_a = requests.get(
            f"http://127.0.0.1:{port_a}/api/admin/notifications", timeout=10
        ).json()
        notifications_b = requests.get(
            f"http://127.0.0.1:{port_b}/api/admin/notifications", timeout=10
        ).json()
        reports_a = [item for item in notifications_a if item["context_id"] == context_id]
        reports_b = [item for item in notifications_b if item["context_id"] == context_id]
        assert len(reports_a) == 1
        assert len(reports_b) == 1
        assert "確認" in reports_a[0]["summary"]
        assert "確認" in reports_b[0]["summary"]
    finally:
        for process in (instance_a, instance_b):
            process.terminate()
        for process in (instance_a, instance_b):
            process.wait(timeout=10)
