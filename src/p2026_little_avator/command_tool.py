"""Shared command runner exposed to LITTLE_AVATOR agents."""

from __future__ import annotations

import subprocess
import os
import sys
from pathlib import Path


_DEFAULT_TIMEOUT_SECONDS = 60
_MAX_TIMEOUT_SECONDS = 300
_MAX_OUTPUT_BYTES = 100_000


def run_command(
    executable: str,
    arguments: list[str] | None = None,
    timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Run an installed command from the project root without a command shell."""
    if not executable or not executable.strip():
        raise ValueError("executable must be a non-empty command name or path")
    if not 1 <= timeout_seconds <= _MAX_TIMEOUT_SECONDS:
        raise ValueError(f"timeout_seconds must be between 1 and {_MAX_TIMEOUT_SECONDS}")

    command = [_resolve_executable(executable.strip()), *(arguments or [])]
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"
    try:
        completed = subprocess.run(
            command,
            cwd=project_root(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            shell=False,
            env=environment,
        )
    except subprocess.TimeoutExpired as exc:
        return _format_result(
            exit_code=None,
            stdout=_limit_output(exc.stdout),
            stderr=_limit_output(exc.stderr),
            error=f"command timed out after {timeout_seconds} seconds",
        )
    except OSError as exc:
        return _format_result(
            exit_code=None,
            stdout="",
            stderr="",
            error=f"command could not be started: {exc}",
        )

    return _format_result(
        exit_code=completed.returncode,
        stdout=_limit_output(completed.stdout),
        stderr=_limit_output(completed.stderr),
    )


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_executable(executable: str) -> str:
    requested = Path(executable)
    if requested.is_absolute() or requested.parent != Path("."):
        return executable

    names = [executable]
    if sys.platform == "win32" and not requested.suffix:
        names.insert(0, f"{executable}.exe")
    for directory in (Path(sys.executable).resolve().parent, project_root() / ".venv" / "Scripts"):
        for name in names:
            candidate = directory / name
            if candidate.is_file():
                return str(candidate)
    return executable


def _limit_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    encoded = value.encode("utf-8")
    if len(encoded) <= _MAX_OUTPUT_BYTES:
        return value
    return encoded[:_MAX_OUTPUT_BYTES].decode("utf-8", errors="ignore") + "\n[output truncated]"


def _format_result(
    *, exit_code: int | None,
    stdout: str,
    stderr: str,
    error: str | None = None,
) -> str:
    result = ["execution: command"]
    if exit_code is not None:
        result.append(f"exit_code: {exit_code}")
    if error:
        result.append(f"error: {error}")
    result.append(f"stdout:\n{stdout}")
    if stderr:
        result.append(f"stderr:\n{stderr}")
    return "\n".join(result) + "\n"
