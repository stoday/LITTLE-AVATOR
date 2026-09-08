from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from p2026_little_avator import command_tool


def test_run_command_uses_argv_project_root_and_no_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="ready\n", stderr="")

    monkeypatch.setattr(command_tool.subprocess, "run", fake_run)

    result = command_tool.run_command("dtri-meeting-room", ["view", "--refresh"])

    assert captured["command"] == [
        str(Path(sys.executable).with_name("dtri-meeting-room.exe")),
        "view",
        "--refresh",
    ]
    assert captured["cwd"] == command_tool.project_root()
    assert captured["shell"] is False
    assert "exit_code: 0" in result
    assert "ready" in result


def test_run_command_prefers_an_executable_next_to_the_running_python(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    python = tmp_path / "python.exe"
    executable = tmp_path / "dtri-meeting-room.exe"
    executable.touch()
    captured: dict[str, object] = {}

    monkeypatch.setattr(sys, "executable", str(python))
    monkeypatch.setattr(
        command_tool.subprocess,
        "run",
        lambda command, **kwargs: captured.setdefault("command", command)
        and subprocess.CompletedProcess(command, 0, stdout="", stderr=""),
    )

    command_tool.run_command("dtri-meeting-room", ["view"])

    assert captured["command"] == [str(executable), "view"]


def test_run_command_forces_python_children_to_emit_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="會議室\n", stderr="")

    monkeypatch.setattr(command_tool.subprocess, "run", fake_run)

    result = command_tool.run_command("dtri-meeting-room", ["view"])

    environment = captured["env"]
    assert isinstance(environment, dict)
    assert environment["PYTHONIOENCODING"] == "utf-8"
    assert environment["PYTHONUTF8"] == "1"
    assert "會議室" in result


def test_run_command_returns_a_failed_command_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        command_tool.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 7, stdout="", stderr="not logged in\n"),
    )

    result = command_tool.run_command("dtri-meeting-room", ["view"])

    assert "exit_code: 7" in result
    assert "stderr:\nnot logged in" in result


def test_run_command_rejects_invalid_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        command_tool.run_command("dtri-meeting-room", timeout_seconds=0)
