# Momo Notes and Proactive Reminders

Status: proposed. This document specifies the feature only; it implements no code.

## Goal

Momo keeps a small, developer-editable set of Markdown notes, uses all current
notes as context for ordinary Agent conversations, and proactively speaks a due
reminder in that same conversation. Direct token-streamed questions and answers
remain available. This feature does not use RAG.

## Confirmed decisions

- Notes and reminders survive closing Momo and restarting Windows.
- `data/momo-notes.md` is the source of truth. A developer may edit it directly.
  The application reads it afresh before every Agent turn and scheduler scan.
- Complete note text is supplied to every Agent turn as data, not instructions.
- One local Avatar owns one long-lived, in-memory conversation per running
  session. Its history resets on exit; Markdown notes do not.
- The Agent may infer a durable note or requested reminder from ordinary chat
  and call note Tools. It reports the result in its answer.
- Update and delete require one unambiguous target. The Agent asks a clarifying
  question rather than guessing which note to change.
- Only one-time date/time and daily `HH:MM` reminders are supported.
- Time defaults to the Windows local timezone, overridden by `MOMO_TIMEZONE`.
- Every reminder is queued as a normal conversation turn. The Agent, not a
  separate UI channel, writes the visible reminder response.
- An in-flight Agent response is never interrupted. A due reminder runs next.
- If no desktop client is connected when a reminder is due, it is skipped and
  never replayed. The outcome is logged.
- Note changes, scheduling results, and parser errors go to a separate JSONL
  activity log. They are separate from Akasha diagnostics.

## Non-goals

- RAG, embeddings, vector databases, cloud sync, accounts, or multiple users.
- Folder/file selection, browser, shell, desktop, network, or unrestricted
  filesystem Tools.
- Weekly/workday/interval/cron recurrence, a notes-management GUI, or reminders
  replayed after Momo was unavailable.
- Exposing thinking, Tool arguments/results, traces, credentials, or raw
  scheduler payloads to the desktop UI.

## Runtime files

The default local data directory is `data/` relative to the application working
directory.

| File | Owner | Purpose |
| --- | --- | --- |
| `data/momo-notes.md` | Developer and note Tools | Human-readable notes plus reminder metadata. |
| `data/momo-activity.jsonl` | Application | Append-only audit events. |
| `logs/` | Akasha | Existing development diagnostics; unchanged. |

The application creates an empty notes file with a short comment header when it
does not exist. Tool writes are atomic (temporary file then replacement), so a
scanner never reads a partial Tool write. A malformed developer edit is never
repaired automatically.

### Markdown format

Every note has a stable UUID and readable prose. Reminder state is an HTML
comment so it does not disrupt normal reading.

```md
# Momo notes

## Stretch reminder
每天三點提醒我起來動一動。

<!-- momo-note: {"id":"8df2c18d-1a94-4ff0-a064-9a4b37d5625b","reminder":{"kind":"daily","time":"15:00","enabled":true,"last_handled_occurrence":null}} -->
```

A one-time reminder uses a timezone-aware value:

```json
{"kind":"once","due_at":"2026-08-29T15:00:00+08:00","enabled":true,"last_handled_occurrence":null}
```

`last_handled_occurrence` is application-maintained. It identifies a delivered
or skipped occurrence, preventing repeated notices on later scans. A developer
metadata edit is trusted as an intentional change.

Malformed or unsupported reminder metadata leaves its prose usable as note
context but disables scheduling for that entry. The application emits one
`notes_parse_error` audit event per unchanged faulty file revision, rather than
one per minute.

## Agent and Tool boundary

`create_akasha_agent()` retains one `stream=True` Agent per conversation. It
receives only application-owned Tools:

| Tool | Contract |
| --- | --- |
| `create_note` | Accepts prose and an optional supported reminder; creates one UUID-backed entry. |
| `update_note` | Requires an unambiguous note id plus replacement prose/reminder. |
| `delete_note` | Requires an unambiguous note id and removes exactly that entry. |
| `get_current_time` | Accepts no user-controlled path/command input and returns effective local time. |

The Tool descriptions and Momo system prompt state when automatic note capture
is appropriate: durable facts, preferences, commitments, and requested
reminders. Markdown is user data, never a source of privileged instructions or
additional Tool permissions. Tool code—not the model—owns validation, IDs,
Markdown parsing, atomic writes, schedule state, and audit writes.

Before each Agent turn, the backend passes:

1. the fixed Momo prompt and Tool policy;
2. freshly loaded complete Markdown notes, clearly delimited as data;
3. complete in-memory history from this Momo session; and
4. the trusted queue item: a user message or a due-reminder instruction.

The implementation must pass history through Akasha's public
`agent(question, messages=history)` interface. Reusing an Agent instance alone
does not supply prior messages.

