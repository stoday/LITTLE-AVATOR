# Akasha Agent 對話後台工作任務

## Problem Statement

使用者已可在 Windows 桌面上看到並操作 Momo Avatar，但目前互動只會觸發固定回應或提醒。使用者希望點擊 Momo 後能開啟可捲動的多輪對話面板，並與後端的 Akasha Agent 即時聊天。

此功能必須保留 Momo 的可愛、俏皮、預設繁體中文人格，同時不把 Agent 的思考、trace 或工具細節暴露給使用者。後端需要足夠的開發期診斷資料，以利調查模型、串流或日後工具／Skill 整合問題；但 API key 與敏感設定絕不能出現在前端或版本控制中。

## Solution

在既有本機 FastAPI 服務中增加以 conversation 為單位的 Akasha Agent 對話服務。點擊 Momo 後，桌面端顯示錨定在角色旁、可捲動且可單獨關閉的聊天面板。每次 Avatar 啟動建立一個新 conversation；該 conversation 有獨立的 Agent 狀態，直到 Avatar 關閉時釋放。

聊天訊息使用 REST 提交，Agent 回覆使用每個 conversation 專屬的 SSE stream 逐段送回。前端只顯示安全的 answer chunk 與友善狀態，讓 Momo 在等待時播放 `thinking` 動畫。後端以 `MODEL` 環境變數建立 `akasha.agents()`，初版不掛任何可執行 Tools 或 Skills，但保留未來擴充位置。

## User Stories

1. As a Windows 使用者, I want to click Momo and open a chat panel, so that I can start talking to her without leaving my desktop task.
2. As a Windows 使用者, I want the chat panel to stay near Momo and be independently closable, so that I can hide conversation text without closing the Avatar.
3. As a Windows 使用者, I want to enter a plain-text message and send it to Momo, so that I can ask questions naturally.
4. As a Windows 使用者, I want Momo's answer to appear incrementally, so that I know she is responding before a long answer completes.
5. As a Windows 使用者, I want Momo to show a thinking state while the Agent is working, so that model latency has a clear visual meaning.
6. As a Windows 使用者, I want Momo to reply in Traditional Chinese by default and follow my language when I change language, so that the conversation feels natural.
7. As a Windows 使用者, I want Momo to remain playful and friendly without claiming access to files, the Internet, or desktop actions she does not have, so that I can trust her boundaries.
8. As a Windows 使用者, I want the send control disabled during an active answer, so that I do not accidentally interleave two requests in one conversation.
9. As a Windows 使用者, I want a friendly error message and retry action when the model is unavailable, so that a transient provider failure does not end the conversation.
10. As a Windows 使用者, I want a new conversation when I restart Avatar, so that the MVP does not silently retain personal chat history.
11. As a backend operator, I want each conversation to have isolated Agent state, so that concurrent requests cannot leak or corrupt messages, tool calls, or logs.
12. As a backend operator, I want to configure the model through `MODEL` and provider credentials through the environment, so that secrets are not embedded in source or sent to the desktop app.
13. As a backend operator, I want to stream only answer content to the client, so that internal thinking and trace details remain server-side.
14. As a backend operator, I want verbose, structured Akasha logs retained locally for seven days, so that provider and future Tool/Skill failures can be diagnosed.
15. As a developer, I want a stable conversation REST/SSE contract, so that the PySide6 chat panel can be tested with a fake backend and the backend can be tested without a running GUI.
16. As a future feature developer, I want the Agent to be created through a dedicated adapter, so that adding explicit Tools or Skills does not change the chat UI contract.

## Implementation Decisions

