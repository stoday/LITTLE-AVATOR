# 15: Discover peers and complete physical Windows LAN acceptance

**What to build:** LITTLE_AVATOR discovers trusted LAN peer candidates through mDNS, handles a changed DHCP address as routing rather than identity, and passes an end-to-end two-Windows-machine acceptance run before it is described as LAN-complete.

**Blocked by:** 07: Report busy peers, unreachable peers, and bounded retries; 08: Stop a discussion and ignore late replies; 09: Manage transcript retention and security audit records; 12: Report action failure honestly and prevent duplicate commit; 14: Manage durable TOFU trust and local capability authority.

**Status:** in-progress

- [ ] Discovery locates the configured A2A service type and connects only after encrypted trust and local policy checks succeed.
- [ ] A physical two-machine Windows run verifies mDNS, DHCP address change, firewall behavior, device continuity, lock-state behavior, packets crossing the LAN, and end-to-end discussion/action responses.
- [ ] The acceptance report distinguishes prototype, loopback cross-process, physical LAN, and deployed-production evidence.
