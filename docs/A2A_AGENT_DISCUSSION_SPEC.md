# LITTLE_AVATOR A2A Agent Discussion Specification

Status: proposed. This document specifies the feature only; it implements no code. It is awaiting user confirmation.

## Problem Statement

LITTLE_AVATOR currently supports conversations between one user and one local Momo agent, and it can load local Skills to gain additional instructions, resources, and executable abilities. It does not yet provide a production feature through which independently owned agents can contact one another, exchange views over multiple turns, reach a useful conclusion, and—when a local Skill and its policy permit—perform an action for their respective users.

The existing prototypes answer only narrow questions. One prototype demonstrates a same-process relay between two Akasha agents with private local context. Another demonstrates the state transitions of a Trust on First Use record. They do not establish an A2A-compliant network contract, independent process isolation, persistent protocol state, real device identity, encrypted LAN transport, safe authorization, or deployed two-machine operation.

The feature must not become a meeting scheduler disguised as a general collaboration system. Exchanging opinions without reaching agreement is a valid use case. Meeting-time negotiation is only an example used to exercise local Skills, private data access, user confirmation, and commit behavior. Different users may have completely different Skills, tools, prompts, storage systems, and negotiation methods; interoperability must come from the Agent2Agent Protocol and natural-language communication, not from installing matching Skills.

The feature must also avoid accumulating a custom protocol that only resembles A2A. Doing so would make later standards compliance progressively more expensive. The official A2A 1.0 data model and HTTP+JSON binding must therefore be the only wire contract from the first implementation onward.

## Solution

Add an application-owned Collaboration Module to every running LITTLE_AVATOR instance. The module starts with the application and exposes an A2A 1.0 HTTP+JSON interface and well-known Agent Card. There is no master A2A feature toggle: running LITTLE_AVATOR means its A2A service is running, and closing LITTLE_AVATOR stops the service. Local trust, capability policy, disclosure policy, and Skill-specific commit rules continue to decide what a peer may actually cause the local agent to observe, recommend, or commit.

Ordinary discussions use the official A2A Send Message operation synchronously. The initiator sends a natural-language Message, the remote agent performs one isolated turn and returns a natural-language Message, and the initiator decides whether another turn is useful. Related Messages use the official `contextId`; LITTLE_AVATOR does not define a competing wire-level DiscussionSession model. Operations that require waiting, additional input, authorization, or side effects use an official A2A Task and its unmodified lifecycle.

Each A2A context receives an isolated background agent and conversation history. It does not inherit the user's ordinary chat transcript. The agent may load only local Skills that explicitly opt into collaboration and that local policy permits for the authenticated peer. Peers never request a Skill or Tool by name and never receive private prompts, model thinking, credentials, full private resources, or unpublished Tool results. The wire content is natural language in A2A text Parts; the system does not require matching domain schemas, matching Skill versions, or special agreement markers.

The first vertical slice runs two independent LITTLE_AVATOR processes over loopback HTTP. Each process owns a different agent, data directory, SQLite store, private context, Skill implementation, and policy. It validates real serialization and process isolation while postponing physical-LAN discovery and device cryptography. That postponement is explicitly temporary: the next required phase must add mDNS discovery, encrypted transport, device keys, continuity proof, durable TOFU records, and two-machine end-to-end validation before the feature can be described as LAN-complete.

## User Stories