- The service remains a local FastAPI process bound to `127.0.0.1`. It is not exposed to a LAN or public network in this task.
- The existing global Avatar event stream remains responsible for avatar-wide notifications and state. Chat traffic uses a conversation-specific event stream so messages never mix with general reminders or another conversation.
- The public conversation contract creates a conversation, submits a plain-text user message, and exposes a conversation-specific SSE stream. SSE events distinguish answer chunks, completed answers, friendly failure states, and keepalive messages.
- A conversation creates and owns an Akasha `agents()` instance configured with `stream=True`, `keep_logs=True`, and `verbose=True`. The instance is never shared across simultaneous conversations or requests.
- Each Agent consumes its complete stream while it is owned by its conversation. Only answer chunks are transformed into client SSE events. Thinking, tool, trace, provider configuration, and raw diagnostic events remain backend-only.
- The initial Agent has no executable Tools and no Skills. The architecture includes an Agent adapter/factory so a future Tool or Skill can be explicitly added with its own authorization and UI status design.
- The model alias comes from the existing `MODEL` environment variable. The current expected value is `gemini:gemini-3.7-flash`; provider credentials, including `GEMINI_API_KEY`, remain environment-only and are never logged or returned by an endpoint.
- The system instruction defines Momo as a friendly, fashion-forward desktop companion: default Traditional Chinese, follows the user's language, lightly playful, non-abusive, and honest about unavailable capabilities.
- The desktop chat panel is anchored near Momo, contains a transcript, a plain-text input, send control, retry control after failure, and a close control that does not close Avatar. It has no attachments, document upload, or file browsing in this MVP.
- The client disables send while an answer is in progress. On answer completion, failure, or explicit conversation closure it restores the interaction controls and the Avatar returns from `thinking` to an appropriate idle or response state.
- Akasha verbose output and structured logs are saved only on the local backend. Logs may include development diagnostics and conversation content, must be excluded from Git, and are deleted after seven days at service startup.
- A provider failure is mapped to a safe, user-readable error and a retryable chat state. The backend log retains diagnostic detail without returning stack traces, API keys, or internal thinking to the client.
- Conversation state is in-process for this single-user MVP and ends when Avatar ends. Cross-restart persistence, account identity, and multi-worker routing are deferred.

## Testing Decisions

- The single highest behavioral seam is the conversation REST/SSE contract. Tests observe submitted messages and emitted event sequences, not internal Qt widgets, Akasha private fields, threads, or logging implementation details.
- Backend contract tests use a deterministic fake Agent stream to verify conversation creation, plain-text validation, incremental answer event ordering, completion, keepalive, failure mapping, retry, and that no thinking or tool payload reaches client SSE.
- Isolation tests establish that two conversations do not share message history, Agent state, or event streams. They also verify that an active conversation cannot accept an interleaving send until its current answer has reached a terminal event.
- Configuration tests verify a missing or invalid `MODEL` results in a friendly, retryable configuration error and that responses never include credential values.
- Logging tests use a temporary local log directory to verify verbose and structured logs are written, old logs are removed according to the seven-day policy, and the client contract omits backend trace content.
- Desktop-client tests use a fake conversation backend to verify that opening a chat panel, sending a message, rendering streamed answer chunks, showing thinking state, disabling send during work, retrying errors, and closing only the panel all produce visible user behavior.
- An opt-in live Gemini smoke test verifies provider wiring and non-empty streamed answers using the configured environment. It must not run in the default test suite because it consumes provider quota.
- Manual Windows acceptance verifies the dialogue panel is visible next to Momo, remains readable at high DPI, does not block dragging or closing Avatar, and handles a provider outage without freezing the UI.

## Out of Scope

- Tools, Skills, MCP servers, autonomous actions, file access, browser access, desktop automation, and RAG/document retrieval.
- Image, audio, document, or other message attachments.
- Conversation persistence across Avatar restarts, user accounts, cross-device sync, multi-user service operation, or deployment outside localhost.
- Displaying model thinking, raw verbose trace data, tool arguments, provider stack traces, or API keys in the desktop client.
- Production observability infrastructure, cloud log aggregation, billing, rate limiting for public users, and LAN/public authentication.
- Changing Momo's existing GIF state model except for the required `thinking`, response, and idle transitions during chat.

## Further Notes

- This task deliberately uses Akasha Agent rather than a simpler chat API to preserve the extension point for future Tools and Skills. That flexibility increases lifecycle and concurrency responsibilities, so Agent state isolation is mandatory even in a local desktop MVP.
- `keep_logs` and `verbose` are development diagnostics, not a frontend feature. Their retention policy must be revisited before any use beyond the local developer machine.
- The project has no configured issue tracker; this task document is the local planning artifact and has not been published or labelled.
