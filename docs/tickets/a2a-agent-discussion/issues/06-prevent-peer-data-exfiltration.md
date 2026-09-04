# 06: Prevent peer-driven private-data exfiltration

**What to build:** Peer content is treated as untrusted, so requests for private prompts, thinking, credentials, ordinary-chat history, full resources, or unpublished Tool results receive only a policy-limited response and cannot trigger a side effect.

**Blocked by:** 05: Gate collaboration through Skill authority and disclosure policy.

**Status:** in-progress

- [ ] Adversarial A2A Messages requesting private material or arbitrary Skill loading are safely refused or restricted through the outward Message seam.
- [ ] Outbound transcript, persisted peer-visible records, and UI transcript exclude unapproved private context and raw Tool data.
- [ ] The same tests verify that an unauthorized commit request produces no local action.
