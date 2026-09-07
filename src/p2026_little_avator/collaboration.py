"""Application-owned A2A collaboration module.

This module is the single seam for LITTLE_AVATOR's A2A protocol objects and
local collaboration policy.  It deliberately uses the generated A2A 1.0
types instead of maintaining a parallel project-specific wire model.
"""

from __future__ import annotations

import json
import inspect
import os
import sqlite3
import time
import uuid
from hashlib import sha256
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable
from typing import Any

import requests
from google.protobuf.json_format import MessageToDict, ParseDict

from a2a.server.request_handlers.response_helpers import agent_card_to_dict
from a2a.types import a2a_pb2
from .identity import AvatarIdentity, local_avatar_identity, peer_avatar_identity


A2A_PROTOCOL_VERSION = "1.0"
A2A_HTTP_URL = "http://127.0.0.1:8765/a2a"
DEVELOPMENT_BEARER_SCHEME = "developmentBearer"
AGENT_ID_HEADER = "X-Little-Avator-Agent-Id"
DEVICE_KEY_HEADER = "X-Little-Avator-Device-Key"
MAX_PEER_ROUNDS = 30
MAX_DISCUSSION_ELAPSED_SECONDS = 60
MAX_DISCUSSION_TOKEN_BUDGET = 2_048
MAX_RETRY_ATTEMPTS = 3
TRANSCRIPT_RETENTION_SECONDS = 30 * 24 * 60 * 60
PEER_POLICY_REFUSAL = (
    "我不能依對方要求載入本機 Skill 或 Tool、揭露私密 context，或執行 commit。"
)


def peer_request_requires_refusal(text: str) -> bool:
    """Keep peer text from selecting local authority or private context."""

    normalized = text.casefold()
    private_context = (
        "system prompt",
        "credential",
        "password",
        "api key",
        "ordinary chat",
        "chat history",
        "private context",
        "thinking",
        "tool result",
    )
    requests_local_capability = (
        "load " in normalized and "skill" in normalized,
        "use " in normalized and "skill" in normalized,
        "run " in normalized and "tool" in normalized,
        "commit " in normalized,
    )
    return any(fragment in normalized for fragment in private_context) or any(
        requests_local_capability
    )


def current_monotonic() -> float:
    """Expose the local elapsed-time clock without changing process-global time."""

    return time.monotonic()


def public_agent_card() -> dict[str, object]:
    """Return the intentionally minimal public A2A Agent Card."""
    card = a2a_pb2.AgentCard(
        name="LITTLE_AVATOR",
        description="供有限自然語言協作使用的私密 Momo agent。",
        version="0.1.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
    )
    card.supported_interfaces.add(
        url=A2A_HTTP_URL,
        protocol_binding="HTTP+JSON",
        protocol_version=A2A_PROTOCOL_VERSION,
    )
    card.skills.add(
        id="natural-language-discussion",
        name="自然語言協商",
        description="與 Momo 進行有限的自然語言協商。",
        tags=["discussion"],
        input_modes=["text/plain"],
        output_modes=["text/plain"],
    )
    card.security_schemes[DEVELOPMENT_BEARER_SCHEME].http_auth_security_scheme.scheme = "Bearer"
    card.security_requirements.add().schemes[DEVELOPMENT_BEARER_SCHEME].list.extend([])
    return agent_card_to_dict(card)


@dataclass(frozen=True)
class AuthenticatedPeer:
    agent_id: str


@dataclass(frozen=True)
class OutboundPeer:
    url: str
    credential: str


