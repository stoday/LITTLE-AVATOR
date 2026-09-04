"""Throwaway: manual EIP onboarding gate before the A2A failure prototype.

This does not read, export, or verify an EIP browser session.  EIP login is a
user-operated onboarding ceremony; device continuity remains local TOFU state.
"""

from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EIP_URL = "https://eip.iii.org.tw/"


@dataclass(frozen=True)
class DeviceIdentity:
    agent_id: str
    fingerprint: str


def create_device_identity(agent_id: str) -> DeviceIdentity:
    """Prototype-only stand-in for a secure-store-backed device key pair."""
    return DeviceIdentity(agent_id=agent_id, fingerprint=secrets.token_hex(16))


def verify_pre_negotiation_identities(simulate_key_change: bool) -> dict[str, object]:
    """Exercise the same TOFU continuity rule used by the HTML prototype."""
    agent_a = create_device_identity("agent-a")
    agent_b = create_device_identity("agent-b")
    trust_records = {
        agent_a.agent_id: agent_a.fingerprint,
        agent_b.agent_id: agent_b.fingerprint,
    }
    presented_b = "different-key" if simulate_key_change else agent_b.fingerprint
    if trust_records[agent_b.agent_id] != presented_b:
        return {
            "status": "rejected_key_changed",
            "schedule_writes": 0,
            "trusted_agents": [],
        }
    return {
        "status": "trusted_for_negotiation",
        "schedule_writes": None,
        "trusted_agents": [agent_a.agent_id, agent_b.agent_id],
    }


def run_existing_failure_prototype() -> int:
    return subprocess.run(
        [sys.executable, str(ROOT / "run.py")],
        cwd=ROOT.parents[1],
        check=False,
    ).returncode


def self_check() -> None:
    accepted = verify_pre_negotiation_identities(simulate_key_change=False)
    rejected = verify_pre_negotiation_identities(simulate_key_change=True)
    assert accepted["status"] == "trusted_for_negotiation"
    assert rejected == {
        "status": "rejected_key_changed",
        "schedule_writes": 0,
        "trusted_agents": [],
    }
    print("SELF-CHECK PASS: TOFU gate accepts continuity and blocks changed keys.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument(
        "--eip-login-confirmed",
        action="store_true",
        help="User has manually completed EIP login in the browser opened by this prototype.",
    )
    parser.add_argument("--simulate-key-change", action="store_true")
    parser.add_argument(
        "--run-negotiation",
        action="store_true",
        help="After the gate passes, run the existing four-agent failure prototype.",
    )
    args = parser.parse_args()

    if args.self_check:
        self_check()
        return

    if not args.eip_login_confirmed:
        webbrowser.open(EIP_URL)
        parser.error(
            "EIP was opened for a user-operated login. After logging in, rerun with --eip-login-confirmed. "
            "No Cookie, session, token, or identity value is read by this prototype."
        )

    gate = verify_pre_negotiation_identities(args.simulate_key_change)
    print(json.dumps({"eip_onboarding": "user_confirmed", "device_trust": gate}, ensure_ascii=False, indent=2))
    if gate["status"] != "trusted_for_negotiation":
        print("IDENTITY GATE BLOCKED: existing negotiation was not started.")
        return

    if args.run_negotiation:
        raise SystemExit(run_existing_failure_prototype())
    print("IDENTITY GATE PASS: rerun with --run-negotiation to start the existing four-agent scenario.")


if __name__ == "__main__":
    main()
