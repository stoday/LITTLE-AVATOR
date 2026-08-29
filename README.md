# Little Avatar

Windows 桌面小助手 MVP：原創角色 Momo、PySide6 透明置頂視窗、互動泡泡，以及 REST + SSE 後端事件。

目前支援 Python 3.11 或 3.12；Akasha light 依賴尚不支援本專案的 Python 3.13 解析範圍。

## 執行

先在兩個終端機分別執行：

```powershell
uv sync
uv run little-avatar-server
```

```powershell
uv run p2026-little-avator
```

在 Windows 也可以直接雙擊或於 PowerShell 執行：

```powershell
.\startup.bat
```

它會同步相依，並由同一個 console session 管理本機 API 與 Momo；API、Uvicorn 與 Akasha 的 verbose 訊息會即時印在該 console。關閉 Momo 或在該 console 按 `Ctrl+C` 都會停止它啟動的前後端 process。若 8765 已有舊 API 執行，啟動器會停止並要求先關閉舊服務，避免誤殺不屬於本次啟動的 process。

桌面角色可拖曳；左鍵點擊 Momo 會開啟聊天面板，右鍵可開啟「給建議」、「逗我」、「安靜 1 小時」與關閉選單。未啟動後端時，角色仍可開啟與拖曳，但聊天只會顯示友善的離線回應。

點擊 Momo 會開啟聊天面板。聊天後端使用 `.env` 的 `MODEL` 與 provider key；例如 `MODEL="gemini:gemini-2.5-flash"` 搭配 `GEMINI_API_KEY`。不要提交 `.env` 或 `logs/`。

要關閉桌面角色，可點角色開啟互動泡泡後選「關閉 Momo」，或在角色上按滑鼠右鍵後選「關閉 Momo」。這只會結束桌面前台；本機 mock API server 若在另一個終端機執行，請用 `Ctrl+C` 停止。

預設後端為 `http://127.0.0.1:8765`。若使用其他服務，設定 `LITTLE_AVATAR_API_URL`，並實作 `/api/interactions`、`/api/events` 與 `/api/settings` 的 MVP PRD 契約。
