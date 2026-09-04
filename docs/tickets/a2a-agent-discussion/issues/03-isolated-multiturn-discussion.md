# 03: Run an isolated multi-turn A2A discussion

**What to build:** An initiating LITTLE_AVATOR instance owns a multi-turn natural-language discussion under one official contextId, deciding after each peer response whether to continue or summarize, while the peer processes exactly one inbound turn at a time.

**Blocked by:** 02: Reject invalid and replayed A2A traffic.

**Status:** completed

- [x] Deterministic agents prove multi-turn direct Messages, initiator-owned continuation, completion without agreement, and the six-round, elapsed-time, and token ceilings.
- [x] Each A2A context has isolated agent/history state and persisted local protocol history; ordinary chat history is excluded.
- [x] The two-process integration seam proves no shared process state or proprietary agreement marker is needed.
