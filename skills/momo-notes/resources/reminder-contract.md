# Reminder contract

- Daily: `{"kind":"daily","time":"HH:MM"}`.
- One-time: `{"kind":"once","due_at":"YYYY-MM-DDTHH:MM:SS+08:00"}`.
- Daily times use Momo's local timezone. One-time reminders must include an
  explicit offset.