## Conversation queue and SSE

Each conversation owns one typed `asyncio.Queue` and one worker. The worker is
the sole owner of the mutable Akasha Agent.

```text
user message ----> ConversationInput(kind="user") ----\
                                                        > serial worker -> Agent -> SSE
due reminder ---> ConversationInput(kind="reminder") -/
```

`POST /api/conversations/{id}/messages` validates and enqueues a user item,
then returns `202 Accepted`. It does not reject a message because an Agent turn
is already active; FIFO order defines visible order.

The reminder scanner supplies only a validated note id, due occurrence, current
time, and original reminder prose. The Agent receives an instruction to write a
short proactive reminder, without arbitrary Tool calls. The resulting assistant
notification becomes part of this session's history.

The desktop creates its conversation and opens
`GET /api/conversations/{id}/events` at Avatar startup. The connection stays
open after a turn completes and emits heartbeats while idle. It is no longer
opened only after the first user message.

| SSE event | Data | Client behavior |
| --- | --- | --- |
| `turn_started` | `turn_id`, `origin` (`user` or `reminder`) | Starts one transcript turn; user turns show normal waiting feedback. |
| `answer` | `turn_id`, `text` | Appends only streamed Momo text to that turn. |
| `completed` | `turn_id`, `origin` | Ends the turn without closing the SSE connection. |
| `error` | `turn_id`, safe `message` | Ends only that failed turn and restores input. |

No Akasha thinking, Tool data, trace, credential, or raw scheduler payload is
forwarded. A queued reminder appears as a new Momo transcript turn, not as
unlabelled text inserted into a partial answer.

If no desktop SSE subscriber exists at an occurrence, the scanner records
`skipped_no_client`, marks it handled, and does not enqueue an Agent turn.

## Scheduler and audit log

FastAPI lifespan starts one task that scans fresh Markdown every 60 seconds and
cancels/awaits it at shutdown. Production uses the effective timezone; tests
inject a clock.

For an enabled reminder, a scan performs exactly one relevant outcome:

- enqueue a reminder turn when it is due, unhandled, and a client is connected;
- append `reminder_delivered` only after that Agent turn completes;
- append `skipped_no_client` when no client is connected;
- append `skipped_missed` once when startup first observes a past unhandled
  occurrence; or
- append a parse/scheduling failure without stopping other reminders.

An Agent/provider failure appends `reminder_agent_failed` and does not retry or
replay that occurrence automatically.

`data/momo-activity.jsonl` contains one object per line, for example:

```json
{"timestamp":"2026-08-28T15:00:03+08:00","type":"reminder_delivered","note_id":"8df2c18d-1a94-4ff0-a064-9a4b37d5625b","occurrence":"2026-08-28T15:00:00+08:00","source":"scheduler"}
```

Allowed types include `note_created`, `note_updated`, `note_deleted`,
`reminder_delivered`, `skipped_no_client`, `skipped_missed`,
`reminder_agent_failed`, and `notes_parse_error`. It contains no full chat,
credential, thinking trace, or raw Tool trace. The developer retains or removes
it manually.

## TDD plan and public seams

No test or feature code starts before this specification is approved. Tests are
red-first and vertical: one public behavior, minimal implementation, then the
next behavior.

| Slice | Public seam | First red behavior |
| --- | --- | --- |
| Markdown notes | `NoteStore` public API and resulting Markdown | A created daily reminder is readable by a new store instance. |
| Tool policy | Fake Agent's exposed Tool list | A durable chat statement creates one readable note; ambiguous edit changes none. |
| Context | Agent factory call arguments | A later turn receives fresh full notes and session history. |
| Queue | Conversation HTTP/SSE contract | Two user inputs and a due reminder become non-overlapping FIFO turns. |
| Scheduler | Scanner API with injected clock/subscriber state | A 15:00 note queues once; no subscriber writes one skip event. |
| Desktop | Persistent conversation SSE stream | A proactive turn renders as a separate Momo turn while input remains usable. |
| Failure | HTTP/SSE and audit public outputs | A bad note/provider failure is safe and the next scan continues. |

Focused tests use `uv run pytest`; live Gemini is not a default test. Manual
Windows acceptance after automated tests must prove persistent SSE, an idle
15:00 proactive turn, post-answer queued delivery, fresh reading after a direct
Markdown edit, and scheduler shutdown.

## Implementation sequence after approval

1. Red/green `NoteStore` persistence and parser behavior.
2. Red/green typed note/time Tools.
3. Red/green serial conversation queue, explicit history, and turn SSE events.
4. Red/green persistent desktop conversation subscription and turn rendering.
5. Red/green injected-clock scheduler and audit outcomes.
6. Focused tests after every slice, then manual Windows acceptance.
