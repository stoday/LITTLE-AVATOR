---
name: momo-notes
description: 當使用者要求儲存、查找、更新、排程或刪除筆記時，管理 Momo 的本機持久筆記與提醒。
---

處理筆記或提醒前，先載入此 Skill。透過 `python_execute` 執行
`scripts/note_cli.py`；它只會操作 Momo 已設定的本機資料。

進行私密的行程協商時，提出時間前先執行 `read-schedule`。它只會讀取此
Avatar 的本機 `schedule.md`；只揭露本次協商所需的特定可用時段。不得用
`read_skill_resource` 讀取 `schedule.md`：它是本機 Avatar 資料，不是內附的
Skill 資源。改以 `python_execute` 執行 `scripts/note_cli.py`，並傳入
`args=[read-schedule]`。

- 更新或刪除指涉不明的筆記前，先執行 `list` 或 `search`。
- 提醒僅支援每日 `HH:MM`，或帶時區的單次 ISO 日期時間。
- 刪除時先執行 `request-delete`，向使用者說明筆記後，等待後續回合的明確
  確認。只有取得受信任 runtime context 中的後續 turn ID，才能執行
  `confirm-delete`。
- 建立提醒 payload 時，讀取 `resources/reminder-contract.md`。
