# Historical dinner-invitation example

> This document is a historical scheduling example. It does not define runtime decision logic:
> ordinary user replies are interpreted by the local MOMO admin, and the UI must not infer
> confirmation from keywords or directly trigger a confirmation action. See
> `AGENT_DRIVEN_COLLABORATION_DECISIONS_SPEC.md` for the governing behavior.

## Roles

- `agent-*-admin` is the user's local chat-facing agent. It receives a request,
  creates a delegation, and presents only its local report.
- `agent-*-communicator` owns approved availability/food-derived information and
  is the sole role that sends or receives A2A Messages.
- An admin is never an A2A peer and never receives the other user's private
  conversation, complete calendar, or communicator prompt.

## Flow

1. A user asks A-admin to invite a named contact to dinner.
2. A-admin resolves that contact through its local contact directory and creates
   a local delegation for A-communicator.
3. A-communicator sends a bounded A2A natural-language invitation to
   B-communicator.
4. Each communicator applies only its own approved availability and meal
   preferences, then returns an outcome to its own admin.
5. A-admin and B-admin separately tell their respective users the tentative
   time/food or the concrete reason no proposal is possible.
6. A tentative proposal is not a reservation, calendar write, or commitment.
   Each local user must separately confirm a later action Task.

## Visibility and diagnostics

Normal user chat never renders communicator-to-communicator messages. It
renders only the local admin's summary and, for a tentative proposal, a local
**Confirm locally** control. The raw A2A message records remain local protocol
history for a future diagnostics or demonstration view; they are not part of
the ordinary chat transcript or the admin delegation response.

## Local configuration for the dual-avatar test

Each instance uses a local JSON profile with:

```json
{
  "contacts": {"XXX": "avatar-b"},
  "availability": ["Wednesday 19:00", "Thursday 19:00"],
  "foods": ["hotpot", "sushi"]
}
```

Only the contact mapping and approved derived choices participate in the
workflow. The profile is never transmitted as a raw resource.