1. As a LITTLE_AVATOR user, I want to ask Momo to consult another person's agent in ordinary language, so that I do not need to learn a separate collaboration interface.
2. As a LITTLE_AVATOR user, I want agents to exchange viewpoints even when no action or agreement is expected, so that collaboration is not limited to workflow automation.
3. As a LITTLE_AVATOR user, I want Momo to summarize a completed agent discussion in my original chat, so that I can understand the result without reading every turn.
4. As a LITTLE_AVATOR user, I want to expand a separate discussion transcript, so that I can inspect what the agents actually told one another.
5. As a LITTLE_AVATOR user, I want discussion progress shown outside my ordinary chat history, so that background turns do not pollute the conversation I am having with Momo.
6. As a LITTLE_AVATOR user, I want to stop an active discussion, so that I remain in control of time, cost, and unwanted communication.
7. As a LITTLE_AVATOR user, I want a late remote reply ignored after I stop a discussion, so that canceled work cannot silently resume.
8. As a LITTLE_AVATOR user, I want an unreachable peer reported immediately, so that the system behaves like a failed phone call rather than an invisible background job.
9. As a LITTLE_AVATOR user, I want a Skill to request a small, bounded number of delayed retries when appropriate, so that transient unavailability can be handled without indefinite calling.
10. As a LITTLE_AVATOR user, I want a busy peer reported as busy instead of being placed in an invisible queue, so that I know to try later.
11. As a LITTLE_AVATOR user, I want A2A available whenever LITTLE_AVATOR is running, so that I do not have to reason about and enable many small feature switches.
12. As a LITTLE_AVATOR user, I want closing LITTLE_AVATOR to stop its A2A service, so that the application's lifecycle remains understandable.
13. As a receiving user, I want an unknown or unauthorized peer prevented from using my local abilities, so that device discovery does not imply access.
14. As a receiving user, I want a trusted peer to use only the local collaboration abilities permitted by my policy, so that trust and authority remain separate decisions.
15. As a receiving user, I want an unsolicited first-contact discussion to require my approval, so that a newly observed device cannot automatically inspect local data.
16. As a receiving user, I want a known peer whose device key changes to be rejected, so that a changed identity cannot silently replace an established Trust Record.
17. As a receiving user, I want to revoke a peer's Trust Record, so that a lost, replaced, or suspicious device loses future access.
18. As a user with private data, I want my ordinary chat history excluded from A2A agent context, so that unrelated personal conversation is not disclosed to a peer.
19. As a user with private data, I want my private prompt and model thinking to remain local, so that internal reasoning is never treated as collaboration content.
20. As a user with private data, I want each local Skill to control the disclosure granularity of its resources, so that a calendar can answer availability without revealing event titles.
21. As a user with private data, I want outbound disclosure policy to reject credentials, private prompts, and unapproved raw Tool results, so that a malicious natural-language request cannot simply ask the agent to leak them.
22. As a user, I want to be warned that a sent message may remain on the peer device, so that deleting my local transcript is not misrepresented as remote deletion.
23. As a user, I want transcript retention to default to 30 days and allow immediate local deletion, so that useful inspection does not become indefinite content retention.
24. As a user, I want security audit events retained without unnecessary message bodies, so that trust and commit incidents can be investigated with less privacy exposure.
25. As a meeting participant, I want my own agent to read my calendar through my locally installed Skill, so that the peer never needs direct access to my calendar provider.
26. As a meeting participant, I want the other person's agent to use a completely different calendar Skill or storage implementation, so that collaboration does not require identical installations.
27. As a meeting participant, I want both users to confirm the final meeting before their respective calendar commits, so that an agent agreement is not mistaken for user authorization.
28. As a user of a non-calendar Skill, I want its own policy to determine whether zero, one, or multiple confirmations are required, so that the meeting example does not impose its rules on every discussion.
29. As a user, I want a failed commit on either side reported honestly, so that agreement is not falsely presented as successful execution.
30. As an agent, I want to receive only natural-language peer content plus standard A2A metadata, so that my internal method remains independent of the peer's Skills.
31. As an agent, I want to choose my own local Skills and Tools in response to a peer message, so that the remote agent cannot direct my implementation.
32. As an initiating agent, I want to decide after each reply whether to continue, summarize, or fail, so that the remote agent does not need a proprietary termination marker.
33. As an initiating agent, I want a hard maximum on turns, elapsed time, and token use, so that natural-language discussion cannot continue indefinitely.
34. As a remote agent, I want duplicate message IDs detected, so that network repetition does not execute my turn or local actions twice.
35. As a Skill author, I want to opt a Skill into collaboration explicitly, so that ordinary trusted Skills are not automatically exposed to peers.
36. As a Skill author, I want to declare the maximum local authority used during collaboration, so that an observe-only Skill cannot accidentally commit an action.
37. As a Skill author, I want to define retry timing and count within a system maximum, so that domain-specific retry behavior remains bounded.
38. As a Skill author, I want to define completion, disclosure, confirmation, commit, and result-verification behavior locally, so that the generic Collaboration Module remains domain-neutral.
39. As a Skill author, I want no requirement to publish my internal Skill name or implementation in the Agent Card, so that local techniques stay private.
40. As a developer, I want the official A2A 1.0 schema to be the only wire model, so that future protocol upgrades do not require translating an invented parallel protocol.
41. As a developer, I want simple discussions to return direct A2A Messages, so that the common path remains synchronous and easy to test.
42. As a developer, I want long-running or action-producing work to use official A2A Tasks, so that polling, input requests, authorization, cancellation, and terminal states remain standards-compliant.
43. As a developer, I want the well-known Agent Card to advertise only generic natural-language discussion, so that protocol discovery does not reveal local private capabilities.
44. As a developer, I want each A2A context to own an isolated agent and history, so that simultaneous chat and collaboration state cannot corrupt or leak into one another.
45. As a developer, I want two independent loopback processes in the first integration test, so that serialization, identity, storage, and context isolation are tested across a real process boundary.
46. As a developer, I want the meeting example to use different local data implementations on the two peers, so that heterogeneous Skills are proven by behavior.
47. As a developer, I want future multi-party discussion to coordinate multiple pairwise A2A contexts locally, so that the official point-to-point wire model is not modified with a proprietary participants field.
48. As a security reviewer, I want malformed, unauthenticated, unauthorized, and replayed A2A requests rejected at the application boundary, so that an agent never processes them as ordinary conversation.
49. As a security reviewer, I want peer messages treated as untrusted content, so that prompt injection is part of the threat model rather than delegated to model goodwill.
50. As a product owner, I want backend protocol validation and visible Windows UI validation reported separately, so that passing unit tests is not misrepresented as a complete user feature.
51. As a product owner, I want local cross-process validation distinguished from physical-LAN validation, so that the mandatory networking and device-trust phase cannot be forgotten.
52. As a product owner, I want existing prototypes retained as exploration evidence but excluded from production architecture, so that prototype shortcuts do not become hidden product contracts.

