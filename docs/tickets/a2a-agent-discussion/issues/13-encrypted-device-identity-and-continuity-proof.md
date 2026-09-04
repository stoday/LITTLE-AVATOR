# 13: Establish encrypted Device Identity and continuity proof

**What to build:** The loopback development credential is replaced by encrypted transport, a device key, and a challenge-based continuity proof that binds transport identity to the expected peer without treating an IP address as identity.

**Blocked by:** 02: Reject invalid and replayed A2A traffic.

**Status:** in-progress

- [ ] A trusted encrypted peer can use the A2A HTTP+JSON interface only after device-key proof succeeds.
- [ ] A routing-address change alone does not change peer identity.
- [ ] Integration tests distinguish encrypted device identity evidence from the retired development credential path.
