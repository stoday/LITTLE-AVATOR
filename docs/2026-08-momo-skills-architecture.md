# Momo Skills Architecture

## Status

Approved MVP design, 2026-08-31.

## Goal

Move note business logic from the application package into a runtime-loadable
Akasha Skill. Future Momo capabilities use the same `skills/<name>/` shape.

## Skill discovery and lifecycle

- Momo scans direct children of `skills/` (or `LITTLE_AVATAR_SKILLS_DIR`).
- Each candidate must contain a valid `SKILL.md`; its metadata is supplied to
  the Agent at construction time through `skills=[...]`.
- Akasha loads a Skill's instructions, resources, and scripts only after the
  Agent calls `load_skill`.
- Development fails fast on an invalid Skill. With
  `LITTLE_AVATAR_ENV=production`, invalid optional Skills are skipped and a
  safe server-side warning is logged.

## Public runtime contract

Skills that provide background services expose
`scripts/runtime.py:create_runtime(context)`. The generic host supplies a
`SkillRuntimeContext` containing the data directory and, when relevant, the
conversation and user-turn IDs. Skill code owns storage, validation, and its
business rules; the application only discovers and loads the public runtime.

## momo-notes MVP

`skills/momo-notes/` owns the SQLite schema, note rendering, reminder parsing
and scanning, activity records, and a command-line script for Agent work.
The existing `data/momo-notes.db` table remains compatible. The Skill supports
create, update, keyword search, reminder-kind filtering, daily reminders, and
one-time reminders.

Deletion is staged. A deletion request records the issuing turn and may only
be confirmed from a later user turn. The turn ID comes from Momo's trusted
runtime prompt. This is a product rule for version-controlled trusted Skills,
not a sandbox against malicious third-party Skill code.

## Migration and verification

Remove `notes.py`, `note_tools.py`, and their compatibility shims. The reminder
scheduler uses the runtime contract. Tests live beside the Skill plus host/API
tests, and validate discovery, metadata loading, legacy data compatibility,
reminder delivery, staged deletion, and `akasha.agents(..., skills=[...])`.