## Implementation Decisions

- The official Agent2Agent Protocol 1.0 canonical data model is the sole wire model. The HTTP+JSON/REST binding is used because the application already exposes a FastAPI service. Protocol version negotiation and content types follow A2A rather than project-specific conventions.
- The service publishes an official well-known Agent Card whenever LITTLE_AVATOR runs. The Agent Card advertises one generic natural-language discussion skill, the supported A2A version, the HTTP+JSON interface, and its authentication requirement. It does not advertise local calendar providers, Skill names, private resources, or negotiation methods.
- There is no master A2A enable switch. Starting LITTLE_AVATOR starts the A2A service; stopping the application stops it. Security is enforced by authentication, Trust Records, Local Capability Policy, disclosure policy, and Skill-specific authorization rather than by requiring users to manage many feature toggles.
- The initial cross-process milestone binds each instance to a configured loopback port and uses an explicit peer allowlist containing the peer agent ID, endpoint, and development credential. Unknown peers and incorrect credentials are rejected before an agent turn begins.
- The mandatory LAN follow-up replaces the development credential with encrypted transport, Device Identity, Device Continuity Proof, durable TOFU Trust Records, mDNS candidate discovery, and physical two-machine validation. IP addresses and mDNS names remain routing hints, not identity.
- TOFU records device-key continuity only. A newly observed Device Identity starts with no local capability authority. A user-initiated discussion may grant the selected peer session-scoped observe or recommend authority; an unsolicited first contact requires local approval. A key change for a known agent ID is rejected until the old Trust Record is explicitly revoked.
- Ordinary multi-turn discussion uses the official Send Message operation and direct Message responses. Each Message uses an official message ID, role, context ID, and one or more text Parts. The collaboration content is natural language; no custom proposal schema, agreement marker, remote Tool name, or matching Skill identifier is required.
- A2A `contextId` is the canonical identifier for related Messages. The UI may call the context a discussion, but the wire protocol and persisted protocol records do not introduce a competing DiscussionSession schema.
- The initiating LITTLE_AVATOR instance is the discussion host. It sends the first Message, invokes its own isolated agent after receiving a reply, and decides locally whether another peer turn is useful. The peer processes one inbound turn and returns a response; it does not run a shared orchestrator.
- The default discussion ceiling is thirty peer rounds. When this ceiling is reached before a conclusion, the application stops automatic discussion and explicitly notifies the local user that no conclusion was reached. The application also imposes elapsed-time and token ceilings. A Skill may lower these limits but cannot make them unbounded.
- The initial implementation permits one active A2A discussion per LITTLE_AVATOR process. A concurrent request receives an explicit busy response and is not silently queued. Historical contexts remain independently readable.
- Sending is phone-call-like rather than mailbox-like. The default is one immediate attempt. A collaboration-enabled Skill may request zero to three bounded retries and specify a delay. Failure is reported to the user; there is no indefinite background delivery, cloud inbox, or offline mailbox.
- A repeated message ID must not produce another agent turn or commit. Idempotency records are persisted locally before a response is returned.
- User cancellation stops subsequent turns and cancels local waiting. The initial implementation does not require the peer's in-progress model call to terminate. A late reply is persisted as late delivery if needed for audit but cannot reactivate the stopped local interaction.
- Work that can respond immediately returns an A2A Message and does not create a Task. Work that must wait, request more input, obtain protocol authorization, or perform an action creates an official A2A Task and follows the complete A2A lifecycle without renamed or reduced wire states.
- Waiting for the server's own local user to confirm an action keeps the Task working. Input-required is used when the client must supply additional information. Auth-required is used for the protocol's authorization flow, not as a generic synonym for a local confirmation dialog. Local rejection produces the official rejected terminal state.
- User confirmation is never inferred from agent prose. The meeting example requires confirmation by both users before the respective local calendar commits. Other Skills define their own confirmation policy; discussion-only Skills need no commit or confirmation.
- Device continuity and operation authority are independent. Local Capability Policy continues to use observe, recommend, and commit. A peer cannot acquire authority by claiming it inside an A2A Message.
- The Collaboration Module is application-owned. It owns the A2A server and client, Agent Card, authentication, trust checks, context and Task persistence, idempotency, retry ceilings, concurrency, cancellation, audit, disclosure enforcement, and authorization gates.
- A local Skill owns its domain method: which local resources it can read, how it reasons about the discussion, what information it may disclose, how it detects sufficient discussion, what confirmation it needs, how it commits, and how it verifies the resulting side effect.
- A Skill must explicitly opt into collaboration through validated metadata declaring its maximum authority, initially observe and/or recommend with commit reserved for Skills that supply an application-integrated execution and confirmation path. Skills without this declaration are unavailable to A2A background agents.
- Collaboration opt-in does not create cross-peer Skill compatibility. Each agent independently selects its local Skills. A peer can describe a goal only in natural language and cannot request that the receiver load a named Skill or call a named Tool.
- A2A background agents are isolated per context. They share the approved Momo persona but do not receive the user's ordinary chat history. They receive only the peer transcript, trusted runtime framing, and local context explicitly provided by allowed Skills.
- Peer content is always marked as untrusted. Private prompts, model thinking, credentials, reusable login material, full private resources, and unpublished raw Tool results are never message content. Local Skills and an outbound disclosure policy determine what derived information may be sent.
- Each process persists the A2A objects it sends or receives, delivery and retry facts, peer identity, local Skill usage, authorization facts, commit results, and security audit events in its own SQLite store. It does not serialize live agent objects, private prompts, thinking, or complete private Tool state.
- Natural-language transcripts default to a 30-day retention period and may be deleted immediately by the local user. Security audit records may be retained longer without message bodies. Local deletion makes no claim about copies already received by a peer.
- The ordinary chat remains the user's entry point. The primary Momo agent asks the Collaboration Module to start an A2A interaction. Progress is shown outside the ordinary transcript; a final summary returns to the original chat. A separate expandable transcript exposes the exchanged Messages without exposing private context or thinking.
- Future multi-party collaboration remains pairwise on the wire. The host maintains one official A2A context per peer and may group those context IDs in a local UI projection. No proprietary participants field is added to A2A Message, Task, or context objects.
- The first behavior examples are deliberately different. One exchanges opinions and completes through direct natural-language Messages without a Task or commit. The other negotiates a meeting time and uses different calendar Skill/storage implementations on the two processes, proving that matching Skills are unnecessary.
- Existing prototypes remain throwaway evidence. Production code is implemented behind the Collaboration Module and official A2A boundary rather than copied from the same-process relay, marker parser, or in-memory TOFU demo.
- The A2A 1.0 major version is pinned. Official schemas or generated types are preferred to copied, hand-edited models. Project-specific protocol data, if eventually required, uses standards-compliant namespaced A2A extensions and requires a separate architecture decision and interoperability tests.