class CollaborationModule:
    """Own the public A2A HTTP seam and durable direct-message records."""

    def __init__(self, database_path: Path, peers: dict[str, str]) -> None:
        self._database_path = database_path
        self._peers = peers
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    @classmethod
    def from_environment(cls) -> "CollaborationModule":
        configured_path = os.getenv("LITTLE_AVATAR_A2A_DB", "data/a2a.db")
        raw_peers = os.getenv("LITTLE_AVATAR_A2A_PEERS", "{}")
        try:
            peers = json.loads(raw_peers)
        except json.JSONDecodeError as exc:
            raise ValueError("LITTLE_AVATAR_A2A_PEERS must be a JSON object") from exc
        if not isinstance(peers, dict) or not all(
            isinstance(agent_id, str) and isinstance(secret, str)
            for agent_id, secret in peers.items()
        ):
            raise ValueError("LITTLE_AVATAR_A2A_PEERS must map agent IDs to bearer credentials")
        return cls(Path(configured_path), peers)

    def authenticate(self, headers: dict[str, str]) -> AuthenticatedPeer:
        agent_id = headers.get(AGENT_ID_HEADER.lower())
        authorization = headers.get("authorization")
        if not agent_id or not authorization or not authorization.startswith("Bearer "):
            raise PermissionError("A2A peer authentication is required")
        expected_secret = self._peers.get(agent_id)
        if expected_secret is None or authorization.removeprefix("Bearer ") != expected_secret:
            raise PermissionError("A2A peer is not authorized")
        if os.getenv("LITTLE_AVATAR_A2A_REQUIRE_DEVICE_PROOF", "false").casefold() == "true":
            device_key = headers.get(DEVICE_KEY_HEADER.lower())
            if not device_key or not self._is_trusted_device(agent_id, device_key):
                raise PermissionError("A2A peer device is not trusted")
        return AuthenticatedPeer(agent_id=agent_id)

    def approve_device(self, agent_id: str, device_key: str) -> None:
        """Persist an explicit local TOFU approval; no message can grant it."""
        with sqlite3.connect(self._database_path) as connection:
            existing = connection.execute(
                "SELECT device_key FROM a2a_trust_record WHERE agent_id = ?", (agent_id,)
            ).fetchone()
            if existing is not None and str(existing[0]) != device_key:
                raise PermissionError("Revoke the existing device trust before approving a new key")
            connection.execute(
                "INSERT OR REPLACE INTO a2a_trust_record (agent_id, device_key) VALUES (?, ?)",
                (agent_id, device_key),
            )

    def revoke_device(self, agent_id: str) -> bool:
        with sqlite3.connect(self._database_path) as connection:
            return bool(
                connection.execute(
                    "DELETE FROM a2a_trust_record WHERE agent_id = ?", (agent_id,)
                ).rowcount
            )

    def trusted_devices(self) -> list[dict[str, str]]:
        """Return local trust records without exposing a reusable device key."""
        with sqlite3.connect(self._database_path) as connection:
            rows = connection.execute(
                "SELECT agent_id, device_key FROM a2a_trust_record ORDER BY agent_id"
            ).fetchall()
        return [
            {
                "agent_id": str(agent_id),
                "device_fingerprint": sha256(str(device_key).encode()).hexdigest()[:16],
            }
            for agent_id, device_key in rows
        ]

    def _is_trusted_device(self, agent_id: str, device_key: str) -> bool:
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT device_key FROM a2a_trust_record WHERE agent_id = ?", (agent_id,)
            ).fetchone()
        return row is not None and str(row[0]) == device_key

    def send_direct_message(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
        responder: Callable[..., str] | None = None,
    ) -> dict[str, Any]:
        if headers.get("a2a-version") != A2A_PROTOCOL_VERSION:
            raise ValueError("Unsupported A2A version")
        peer = self.authenticate(headers)
        request = ParseDict(payload, a2a_pb2.SendMessageRequest())
        message = request.message
        if not message.message_id or not message.context_id or not message.parts:
            raise ValueError("A2A Message requires messageId, contextId, and at least one Part")
        if message.role != a2a_pb2.ROLE_USER:
            raise ValueError("Inbound A2A direct Messages must use ROLE_USER")
        if not all(part.text for part in message.parts):
            raise ValueError("This A2A discussion accepts text Parts only")

        existing = self._load_exchange(message.message_id)
        if existing is not None:
            request_json, response_json = existing
            if request_json != json.dumps(payload, sort_keys=True):
                raise ValueError("A2A message ID replay payload mismatch")
            return json.loads(response_json)

        peer_text = "".join(part.text for part in message.parts)
        self._record_identity_snapshot(message.context_id, peer.agent_id)
        transcript = self._peer_transcript(message.context_id)
        reply_text = (
            PEER_POLICY_REFUSAL
            if peer_request_requires_refusal(peer_text)
            else self._call_responder(responder, peer_text, transcript, message.context_id, peer.agent_id)
            if responder
            else "Momo 已收到協商訊息。"
        )
        reply = a2a_pb2.Message(
            message_id=f"{message.message_id}:reply",
            context_id=message.context_id,
            role=a2a_pb2.ROLE_AGENT,
        )
        reply.parts.add(text=reply_text)
        response = MessageToDict(a2a_pb2.SendMessageResponse(message=reply))
        self._store_exchange(
            message_id=message.message_id,
            context_id=message.context_id,
            peer_id=peer.agent_id,
            request_payload=payload,
            response_payload=response,
        )
        self._record_audit("authorized_delivery", peer.agent_id, message.context_id)
        return response

    @staticmethod
    def _call_responder(
        responder: Callable[..., str],
        peer_text: str,
        transcript: list[dict[str, str]],
        context_id: str,
        peer_agent_id: str,
    ) -> str:
        """Pass local context to aware adapters while retaining simple test adapters."""
        parameters = inspect.signature(responder).parameters.values()
        accepts_context = any(
            parameter.name == "context_id" or parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters
        )
        accepts_peer = any(
            parameter.name == "peer_agent_id" or parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters
        )
        if accepts_context or accepts_peer:
            kwargs: dict[str, str] = {}
            if accepts_context:
                kwargs["context_id"] = context_id
            if accepts_peer:
                kwargs["peer_agent_id"] = peer_agent_id
            return responder(peer_text, transcript, **kwargs)
        return responder(peer_text, transcript)

    def start_discussion(
        self,
        peer_agent_id: str,
        content: str,
        decider: Callable[[str, int], str | None] | None = None,
    ) -> dict[str, str]:
        """Send the initial official A2A Message to one configured peer."""
        peer = self._outbound_peer(peer_agent_id)
        retry_attempts = self._configured_retry_attempts()
        self._begin_outbound_discussion(peer_agent_id)
        try:
            return self._run_discussion(
                peer_agent_id, peer, content, decider, retry_attempts
            )
        finally:
            self._finish_outbound_discussion(peer_agent_id)

    def create_discussion_task(
        self, peer_agent_id: str, contact_name: str, request: str
    ) -> dict[str, str]:
        """Persist an outbound discussion before any communicator Agent is invoked.

        The task owns the A2A context and its deliberate wire transcript.  It is
        intentionally independent from the lifetime of a communicator Agent.
        """
        self._outbound_peer(peer_agent_id)
        self._begin_outbound_discussion(peer_agent_id)
        context_id = str(uuid.uuid4())
        try:
            self._record_identity_snapshot(context_id, peer_agent_id)
            with sqlite3.connect(self._database_path) as connection:
                connection.execute(
                    """
                    INSERT INTO a2a_discussion_task
                        (context_id, peer_id, contact_name, request, status, rounds, result, error, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'queued', 0, '', '', ?, ?)
                    """,
                    (context_id, peer_agent_id, contact_name, request, time.time(), time.time()),
                )
        except Exception:
            self._finish_outbound_discussion(peer_agent_id)
            raise
        return {
            "context_id": context_id,
            "peer_agent_id": peer_agent_id,
            "status": "queued",
        }

    def get_discussion_task(self, context_id: str) -> dict[str, str | int]:
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT context_id, peer_id, contact_name, request, status, rounds, result, error
                FROM a2a_discussion_task WHERE context_id = ?
                """,
                (context_id,),
            ).fetchone()
        if row is None:
            raise LookupError("A2A discussion task was not found")
        return {
            "context_id": str(row[0]),
            "peer_agent_id": str(row[1]),
            "contact_name": str(row[2]),
            "request": str(row[3]),
            "status": str(row[4]),
            "rounds": int(row[5]),
            "result": str(row[6]),
            "error": str(row[7]),
        }

    def update_discussion_task(self, context_id: str, **changes: str | int) -> None:
        """Update the small, application-owned state record for one discussion."""
        allowed = {"status", "rounds", "result", "error"}
        if not changes or set(changes) - allowed:
            raise ValueError("Invalid A2A discussion task update")
        assignments = ", ".join(f"{name} = ?" for name in changes)
        values = [changes[name] for name in changes]
        with sqlite3.connect(self._database_path) as connection:
            updated = connection.execute(
                f"UPDATE a2a_discussion_task SET {assignments}, updated_at = ? WHERE context_id = ?",
                (*values, time.time(), context_id),
            ).rowcount
        if not updated:
            raise LookupError("A2A discussion task was not found")

    def finish_discussion_task(self, context_id: str) -> None:
        """Release the peer reservation after a background task reaches a terminal state."""
        task = self.get_discussion_task(context_id)
        self._finish_outbound_discussion(str(task["peer_agent_id"]))

    def send_discussion_turn(self, peer_agent_id: str, context_id: str, content: str) -> str:
        """Send one explicit turn for an already-created discussion task."""
        peer = self._outbound_peer(peer_agent_id)
        return self._send_outbound_message(
            peer_agent_id,
            peer,
            os.getenv("LITTLE_AVATAR_A2A_AGENT_ID", "little-avator"),
            context_id,
            content,
            self._configured_retry_attempts(),
        )

    def _run_discussion(
        self,
        peer_agent_id: str,
        peer: OutboundPeer,
        content: str,
        decider: Callable[[str, int], str | None] | None,
        retry_attempts: int,
    ) -> dict[str, str]:
        local_agent_id = os.getenv("LITTLE_AVATAR_A2A_AGENT_ID", "little-avator")
        context_id = str(uuid.uuid4())
        next_content = content
        reply_text = ""
        started_at = current_monotonic()
        consumed_tokens = 0
        for round_number in range(1, MAX_PEER_ROUNDS + 1):
            if self._is_stopped(context_id):
                break
            if current_monotonic() - started_at >= MAX_DISCUSSION_ELAPSED_SECONDS:
                break
            consumed_tokens += self._estimated_tokens(next_content)
            if consumed_tokens > MAX_DISCUSSION_TOKEN_BUDGET:
                break
            reply_text = self._send_outbound_message(
                peer_agent_id,
                peer,
                local_agent_id,
                context_id,
                next_content,
                retry_attempts,
            )
            if self._is_stopped(context_id):
                break
            consumed_tokens += self._estimated_tokens(reply_text)
            if consumed_tokens >= MAX_DISCUSSION_TOKEN_BUDGET:
                break
            next_content = decider(reply_text, round_number) if decider else None
            if not next_content:
                break
        else:
            raise OverflowError("A2A discussion has reached its peer-round limit")
        return {
            "context_id": context_id,
            "peer_agent_id": peer_agent_id,
            "reply": reply_text,
        }

    @staticmethod
    def _estimated_tokens(text: str) -> int:
        """Use a conservative, model-independent budget for plain-text discussion."""

        return len(text.split())

    def _send_outbound_message(
        self,
        peer_agent_id: str,
        peer: OutboundPeer,
        local_agent_id: str,
        context_id: str,
        content: str,
        retry_attempts: int,
    ) -> str:
        message = a2a_pb2.Message(
            message_id=str(uuid.uuid4()),
            context_id=context_id,
            role=a2a_pb2.ROLE_USER,
        )
        message.parts.add(text=content)
        payload = MessageToDict(a2a_pb2.SendMessageRequest(message=message))
        headers = {
            "A2A-Version": A2A_PROTOCOL_VERSION,
            "Authorization": f"Bearer {peer.credential}",
            AGENT_ID_HEADER: local_agent_id,
        }
        if os.getenv("LITTLE_AVATAR_A2A_REQUIRE_DEVICE_PROOF", "false").casefold() == "true":
            device_key = os.getenv("LITTLE_AVATAR_A2A_DEVICE_KEY", "").strip()
            if not device_key:
                raise ValueError("LITTLE_AVATAR_A2A_DEVICE_KEY is required for device proof")
            headers[DEVICE_KEY_HEADER] = device_key
        for attempt in range(retry_attempts + 1):
            try:
                response = requests.post(
                    f"{peer.url.rstrip('/')}/message:send",
                    headers=headers,
                    json=payload,
                    timeout=float(os.getenv("LITTLE_AVATAR_A2A_REQUEST_TIMEOUT_SECONDS", "60")),
                )
                break
            except requests.RequestException:
                if attempt == retry_attempts:
                    raise
                time.sleep(0.1)
        response.raise_for_status()
        parsed = ParseDict(response.json(), a2a_pb2.SendMessageResponse())
        if not parsed.HasField("message") or not parsed.message.parts:
            raise ValueError("Peer did not return a direct A2A Message")
        reply = parsed.message
        if reply.context_id != message.context_id or reply.role != a2a_pb2.ROLE_AGENT:
            raise ValueError("Peer returned an invalid A2A discussion response")
        if not all(part.text for part in reply.parts):
            raise ValueError("Peer response must contain text Parts only")
        self._record_outbound_exchange(
            message_id=message.message_id,
            context_id=context_id,
            peer_id=peer_agent_id,
            request_payload=payload,
            response_payload=MessageToDict(parsed),
        )
        self._record_audit("outbound_delivery", peer_agent_id, context_id)
        return "".join(part.text for part in reply.parts)

    @staticmethod
    def _outbound_peer(peer_agent_id: str) -> OutboundPeer:
        raw_peers = os.getenv("LITTLE_AVATAR_A2A_OUTBOUND_PEERS", "{}")
        try:
            peers = json.loads(raw_peers)
            configured = peers[peer_agent_id]
            url = configured["url"]
            credential = configured["credential"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise LookupError(f"A2A peer is not configured: {peer_agent_id}") from exc
        if not isinstance(url, str) or not isinstance(credential, str):
            raise LookupError(f"A2A peer is not configured: {peer_agent_id}")
        return OutboundPeer(url=url, credential=credential)

    @staticmethod
    def _configured_retry_attempts() -> int:
        raw_attempts = os.getenv("LITTLE_AVATAR_A2A_RETRY_ATTEMPTS", "0")
        try:
            return min(max(int(raw_attempts), 0), MAX_RETRY_ATTEMPTS)
        except ValueError as exc:
            raise ValueError("LITTLE_AVATAR_A2A_RETRY_ATTEMPTS must be an integer") from exc

    def _initialize_database(self) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS a2a_message_exchange (
                    message_id TEXT PRIMARY KEY,
                    context_id TEXT NOT NULL,
                    peer_id TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    response_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS a2a_outbound_session (
                    peer_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS a2a_stopped_context (context_id TEXT PRIMARY KEY)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS a2a_task (task_id TEXT PRIMARY KEY, context_id TEXT NOT NULL, state INTEGER NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS a2a_trust_record (agent_id TEXT PRIMARY KEY, device_key TEXT NOT NULL)"
            )
            connection.execute("CREATE TABLE IF NOT EXISTS a2a_task_commit (task_id TEXT PRIMARY KEY)")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS a2a_pending_local_deletion "
                "(context_id TEXT PRIMARY KEY, requested_turn_id TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS a2a_pending_all_local_deletion "
                "(id INTEGER PRIMARY KEY CHECK (id = 1), requested_turn_id TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS a2a_admin_notification (id INTEGER PRIMARY KEY, context_id TEXT NOT NULL, summary TEXT NOT NULL, created_at REAL NOT NULL)"
            )
            connection.execute(
                """
                DELETE FROM a2a_admin_notification
                WHERE id NOT IN (
                    SELECT MIN(id) FROM a2a_admin_notification GROUP BY context_id, summary
                )
                """
            )
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS a2a_admin_notification_once ON a2a_admin_notification (context_id, summary)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS a2a_outbound_exchange (
                    message_id TEXT PRIMARY KEY,
                    context_id TEXT NOT NULL,
                    peer_id TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    response_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS a2a_security_audit (
                    id INTEGER PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    peer_id TEXT NOT NULL,
                    context_id TEXT NOT NULL,
                    occurred_at REAL NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS a2a_context (
                    context_id TEXT PRIMARY KEY,
                    peer_id TEXT NOT NULL,
                    peer_rounds INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS a2a_discussion_task (
                    context_id TEXT PRIMARY KEY,
                    peer_id TEXT NOT NULL,
                    contact_name TEXT NOT NULL,
                    request TEXT NOT NULL,
                    status TEXT NOT NULL,
                    rounds INTEGER NOT NULL,
                    result TEXT NOT NULL,
                    error TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS a2a_context_identity (
                    context_id TEXT PRIMARY KEY,
                    local_owner_name TEXT NOT NULL,
                    local_communicator_name TEXT NOT NULL,
                    peer_owner_name TEXT NOT NULL,
                    peer_communicator_name TEXT NOT NULL
                )
                """
            )
            self._purge_expired_transcripts(connection)

    def delete_transcript(self, context_id: str) -> bool:
        """Delete this device's message bodies; peer copies are unaffected."""
        with sqlite3.connect(self._database_path) as connection:
            deleted = connection.execute(
                "DELETE FROM a2a_message_exchange WHERE context_id = ?", (context_id,)
            ).rowcount
            deleted += connection.execute(
                "DELETE FROM a2a_outbound_exchange WHERE context_id = ?", (context_id,)
            ).rowcount
            connection.execute("DELETE FROM a2a_context WHERE context_id = ?", (context_id,))
            connection.execute("DELETE FROM a2a_context_identity WHERE context_id = ?", (context_id,))
        return bool(deleted)

    def request_local_discussion_deletion(self, context_id: str, turn_id: str) -> None:
        """Record a local-only deletion request that must be confirmed in a later turn."""
        with sqlite3.connect(self._database_path) as connection:
            exists = connection.execute(
                "SELECT 1 FROM a2a_discussion_task WHERE context_id = ? "
                "UNION SELECT 1 FROM a2a_admin_notification WHERE context_id = ? LIMIT 1",
                (context_id, context_id),
            ).fetchone()
            if exists is None:
                raise LookupError("Local collaboration context was not found")
            connection.execute(
                "INSERT OR REPLACE INTO a2a_pending_local_deletion (context_id, requested_turn_id) VALUES (?, ?)",
                (context_id, turn_id),
            )

    def confirm_local_discussion_deletion(self, context_id: str, turn_id: str) -> None:
        """Purge every local record for one collaboration after a later confirmation."""
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT requested_turn_id FROM a2a_pending_local_deletion WHERE context_id = ?",
                (context_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Local collaboration deletion was not requested")
            if str(row[0]) == turn_id:
                raise ValueError("Local collaboration deletion requires a later user turn")
            task_ids = [
                str(item[0])
                for item in connection.execute("SELECT task_id FROM a2a_task WHERE context_id = ?", (context_id,))
            ]
            for table in (
                "a2a_message_exchange",
                "a2a_outbound_exchange",
                "a2a_stopped_context",
                "a2a_admin_notification",
                "a2a_security_audit",
                "a2a_context",
                "a2a_discussion_task",
                "a2a_context_identity",
                "a2a_task",
                "a2a_pending_local_deletion",
            ):
                connection.execute(f"DELETE FROM {table} WHERE context_id = ?", (context_id,))
            for task_id in task_ids:
                connection.execute("DELETE FROM a2a_task_commit WHERE task_id = ?", (task_id,))

    def request_all_local_collaborations_deletion(self, turn_id: str) -> None:
        """Record one all-context local purge request for a later user confirmation."""
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO a2a_pending_all_local_deletion (id, requested_turn_id) VALUES (1, ?)",
                (turn_id,),
            )

    def confirm_all_local_collaborations_deletion(self, turn_id: str) -> None:
        """Purge all local collaboration records while preserving device trust configuration."""
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT requested_turn_id FROM a2a_pending_all_local_deletion WHERE id = 1"
            ).fetchone()
            if row is None:
                raise ValueError("All local collaboration deletion was not requested")
            if str(row[0]) == turn_id:
                raise ValueError("All local collaboration deletion requires a later user turn")
            active = connection.execute(
                "SELECT 1 FROM a2a_discussion_task WHERE status IN ('queued', 'running') LIMIT 1"
            ).fetchone()
            if active is not None:
                raise RuntimeError("Cannot clear local collaborations while a discussion is running")
            for table in (
                "a2a_message_exchange",
                "a2a_outbound_exchange",
                "a2a_stopped_context",
                "a2a_task_commit",
                "a2a_admin_notification",
                "a2a_security_audit",
                "a2a_context",
                "a2a_discussion_task",
                "a2a_context_identity",
                "a2a_task",
                "a2a_pending_local_deletion",
                "a2a_pending_all_local_deletion",
            ):
                connection.execute(f"DELETE FROM {table}")

    def record_admin_notification(self, context_id: str, summary: str) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO a2a_admin_notification (context_id, summary, created_at) VALUES (?, ?, ?)",
                (context_id, summary, time.time()),
            )

    def admin_notifications(self) -> list[dict[str, str]]:
        with sqlite3.connect(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT notification.context_id, notification.summary, task.task_id, task.state
                FROM a2a_admin_notification AS notification
                LEFT JOIN a2a_task AS task ON task.context_id = notification.context_id
                ORDER BY notification.id
                """
            ).fetchall()
        return [
            {
                "context_id": str(context_id),
                "summary": str(summary),
            }
            for context_id, summary, task_id, task_state in rows
        ]

    def pending_admin_decisions(self) -> list[dict[str, str]]:
        """Return only local, user-safe summaries whose decision is still pending."""
        with sqlite3.connect(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT notification.context_id, notification.summary, task.task_id
                FROM a2a_admin_notification AS notification
                JOIN a2a_task AS task ON task.context_id = notification.context_id
                WHERE task.state = ?
                  AND NOT EXISTS (
                    SELECT 1 FROM a2a_security_audit AS audit
                    WHERE audit.context_id = task.context_id
                      AND audit.event_type IN ('task_confirmed', 'task_rejected')
                  )
                ORDER BY notification.id
                """,
                (a2a_pb2.TASK_STATE_WORKING,),
            ).fetchall()
        return [
            {"context_id": str(context_id), "summary": str(summary), "task_id": str(task_id)}
            for context_id, summary, task_id in rows
        ]

    def discussion_transcript(self, context_id: str) -> dict[str, Any]:
        """Return only the A2A message bodies exchanged for one local context.

        This diagnostic view intentionally excludes prompts, credentials, tool data,
        and all local context that was not sent over A2A.
        """
        with sqlite3.connect(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT created_at, direction, peer_id, request_json, response_json, exchange_id
                FROM (
                    SELECT created_at, 'inbound' AS direction, peer_id, request_json,
                           response_json, rowid AS exchange_id
                    FROM a2a_message_exchange WHERE context_id = ?
                    UNION ALL
                    SELECT created_at, 'outbound' AS direction, peer_id, request_json,
                           response_json, rowid AS exchange_id
                    FROM a2a_outbound_exchange WHERE context_id = ?
                )
                ORDER BY created_at, exchange_id
                """,
                (context_id, context_id),
            ).fetchall()
        local_identity, peer_identity = self._identity_snapshot(context_id)
        entries: list[dict[str, str]] = []
        for _, direction, _, request_json, response_json, _ in rows:
            request_text = self._message_text(str(request_json))
            response_text = self._message_text(str(response_json))
            if direction == "outbound":
                ordered_messages = (("local", local_identity.communicator_name, request_text), ("peer", peer_identity.communicator_name, response_text))
            else:
                ordered_messages = (("peer", peer_identity.communicator_name, request_text), ("local", local_identity.communicator_name, response_text))
            entries.extend(
                {"role": role, "speaker": speaker, "text": text}
                for role, speaker, text in ordered_messages
                if text
            )
        return {
            "local_communicator_name": local_identity.communicator_name,
            "peer_communicator_name": peer_identity.communicator_name,
            "entries": entries,
        }

    def _record_identity_snapshot(self, context_id: str, peer_agent_id: str) -> None:
        local = local_avatar_identity()
        peer = peer_avatar_identity(peer_agent_id)
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO a2a_context_identity VALUES (?, ?, ?, ?, ?)",
                (context_id, local.owner_name, local.communicator_name, peer.owner_name, peer.communicator_name),
            )

    def _identity_snapshot(self, context_id: str) -> tuple[AvatarIdentity, AvatarIdentity]:
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT local_owner_name, local_communicator_name, peer_owner_name, peer_communicator_name "
                "FROM a2a_context_identity WHERE context_id = ?", (context_id,)
            ).fetchone()
        if row is None:
            return AvatarIdentity("", "MOMO"), AvatarIdentity("", "對方秘書")
        return AvatarIdentity(str(row[0]), str(row[1])), AvatarIdentity(str(row[2]), str(row[3]))

    def create_confirmation_task(self, context_id: str) -> dict[str, Any]:
        task_id = str(uuid.uuid4())
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                "INSERT INTO a2a_task (task_id, context_id, state) VALUES (?, ?, ?)",
                (task_id, context_id, a2a_pb2.TASK_STATE_WORKING),
            )
        return self.get_task(task_id)

    def get_or_create_confirmation_task(self, context_id: str) -> dict[str, Any]:
        """One local confirmation Task represents one proposal context."""
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT task_id FROM a2a_task WHERE context_id = ? ORDER BY rowid LIMIT 1",
                (context_id,),
            ).fetchone()
        return self.get_task(str(row[0])) if row is not None else self.create_confirmation_task(context_id)

    def get_task(self, task_id: str) -> dict[str, Any]:
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute("SELECT context_id, state FROM a2a_task WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            raise LookupError("A2A Task was not found")
        task = a2a_pb2.Task(id=task_id, context_id=str(row[0]))
        task.status.state = int(row[1])
        return MessageToDict(task)

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute("SELECT context_id FROM a2a_task WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise LookupError("A2A Task was not found")
            connection.execute("UPDATE a2a_task SET state = ? WHERE task_id = ?", (a2a_pb2.TASK_STATE_CANCELED, task_id))
        return self.get_task(task_id)

    def resolve_local_confirmation(self, task_id: str, confirmed: bool) -> dict[str, Any]:
        """Apply only the local user's confirmation decision to a working Task."""
        target_state = a2a_pb2.TASK_STATE_WORKING if confirmed else a2a_pb2.TASK_STATE_REJECTED
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT context_id, state FROM a2a_task WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row is None:
                raise LookupError("A2A Task was not found")
            if int(row[1]) != a2a_pb2.TASK_STATE_WORKING:
                return self.get_task(task_id)
            connection.execute(
                "UPDATE a2a_task SET state = ? WHERE task_id = ?", (target_state, task_id)
            )
        self._record_audit("task_confirmed" if confirmed else "task_rejected", "local-user", str(row[0]))
        return self.get_task(task_id)

    def commit_task(self, task_id: str, commit: Callable[[], None]) -> dict[str, Any]:
        """Run one verified local side effect; duplicate delivery cannot repeat it."""
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute("SELECT state FROM a2a_task WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise LookupError("A2A Task was not found")
            if int(row[0]) != a2a_pb2.TASK_STATE_WORKING:
                return self.get_task(task_id)
            try:
                connection.execute("INSERT INTO a2a_task_commit (task_id) VALUES (?)", (task_id,))
            except sqlite3.IntegrityError:
                return self.get_task(task_id)
        try:
            commit()
        except Exception:
            state = a2a_pb2.TASK_STATE_FAILED
        else:
            state = a2a_pb2.TASK_STATE_COMPLETED
        with sqlite3.connect(self._database_path) as connection:
            connection.execute("UPDATE a2a_task SET state = ? WHERE task_id = ?", (state, task_id))
        return self.get_task(task_id)

    def set_task_waiting_state(self, task_id: str, *, authorization: bool) -> dict[str, Any]:
        """Represent protocol auth and client-input waits with their A2A states."""
        state = (
            a2a_pb2.TASK_STATE_AUTH_REQUIRED
            if authorization
            else a2a_pb2.TASK_STATE_INPUT_REQUIRED
        )
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT state FROM a2a_task WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row is None:
                raise LookupError("A2A Task was not found")
            if int(row[0]) != a2a_pb2.TASK_STATE_WORKING:
                raise ValueError("Only a working Task can request more input or authorization")
            connection.execute("UPDATE a2a_task SET state = ? WHERE task_id = ?", (state, task_id))
        return self.get_task(task_id)

    def stop_discussion(self, context_id: str) -> None:
        """Stop local continuation; a remote in-flight request may still finish."""
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO a2a_stopped_context (context_id) VALUES (?)",
                (context_id,),
            )
        self._record_audit("local_stop", "local-user", context_id)

    def _is_stopped(self, context_id: str) -> bool:
        with sqlite3.connect(self._database_path) as connection:
            return connection.execute(
                "SELECT 1 FROM a2a_stopped_context WHERE context_id = ?", (context_id,)
            ).fetchone() is not None

    @staticmethod
    def _purge_expired_transcripts(connection: sqlite3.Connection) -> None:
        # Existing rows have no timestamp in the initial MVP schema, so retention
        # begins with this migration rather than guessing an unsafe creation time.
        for table in ("a2a_message_exchange", "a2a_outbound_exchange"):
            columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            if "created_at" not in columns:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN created_at REAL")
            connection.execute(
                f"DELETE FROM {table} WHERE created_at IS NOT NULL AND created_at < ?",
                (time.time() - TRANSCRIPT_RETENTION_SECONDS,),
            )

    def _load_exchange(self, message_id: str) -> tuple[str, str] | None:
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT request_json, response_json FROM a2a_message_exchange WHERE message_id = ?",
                (message_id,),
            ).fetchone()
        return (str(row[0]), str(row[1])) if row else None

    def _peer_transcript(self, context_id: str) -> list[dict[str, str]]:
        with sqlite3.connect(self._database_path) as connection:
            rows = connection.execute(
                "SELECT request_json, response_json FROM a2a_message_exchange WHERE context_id = ? ORDER BY rowid",
                (context_id,),
            ).fetchall()
        transcript: list[dict[str, str]] = []
        for request_json, response_json in rows:
            request_text = self._message_text(str(request_json))
            response_text = self._message_text(str(response_json))
            if request_text:
                transcript.append({"role": "user", "content": request_text})
            if response_text:
                transcript.append({"role": "assistant", "content": response_text})
        return transcript

    @staticmethod
    def _message_text(payload_json: str) -> str:
        payload = json.loads(payload_json)
        parts = payload.get("message", {}).get("parts", [])
        return "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))

    def _store_exchange(
        self,
        *,
        message_id: str,
        context_id: str,
        peer_id: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any],
    ) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT peer_id, peer_rounds FROM a2a_context WHERE context_id = ?",
                (context_id,),
            ).fetchone()
            if row is not None and (row[0] != peer_id or row[1] >= MAX_PEER_ROUNDS):
                raise OverflowError("A2A discussion has reached its peer-round limit")
            connection.execute(
                """
                INSERT INTO a2a_message_exchange
                    (message_id, context_id, peer_id, request_json, response_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    context_id,
                    peer_id,
                    json.dumps(request_payload, sort_keys=True),
                    json.dumps(response_payload, sort_keys=True),
                    time.time(),
                ),
            )
            if row is None:
                connection.execute(
                    "INSERT INTO a2a_context (context_id, peer_id, peer_rounds) VALUES (?, ?, 1)",
                    (context_id, peer_id),
                )
            else:
                connection.execute(
                    "UPDATE a2a_context SET peer_rounds = peer_rounds + 1 WHERE context_id = ?",
                    (context_id,),
                )

    def _record_outbound_exchange(
        self,
        *,
        message_id: str,
        context_id: str,
        peer_id: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any],
    ) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO a2a_outbound_exchange
                    (message_id, context_id, peer_id, request_json, response_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    context_id,
                    peer_id,
                    json.dumps(request_payload, sort_keys=True),
                    json.dumps(response_payload, sort_keys=True),
                    time.time(),
                ),
            )

    def _record_audit(self, event_type: str, peer_id: str, context_id: str) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO a2a_security_audit (event_type, peer_id, context_id, occurred_at)
                VALUES (?, ?, ?, ?)
                """,
                (event_type, peer_id, context_id, time.time()),
            )

    def _begin_outbound_discussion(self, peer_id: str) -> None:
        with sqlite3.connect(self._database_path) as connection:
            try:
                connection.execute(
                    "INSERT INTO a2a_outbound_session (peer_id, state) VALUES (?, 'active')",
                    (peer_id,),
                )
            except sqlite3.IntegrityError as exc:
                raise RuntimeError(f"A2A peer is busy: {peer_id}") from exc

    def _finish_outbound_discussion(self, peer_id: str) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute("DELETE FROM a2a_outbound_session WHERE peer_id = ?", (peer_id,))
