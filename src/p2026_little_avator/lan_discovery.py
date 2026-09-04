"""mDNS service metadata for trusted LITTLE_AVATOR peer discovery."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from zeroconf import ServiceBrowser, ServiceInfo, ServiceStateChange, Zeroconf


SERVICE_TYPE = "_little-avator-a2a._tcp.local."


@dataclass(frozen=True)
class DiscoveredPeer:
    agent_id: str
    device_fingerprint: str
    host: str
    port: int

    @property
    def a2a_url(self) -> str:
        return f"https://{self.host}:{self.port}/a2a"


def service_properties(agent_id: str, device_fingerprint: str) -> dict[bytes, bytes]:
    """Publish only stable identity hints; credentials never enter mDNS."""

    return {b"agent_id": agent_id.encode(), b"device_fingerprint": device_fingerprint.encode()}


def service_info(peer: DiscoveredPeer) -> ServiceInfo:
    """Create the actual zeroconf record without embedding credentials."""

    return ServiceInfo(
        type_=SERVICE_TYPE,
        name=f"{peer.agent_id}.{SERVICE_TYPE}",
        server=f"{peer.host}.",
        port=peer.port,
        properties=service_properties(peer.agent_id, peer.device_fingerprint),
    )


def peer_from_service_info(record: ServiceInfo) -> DiscoveredPeer:
    """Turn a discovered mDNS record into an untrusted routing candidate."""
    properties = record.properties
    try:
        agent_id = properties[b"agent_id"].decode()
        fingerprint = properties[b"device_fingerprint"].decode()
    except (KeyError, UnicodeDecodeError) as exc:
        raise ValueError("mDNS A2A record is missing valid identity metadata") from exc
    host = record.server.rstrip(".")
    if not agent_id or not fingerprint or not host or not record.port:
        raise ValueError("mDNS A2A record is incomplete")
    return DiscoveredPeer(agent_id, fingerprint, host, record.port)


class MdnsPublisher:
    """Own one explicit local mDNS registration lifecycle."""

    def __init__(self, zeroconf: Zeroconf) -> None:
        self._zeroconf = zeroconf
        self._record: ServiceInfo | None = None

    def publish(self, peer: DiscoveredPeer) -> None:
        if self._record is not None:
            raise RuntimeError("mDNS service is already published")
        self._record = service_info(peer)
        self._zeroconf.register_service(self._record)

    def close(self) -> None:
        if self._record is not None:
            self._zeroconf.unregister_service(self._record)
            self._record = None


class MdnsDiscovery:
    """Translate mDNS service additions into untrusted routing candidates."""

    def __init__(self, zeroconf: Zeroconf, on_candidate: Callable[[DiscoveredPeer], None]) -> None:
        self._zeroconf = zeroconf
        self._on_candidate = on_candidate
        self._browser = ServiceBrowser(zeroconf, SERVICE_TYPE, handlers=[self._service_changed])

    def _service_changed(
        self, zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange
    ) -> None:
        if state_change != ServiceStateChange.Added and str(state_change).casefold() != "added":
            return
        record = zeroconf.get_service_info(service_type, name)
        if record is None:
            return
        try:
            candidate = peer_from_service_info(record)
        except ValueError:
            return
        self._on_candidate(candidate)

    def close(self) -> None:
        self._browser.cancel()