## Testing Decisions

- The highest behavioral seam is the official A2A HTTP+JSON interface, including the Agent Card, Send Message, direct Message response, Task operations, authentication, version negotiation, media types, and standard errors. Tests observe protocol behavior, not private orchestration functions or ORM details.
- The second seam is a two-process integration harness. It starts two independent LITTLE_AVATOR instances with different agent IDs, ports, data directories, SQLite databases, private context, and local Skills. Passing a same-process unit test is not equivalent to passing this seam.
- The third seam is visible desktop behavior. UI tests and manual Windows acceptance verify ordinary-chat initiation, progress outside transcript history, expandable peer transcript, stopping, busy/unreachable feedback, confirmation prompts, and final summary. Backend success is not reported as UI success.
- Protocol conformance tests validate the well-known Agent Card, the declared A2A 1.0 HTTP+JSON interface, required request headers, official Message and Part shapes, direct Message responses, Task creation and retrieval, official TaskState values, standard errors, content types, and protocol-version rejection.
- Natural-language discussion tests use deterministic fake agents. They verify multiple turns under one context ID, initiator-owned continuation, completion without agreement, the six-round ceiling, time/token ceilings, and a final summary returned to the originating chat.
- Heterogeneous Skill tests give the two processes different calendar Skill names, prompts, storage types, and local algorithms. The test succeeds only through exchanged text Parts and must not rely on matching Skill metadata or shared domain payloads.
- Privacy tests verify ordinary chat history, private prompts, thinking events, credentials, full calendar entries, and unapproved raw Tool results never appear in outbound A2A Messages, persisted peer-visible artifacts, or the transcript UI.
- Adversarial tests send peer text that asks for system prompts, credentials, complete calendars, hidden Tool output, arbitrary Skill loading, and unauthorized commit. The expected result is safe refusal or policy-limited disclosure, with no side effect.
- Trust and authorization tests reject unknown peers, incorrect development credentials, revoked peers, changed Device Identity, insufficient Local Capability Policy, and commit attempts without the Skill-required local confirmation.
- Idempotency tests repeat the same message ID and verify one agent turn, one persisted logical Message, and at most one side effect.
- Retry tests verify the default single attempt, Skill-selected delay and retry count, the system maximum of three retries, immediate user-visible failure when retries are disabled, and no work after the retry budget is exhausted.
- Concurrency tests verify one active A2A interaction per process, an explicit busy response for another caller, no invisible queue, and no corruption between historical contexts.
- Cancellation tests verify no subsequent peer call after local stop, no reactivation from a late response, and honest reporting when an already-running remote model call cannot be interrupted.
- Task tests distinguish direct Message discussion from action-producing Tasks. They verify local-user waiting remains working, client input uses input-required, protocol authorization uses auth-required, local refusal uses rejected, successful verified action uses completed, and operational failure never appears completed.
- Commit tests verify the meeting example requires both local users' confirmation, each side commits only through its own Skill, duplicate commit is prevented, and one failed side is reported as partial or failed rather than agreed-and-written.
- Persistence tests verify each process stores only its own observed protocol history and audit, transcript retention and deletion behavior, idempotency across restart, and that an interrupted execution does not resume autonomously after restart.
- An integration test proves the opinion-exchange example completes without calendar access, Task creation, user confirmation, or commit. This protects the domain-neutral collaboration boundary.
- Existing conversation API tests, Skill-host tests, and desktop chat tests remain regression coverage. A2A additions must not merge ordinary chat history into collaboration context or change existing chat behavior while no A2A interaction is active.
- The later LAN phase requires separate physical validation on two Windows machines. It must verify mDNS discovery, DHCP address change, TLS/device-key proof, TOFU continuity, changed-key rejection, Windows lock behavior, firewall configuration, actual packets crossing the LAN, and end-to-end A2A responses. Loopback evidence does not satisfy this gate.

