# 02: Reject invalid and replayed A2A traffic

**What to build:** A receiving LITTLE_AVATOR instance rejects malformed, version-incompatible, unsupported-media-type, unauthenticated, unauthorized, and repeated A2A Messages before they can cause an agent turn or local action.

**Blocked by:** 01: Deliver an official A2A direct Message across two processes.

**Status:** completed

- [x] Protocol-boundary tests observe official error behavior for invalid shapes, versions, content types, unknown peers, and incorrect development credentials.
- [x] Repeating one message ID produces one logical message and returns the stored reply after a client restart; altered replay payloads are rejected.
- [x] The idempotency decision is durable and recorded before the response is returned.
