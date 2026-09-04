# 14: Manage durable TOFU trust and local capability authority

**What to build:** A user can approve first contact, grant session-scoped authority, reject a changed key, and revoke a peer, while Device Identity continuity remains separate from observe, recommend, and commit authority.

**Blocked by:** 05: Gate collaboration through Skill authority and disclosure policy; 13: Establish encrypted Device Identity and continuity proof.

**Status:** in-progress

- [ ] An unsolicited unknown peer requires local approval and begins with no capability authority.
- [ ] A known agent ID with a changed device key is rejected until the old Trust Record is explicitly revoked.
- [ ] Trust and policy decisions survive restart and are visible through a local user-facing management flow.
