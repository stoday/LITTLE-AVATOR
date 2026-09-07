"""Trusted local display identities for MOMO and A2A communicators."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AvatarIdentity:
    owner_name: str
    communicator_name: str


def local_avatar_identity() -> AvatarIdentity:
    owner_name = os.getenv("LITTLE_AVATAR_OWNER_NAME", "").strip()
    configured_name = os.getenv("LITTLE_AVATAR_COMMUNICATOR_NAME", "").strip()
    communicator_name = configured_name or (f"{owner_name}的秘書" if owner_name else "MOMO")
    return AvatarIdentity(owner_name=owner_name, communicator_name=communicator_name)


def peer_avatar_identity(peer_agent_id: str) -> AvatarIdentity:
    """Resolve a peer only from this device's trusted identity mapping."""
    try:
        configured = json.loads(os.getenv("LITTLE_AVATAR_A2A_PEER_IDENTITIES", "{}"))[peer_agent_id]
        owner_name = str(configured["owner_name"]).strip()
        communicator_name = str(configured["communicator_name"]).strip()
    except (KeyError, TypeError, json.JSONDecodeError):
        return AvatarIdentity(owner_name="", communicator_name="對方秘書")
    if not owner_name or not communicator_name:
        return AvatarIdentity(owner_name="", communicator_name="對方秘書")
    return AvatarIdentity(owner_name=owner_name, communicator_name=communicator_name)