## Out of Scope

- Requiring peers to install the same Skill, use the same Tool, expose the same data provider, or follow the same negotiation algorithm.
- Defining a universal domain schema for proposals, agreements, objections, meeting slots, or discussion outcomes. The initial wire content is natural-language text Parts.
- A proprietary A2A-like endpoint, custom Message or Task schema, reduced wire Task lifecycle, or custom participants field.
- Full implementation of every A2A binding and delivery mode. The first implementation uses HTTP+JSON, direct Messages, and only the Task operations needed by the validated examples; gRPC, JSON-RPC, streaming, and push notifications are deferred.
- A centralized relay, organization directory, cloud offline inbox, public-Internet discovery, or cross-network delivery.
- Production calendar providers. The meeting vertical slice uses local deterministic test Skills and storage implementations.
- More than one simultaneous active A2A interaction per process in the first implementation.
- Complete multi-party orchestration in the first implementation. The design preserves pairwise A2A contexts so it can be added later without changing the wire protocol.
- Treating TOFU as proof of corporate identity, employee status, or EIP authentication.
- Sharing EIP cookies, browser sessions, account passwords, hardware private keys, reusable provider tokens, private prompts, model thinking, or unrestricted local resource content.
- Claiming production LAN readiness from prototype tests, schema tests, same-process execution, loopback integration, or a local UI demonstration.

## Further Notes

- Normative protocol reference: https://a2a-protocol.org/latest/specification. The implementation decision is A2A 1.0 with its canonical schema and HTTP+JSON binding; any later version change requires explicit review.
- The current same-process negotiation prototype remains valuable as evidence that two isolated agents can relay answer text and reach a locally checked conclusion. Its private-data isolation is incomplete because full natural-language responses and result artifacts can reveal derived private information; production disclosure policy must be stronger.
- The current TOFU prototype verifies first sight, continuity, changed-key rejection, and revocation only as an in-memory state machine. It does not verify key generation, challenge signing, encryption, secure storage, or LAN identity.
- The real-LAN phase is a required continuation, not an optional nice-to-have. Until it passes physical two-machine validation, status reporting must say “local cross-process A2A validated,” never “LAN A2A complete.”
- The project currently has no issue-tracker configuration or `ready-for-agent` label vocabulary available to this session. Per the user's request, this specification is a local review document and has not been published or labelled.
