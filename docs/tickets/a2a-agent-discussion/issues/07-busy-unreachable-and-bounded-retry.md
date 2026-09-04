# 07: Report busy peers, unreachable peers, and bounded retries

**What to build:** A user gets an immediate honest result when a peer is busy or unreachable, and collaboration-enabled Skills can request only a small, bounded retry policy rather than creating an invisible delivery queue.

**Blocked by:** 05: Gate collaboration through Skill authority and disclosure policy.

**Status:** in-progress

- [ ] A second active discussion receives an explicit busy response and is not silently queued.
- [ ] The default sends once and reports an unreachable peer immediately; a Skill may request at most three delayed retries.
- [ ] The chat UI displays the outcome clearly and the integration harness proves no work occurs after retry exhaustion.
