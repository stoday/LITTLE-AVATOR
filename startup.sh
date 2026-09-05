#!/usr/bin/env bash
# Start one local Little Avatar backend and desktop client.
set -Eeuo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
port="${PORT:-8765}"

fail() {
    printf '[ERROR] %s\n' "$*" >&2
    exit 1
}

validate_port() {
    [[ "$1" =~ ^[0-9]+$ ]] || fail "PORT must be an integer between 1 and 65535."
    local port_number=$((10#$1))
    (( port_number >= 1 && port_number <= 65535 )) || fail "PORT must be between 1 and 65535."
}

resolve_venv_command() {
    local command_name="$1"
    local candidate
    for candidate in "$root/.venv/bin/$command_name" "$root/.venv/Scripts/$command_name" "$root/.venv/Scripts/$command_name.exe"; do
        if [[ -x "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

is_healthy() {
    "$python" - "$port" <<'PY'
import sys
from urllib.error import URLError
from urllib.request import urlopen

try:
    with urlopen(f"http://127.0.0.1:{sys.argv[1]}/health", timeout=1) as response:
        raise SystemExit(0 if response.status == 200 else 1)
except URLError:
    raise SystemExit(1)
PY
}

cleanup() {
    if [[ -n "${frontend_pid:-}" ]] && kill -0 "$frontend_pid" 2>/dev/null; then
        kill "$frontend_pid" 2>/dev/null || true
        wait "$frontend_pid" 2>/dev/null || true
    fi
    if [[ -n "${backend_pid:-}" ]] && kill -0 "$backend_pid" 2>/dev/null; then
        kill "$backend_pid" 2>/dev/null || true
        wait "$backend_pid" 2>/dev/null || true
    fi
}

validate_port "$port"
command -v uv >/dev/null 2>&1 || fail "uv was not found. Install uv and reopen the terminal."

cd "$root"
printf '[CONFIG] API port: %s\n' "$port"
printf '[1/2] Syncing project dependencies...\n'
uv sync

python="$(resolve_venv_command python || true)"
frontend="$(resolve_venv_command little-avatar || true)"
[[ -n "$python" && -n "$frontend" ]] || fail "The project virtual environment is incomplete. Run uv sync again."

if is_healthy; then
    fail "An API is already running on port $port. Stop it or set PORT to another value."
fi

trap cleanup EXIT
trap 'exit 130' INT TERM

printf '[2/2] Starting API and Momo...\n'
"$python" -u -m uvicorn p2026_little_avator.api:app --host 127.0.0.1 --port "$port" &
backend_pid=$!

deadline=$((SECONDS + 30))
until is_healthy; do
    if ! kill -0 "$backend_pid" 2>/dev/null; then
        fail "The API exited before it became healthy."
    fi
    (( SECONDS < deadline )) || fail "The API did not become healthy within 30 seconds."
    sleep 0.25
done

export LITTLE_AVATAR_API_URL="http://127.0.0.1:$port"
"$frontend" &
frontend_pid=$!

printf 'Momo is running. Close Momo or press Ctrl+C here to stop both processes.\n'
wait "$frontend_pid"
