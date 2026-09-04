from p2026_little_avator.lan_discovery import (
    MdnsPublisher,
    SERVICE_TYPE,
    DiscoveredPeer,
    peer_from_service_info,
    service_info,
    service_properties,
)


def test_mdns_peer_metadata_exposes_routing_and_identity_without_credentials() -> None:
    peer = DiscoveredPeer("agent-b", "fingerprint", "192.168.1.25", 9443)

    assert SERVICE_TYPE == "_little-avator-a2a._tcp.local."
    assert peer.a2a_url == "https://192.168.1.25:9443/a2a"
    assert service_properties("agent-b", "fingerprint") == {
        b"agent_id": b"agent-b",
        b"device_fingerprint": b"fingerprint",
    }
    record = service_info(peer)
    assert record.name == "agent-b._little-avator-a2a._tcp.local."
    assert record.port == 9443


def test_mdns_publisher_registers_and_unregisters_one_record() -> None:
    class ZeroconfStub:
        registered: list[object] = []
        unregistered: list[object] = []

        def register_service(self, record: object) -> None:
            self.registered.append(record)

        def unregister_service(self, record: object) -> None:
            self.unregistered.append(record)

    stub = ZeroconfStub()
    publisher = MdnsPublisher(stub)  # type: ignore[arg-type]
    publisher.publish(DiscoveredPeer("agent-b", "fingerprint", "host", 9443))
    publisher.close()

    assert len(stub.registered) == 1
    assert stub.unregistered == stub.registered


def test_mdns_candidate_uses_routing_hint_but_keeps_device_fingerprint() -> None:
    record = service_info(DiscoveredPeer("agent-b", "fingerprint", "192.168.1.25", 9443))

    candidate = peer_from_service_info(record)

    assert candidate == DiscoveredPeer("agent-b", "fingerprint", "192.168.1.25", 9443)


def test_mdns_discovery_emits_only_a_valid_candidate(monkeypatch) -> None:
    import p2026_little_avator.lan_discovery as discovery_module
    from p2026_little_avator.lan_discovery import MdnsDiscovery

    record = service_info(DiscoveredPeer("agent-b", "fingerprint", "192.168.1.25", 9443))

    class ZeroconfStub:
        def get_service_info(self, service_type: str, name: str) -> object:
            assert service_type == SERVICE_TYPE
            assert name == record.name
            return record

    class BrowserStub:
        def __init__(self, zeroconf: object, service_type: str, handlers: list[object]) -> None:
            handlers[0](zeroconf, service_type, record.name, "Added")

        def cancel(self) -> None:
            pass

    monkeypatch.setattr(discovery_module, "ServiceBrowser", BrowserStub)
    received: list[DiscoveredPeer] = []

    watcher = MdnsDiscovery(ZeroconfStub(), received.append)  # type: ignore[arg-type]
    watcher.close()

    assert received == [DiscoveredPeer("agent-b", "fingerprint", "192.168.1.25", 9443)]
