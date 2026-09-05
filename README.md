# Little Avatar

[繁體中文](#專案簡介) | [English](#overview)

### 專案簡介

Little Avatar 是 Windows 桌面小助手 MVP。Momo 使用 PySide6，呈現透明、無框、置頂且可拖曳的桌面角色；本機 FastAPI 後端負責互動事件、Akasha Agent 對話，以及 Markdown 筆記與提醒。

Python 發行套件名稱仍為 `p2026-little-avator`；桌面啟動指令為 `little-avatar`，後端啟動指令為 `little-avatar-server`。

### 目前功能

- Momo 提供 `idle`、`greeting`、`thinking`、`happy`、`sleeping`、`drag`、`drop` 動畫。
- 視窗可拖曳，聊天面板會跟隨 Momo；點擊 Momo 可開啟多輪文字聊天。
- 聊天支援逐段回答、thinking 指示、錯誤後重試與獨立關閉。
- 氣泡操作包括「給建議」、「逗我」、「聊天」、「安靜 1 小時」與「關閉 Momo」；右鍵目前只有關閉。
- 桌面端以 REST 送命令、以 SSE 接收全域互動事件；聊天使用獨立的 conversation REST/SSE 連線。全域 SSE 會遞增重試並顯示連線狀態。
- Agent 預設使用繁體中文並跟隨使用者語言；thinking、tool、verbose trace 與 provider 錯誤細節只留在後端。
- Agent 工具可建立、修改、刪除 Markdown 筆記；提醒支援每日 `HH:MM` 與一次性 ISO 日期時間。後端每 60 秒掃描並把到期提醒排入同一個 conversation。
- Conversation 狀態只存在單一本機程序；重啟 Momo 會建立新 conversation，但 Markdown 筆記和活動紀錄會保留。

### 系統需求

- Windows
- Python 3.11 或 3.12（`pyproject.toml` 限制 `>=3.11,<3.13`）
- [uv](https://docs.astral.sh/uv/)
- Akasha provider 設定；Agent 對話需要 `MODEL` 與相應 credential

### 快速開始

在專案根目錄執行：

```powershell
uv sync
```

方式一：在兩個終端機啟動後端與桌面端。

```powershell
# 終端機 1
uv run little-avatar-server
```

```powershell
# 終端機 2
uv run little-avatar
```

方式二：使用單一 console 啟動器。它會檢查 `.venv`、確認 8765 沒有舊 API、等待 `/health` 成功後啟動桌面端；關閉 Momo 或按 `Ctrl+C` 會停止它啟動的程序。

```powershell
.\startup.bat
```

在 Bash（例如 Linux、macOS、WSL 或 Git Bash）可使用相同的單一 Avatar 啟動器：

```bash
./startup.sh
```

方式三：在同一台電腦啟動兩個可彼此進行 A2A 討論的 Momo。這個啟動器會為兩個
Avatar 使用不同的 port、資料目錄與 A2A 資料庫，並開啟兩個桌面視窗：

```powershell
.\scripts\start-dual-avatar.ps1 -PortA 18765 -PortB 18766 -NameA "小王" -NameB "小美"
```

關閉兩個 Momo 視窗或在 PowerShell 按 `Ctrl+C` 可停止它們。這是同一台電腦上的
跨 process 測試；實體 LAN、mDNS、TLS 與裝置信任尚未包含在此啟動方式中。操作細節請見
[雙 Avatar 本機測試說明](docs/DUAL_AVATAR_LOCAL_TEST.md)。

在 Bash 使用雙 Avatar 啟動器時，指令與可選參數如下：

```bash
./start-dual-avator.sh --port-a 18765 --port-b 18766 --name-a "小王" --name-b "小美"
```

### 設定

在根目錄建立 `.env`（不要提交）：

```dotenv
MODEL=gemini:gemini-3.7-flash
GEMINI_API_KEY=your-provider-key
```

| 變數 | 預設值 | 用途 |
| --- | --- | --- |
| `MODEL` | 無（Agent 對話必填） | Akasha 模型別名。 |
| `GEMINI_API_KEY` | 無 | Gemini credential，僅後端使用。 |
| `LITTLE_AVATAR_API_URL` | `http://127.0.0.1:8765` | 桌面端 API 根網址。 |
| `LITTLE_AVATAR_DATA_DIR` | `data` | 筆記與活動紀錄目錄。 |
| `LITTLE_AVATAR_LOG_DIR` | `logs` | Akasha 本機診斷 log 目錄。 |
| `MOMO_TIMEZONE` | Windows 本機時區 | 提醒排程時區，可填 IANA 名稱。 |

### API

後端預設只綁定 `127.0.0.1:8765`：

| 方法 | 路徑 | 用途 |
| --- | --- | --- |
| `GET` | `/health` | 健康檢查，回傳 `{"status":"ok"}`。 |
| `GET` | `/api/settings` | 回傳 `cooldown_seconds`（目前 900）與 SSE 狀態。 |
| `POST` | `/api/interactions` | 接收 `ask_suggestion`、`tease`、`dismiss`、`mute`。 |
| `GET` | `/api/events` | 全域互動 SSE，傳送 `suggestion`、`avatar_state`、heartbeat。 |
| `POST` | `/api/conversations` | 建立 conversation。 |
| `POST` | `/api/conversations/{conversation_id}/messages` | 提交文字訊息，成功回傳 `202`。 |
| `GET` | `/api/conversations/{conversation_id}/events` | Conversation SSE，傳送 `turn_started`、`answer`、`completed`、`error`。 |

聊天訊息依 FIFO 處理；進行中的 Agent 回合不會被中斷。SSE 事件含 ID、類型、JSON data 與 heartbeat。

### 持久化資料與測試

- `data/momo-notes.md`：可直接編輯的 Markdown 筆記來源，每則筆記有 UUID 與提醒 metadata。
- `data/momo-activity.jsonl`：append-only 活動紀錄。
- `logs/`：本機診斷 log；保存 Agent log 時清理超過七天的 JSON。

```powershell
uv run pytest
```

測試涵蓋 REST/SSE、conversation 排程、筆記提醒、動畫狀態、資產解析、聊天面板定位與重連。透明度、置頂、高 DPI 與實機啟動仍需手動驗收。提醒若到期時沒有桌面 SSE 訂閱者，會記錄為略過而不補發。

### 安全與範圍

後端只監聽 `127.0.0.1`。API key、模型設定、Agent thinking/tool trace 與 stack trace 不會回傳給桌面端。附件、文件上傳、檔案瀏覽、帳號、多使用者路由及跨重啟 conversation 歷史不在本 MVP 內。

### Overview

Little Avatar is a Windows desktop companion MVP. Momo is a transparent, frameless, always-on-top, draggable PySide6 character. A local FastAPI backend handles interaction events, Akasha Agent conversations, and Markdown-backed notes and reminders.

The Python distribution remains `p2026-little-avator`; the desktop command is `little-avatar`, and the backend command is `little-avatar-server`.

### Current capabilities

- Momo has `idle`, `greeting`, `thinking`, `happy`, `sleeping`, `drag`, and `drop` animation states.
- The window is draggable; the chat panel follows Momo. Clicking Momo opens multi-turn text chat.
- Chat supports incremental answers, a thinking indicator, retry after failure, and an independent close control.
- The bubble offers “ask for a suggestion”, “tease”, “chat”, “mute for one hour”, and “close Momo”. Right-click currently offers only close.
- The desktop sends commands over REST and receives global interaction events over SSE. Chat uses a separate conversation REST/SSE connection. The global SSE listener retries with increasing delays and shows connection status.
- The Agent defaults to Traditional Chinese and follows the user’s language. Thinking, tool, verbose-trace, and provider-error details stay on the backend.
- Agent tools create, update, and delete Markdown notes. Reminders support daily `HH:MM` times and one-time ISO date-times. The backend scans every 60 seconds and queues due reminders in the same conversation.
- Conversation state is in-process and single-user. Restarting Momo creates a new conversation; Markdown notes and activity logs remain on disk.

### Requirements

- Windows
- Python 3.11 or 3.12 (`pyproject.toml` requires `>=3.11,<3.13`)
- [uv](https://docs.astral.sh/uv/)
- Akasha provider configuration; Agent chat requires `MODEL` and the matching credential

### Quick start

From the project root:

```powershell
uv sync
```

Option 1: use two terminals.

```powershell
# Terminal 1
uv run little-avatar-server
```

```powershell
# Terminal 2
uv run little-avatar
```

Option 2: use the Windows single-console launcher. It checks `.venv`, verifies that port 8765 has no old API, waits for `/health`, and starts the desktop client. Closing Momo or pressing `Ctrl+C` stops the processes it started.

```powershell
.\startup.bat
```

For Bash environments (Linux, macOS, WSL, or Git Bash), use the equivalent
single-Avatar launcher:

```bash
./startup.sh
```

Option 3: launch two Momos on the same computer for a local A2A discussion. The
launcher assigns separate ports, data directories, and A2A databases, then opens
two desktop windows:

```powershell
.\scripts\start-dual-avatar.ps1 -PortA 18765 -PortB 18766 -NameA "Alice" -NameB "Xiaomei"
```

Close both Momo windows or press `Ctrl+C` in PowerShell to stop them. This is a
same-computer, cross-process test; physical-LAN, mDNS, TLS, and device-trust
validation are not included. See the [dual-Avatar local-test guide](docs/DUAL_AVATAR_LOCAL_TEST.md)
for details.

For Bash, use the dual-Avatar launcher (the filename intentionally follows this
project's `avator` spelling):

```bash
./start-dual-avator.sh --port-a 18765 --port-b 18766 --name-a "Alice" --name-b "Xiaomei"
```

### Configuration

Create `.env` in the project root (do not commit it):

```dotenv
MODEL=gemini:gemini-3.7-flash
GEMINI_API_KEY=your-provider-key
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `MODEL` | None (required for Agent chat) | Akasha model alias. |
| `GEMINI_API_KEY` | None | Gemini credential, used only by the backend. |
| `LITTLE_AVATAR_API_URL` | `http://127.0.0.1:8765` | Desktop API base URL. |
| `LITTLE_AVATAR_DATA_DIR` | `data` | Notes and activity-log directory. |
| `LITTLE_AVATAR_LOG_DIR` | `logs` | Local Akasha diagnostic-log directory. |
| `MOMO_TIMEZONE` | Windows local timezone | Reminder timezone; accepts an IANA name. |

### API

The backend binds to `127.0.0.1:8765` by default:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Health check; returns `{"status":"ok"}`. |
| `GET` | `/api/settings` | Returns `cooldown_seconds` (currently 900) and SSE support. |
| `POST` | `/api/interactions` | Accepts `ask_suggestion`, `tease`, `dismiss`, and `mute`. |
| `GET` | `/api/events` | Global interaction SSE with `suggestion`, `avatar_state`, and heartbeat events. |
| `POST` | `/api/conversations` | Creates a conversation. |
| `POST` | `/api/conversations/{conversation_id}/messages` | Submits a text message; returns `202` when accepted. |
| `GET` | `/api/conversations/{conversation_id}/events` | Conversation SSE with `turn_started`, `answer`, `completed`, or `error`. |

Chat messages use a FIFO queue; an in-flight Agent turn is not interrupted. SSE events include an ID, type, JSON data, and heartbeats.

### Persistent data and tests

- `data/momo-notes.md`: human-readable, directly editable Markdown source; each note has a UUID and reminder metadata.
- `data/momo-activity.jsonl`: append-only activity log.
- `logs/`: local diagnostic logs; JSON logs older than seven days are cleaned when Agent logs are saved.

```powershell
uv run pytest
```

Tests cover the REST/SSE contract, conversation scheduling, notes and reminders, animation state, asset decoding, chat-panel placement, and reconnect behavior. Native Windows transparency, always-on-top behavior, high-DPI rendering, and real startup still require manual acceptance. A reminder due without a desktop SSE subscriber is recorded as skipped rather than delivered after restart.

### Security and scope

The backend listens only on `127.0.0.1`. API keys, model configuration, Agent thinking/tool traces, and stack traces are not returned to the desktop client. Attachments, document upload, file browsing, accounts, multi-user routing, and cross-restart conversation history are outside this MVP.
