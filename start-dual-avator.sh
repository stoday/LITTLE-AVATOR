#!/usr/bin/env bash
# Start two isolated local Little Avatar instances for a loopback A2A discussion.
set -Eeuo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
port_a="${PORT_A:-8765}"
port_b="${PORT_B:-8766}"
name_a="${NAME_A:-Alice}"
name_b="${NAME_B:-Xiaomei}"
backend_pids=()
desktop_pids=()

usage() {
    cat <<'EOF'
Usage: ./start-dual-avator.sh [options]

Options:
  --port-a PORT   First Avatar API port (default: 8765)
  --port-b PORT   Second Avatar API port (default: 8766)
  --name-a NAME   First Avatar owner's name (default: Alice)
  --name-b NAME   Second Avatar owner's name (default: Xiaomei)
  -h, --help      Show this help text
EOF
}

fail() {
    printf '[ERROR] %s\n' "$*" >&2
    exit 1
}

validate_port() {
    [[ "$1" =~ ^[0-9]+$ ]] || fail "Ports must be integers between 1 and 65535."
    local port_number=$((10#$1))
    (( port_number >= 1 && port_number <= 65535 )) || fail "Ports must be between 1 and 65535."
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
    "$python" - "$1" <<'PY'
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

wait_for_health() {
    local port="$1"
    local deadline=$((SECONDS + 30))
    until is_healthy "$port"; do
        (( SECONDS < deadline )) || fail "Avatar backend on port $port did not become healthy within 30 seconds."
        sleep 0.25
    done
}

cleanup() {
    local pid
    for pid in "${desktop_pids[@]}" "${backend_pids[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    for pid in "${desktop_pids[@]}" "${backend_pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done
}

start_backend() {
    local id="$1" identity="$2" port="$3" inbound="$4" outbound="$5" peer="$6" profile="$7" contact="$8"
    local data_directory="$root/data/dual-avatar/$id"
    local log_directory="$root/logs/dual-avatar/$id"
    local schedule_template schedule_path

    if [[ "$id" == "avatar-a" ]]; then
        schedule_template="$root/docs/dual-avatar-schedules/avatar-a.schedule.md"
    else
        schedule_template="$root/docs/dual-avatar-schedules/avatar-b.schedule.md"
    fi
    schedule_path="$data_directory/schedule.md"
    mkdir -p "$data_directory" "$log_directory"
    [[ -e "$schedule_path" ]] || cp "$schedule_template" "$schedule_path"

    env \
        LITTLE_AVATAR_A2A_AGENT_ID="$id" \
        LITTLE_AVATAR_A2A_DB="$data_directory/a2a.db" \
        LITTLE_AVATAR_DATA_DIR="$data_directory" \
        LITTLE_AVATAR_LOG_DIR="$log_directory" \
        LITTLE_AVATAR_A2A_PEERS="$inbound" \
        LITTLE_AVATAR_A2A_OUTBOUND_PEERS="$outbound" \
        LITTLE_AVATAR_A2A_DEFAULT_PEER="$peer" \
        LITTLE_AVATAR_ADMIN_PROFILE="$profile" \
        LITTLE_AVATAR_ADMIN_DEFAULT_CONTACT="$contact" \
        LITTLE_AVATAR_IDENTITY="$identity" \
        "$python" -u -m uvicorn p2026_little_avator.api:app --host 127.0.0.1 --port "$port" &
    backend_pids+=("$!")
}

while (($#)); do
    case "$1" in
        --port-a) port_a="${2:?--port-a requires a value}"; shift 2 ;;
        --port-b) port_b="${2:?--port-b requires a value}"; shift 2 ;;
        --name-a) name_a="${2:?--name-a requires a value}"; shift 2 ;;
        --name-b) name_b="${2:?--name-b requires a value}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) fail "Unknown option: $1" ;;
    esac
done

validate_port "$port_a"
validate_port "$port_b"
[[ "$port_a" != "$port_b" ]] || fail "--port-a and --port-b must differ."
[[ -n "$name_a" && -n "$name_b" ]] || fail "Avatar names must not be empty."
command -v uv >/dev/null 2>&1 || fail "uv was not found. Install uv and reopen the terminal."

cd "$root"
printf '[1/2] Syncing project dependencies...\n'
uv sync
python="$(resolve_venv_command python || true)"
frontend="$(resolve_venv_command little-avatar || true)"
[[ -n "$python" && -n "$frontend" ]] || fail "The project virtual environment is incomplete. Run uv sync again."

if is_healthy "$port_a" || is_healthy "$port_b"; then
    fail "An API is already running on one of the requested ports ($port_a, $port_b)."
fi

trap cleanup EXIT
trap 'exit 130' INT TERM

profile_a="{\"contacts\":{\"$name_b\":\"avatar-b\"}}"
profile_b="{\"contacts\":{\"$name_a\":\"avatar-a\"}}"
identity_a="$name_a's Momo (initiator)"
identity_b="$name_b's Momo (invitee)"

printf '[2/2] Starting two isolated Avatar backends...\n'
start_backend "avatar-a" "$identity_a" "$port_a" '{"avatar-b":"b-to-a"}' "{\"avatar-b\":{\"url\":\"http://127.0.0.1:$port_b/a2a\",\"credential\":\"a-to-b\"}}" "avatar-b" "$profile_a" "$name_b"
start_backend "avatar-b" "$identity_b" "$port_b" '{"avatar-a":"a-to-b"}' "{\"avatar-a\":{\"url\":\"http://127.0.0.1:$port_a/a2a\",\"credential\":\"b-to-a\"}}" "avatar-a" "$profile_b" "$name_a"
wait_for_health "$port_a"
wait_for_health "$port_b"

env LITTLE_AVATAR_API_URL="http://127.0.0.1:$port_a" LITTLE_AVATAR_DISPLAY_NAME="$identity_a" "$frontend" &
desktop_pids+=("$!")
env LITTLE_AVATAR_API_URL="http://127.0.0.1:$port_b" LITTLE_AVATAR_DISPLAY_NAME="$identity_b" "$frontend" &
desktop_pids+=("$!")

printf '%s=%s and %s=%s are running. Close both Momos or press Ctrl+C to stop them.\n' "$identity_a" "$port_a" "$identity_b" "$port_b"
wait "${desktop_pids[0]}"
wait "${desktop_pids[1]}"
