# 01: Deliver an official A2A direct Message across two processes

**What to build:** Two independently configured LITTLE_AVATOR instances can authenticate one another over loopback HTTP, publish and read an official A2A Agent Card, and complete one generic natural-language direct Message without revealing local Skills or resources.

**Blocked by:** None (can start immediately).

**Status:** completed

- [x] The official A2A HTTP+JSON seam accepts a valid authenticated direct Message and returns an official direct Message response with text Parts.
- [x] A two-process loopback harness proves separate agent IDs, ports, private contexts, and data directories communicate through serialization rather than in-memory calls.
- [x] The Agent Card advertises only generic discussion, the A2A 1.0 version, HTTP+JSON interface, and authentication requirement.
