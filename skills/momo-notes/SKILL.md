---
name: momo-notes
description: Manage Momo's durable local notes and reminders when the user asks to save, find, update, schedule, or delete a note.
---

Load this Skill before handling a note or reminder. Use `scripts/note_cli.py`
through `python_execute`; it operates only on Momo's configured local data.

For a private scheduling discussion, run `read-schedule` before proposing a
time. It reads only this avatar's local `schedule.md`; disclose only the
specific availability needed for the discussion. Never use `read_skill_resource` to read
`schedule.md`: it is local avatar data, not a bundled Skill resource. Use
`python_execute` with `scripts/note_cli.py` and `args=[read-schedule]` instead.

- Use `list` or `search` before updating or deleting an ambiguous note.
- Reminders are only daily `HH:MM` or one-time timezone-aware ISO datetimes.
- For deletion, run `request-delete` first, explain the note to the user, then
  wait for a later explicit user confirmation. Run `confirm-delete` only with
  the later turn ID from trusted runtime context.
- Read `resources/reminder-contract.md` when constructing a reminder payload.
