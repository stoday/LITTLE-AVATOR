# Little Avatar MVP PRD

## Problem Statement

Windows 使用者想要一個常駐桌面的復古 Office 助手風格小角色：它能以動畫與對話泡泡呈現，讓使用者主動逗弄或要求建議，也能在合適時機主動送出建議。建議的內容與時機屬於後端服務的責任；桌面程式必須可靠地接收、呈現並回報使用者互動，而不打斷日常工作。

目前沒有可重用的桌面 UI、事件協定或後端服務契約。若直接把 LLM、情境蒐集、動畫和系統通知一起實作，將難以驗證哪些部分真正改善互動體驗，也無法控制主動打擾的頻率。

## Solution

提供 Windows 桌面小角色 MVP。角色以透明、無框、可拖曳、置頂的小型視窗呈現，包含有限的待機與互動動畫，以及可關閉的文字泡泡。

桌面端以 REST API 送出使用者動作並讀取設定；透過一條可自動重連的 SSE 連線接收後端事件。後端決定是否與何時提出建議，桌面端只根據事件顯示建議或切換角色狀態。MVP 以規則或固定測試事件即可運作，不要求 LLM 或作業系統層級的使用者行為蒐集。

## User Stories

1. As a Windows 使用者, I want to see a small desktop character after launching the app, so that I can tell the assistant is available.
2. As a Windows 使用者, I want the character to stay above ordinary application windows without blocking my work, so that it feels present but unobtrusive.
3. As a Windows 使用者, I want to drag the character to a preferred screen position, so that it does not cover important content.
4. As a Windows 使用者, I want the character to show a quiet idle state when no interaction is occurring, so that it does not consume my attention.
5. As a Windows 使用者, I want to click the character to open a compact interaction menu, so that I can discover available actions.
6. As a Windows 使用者, I want to ask for a suggestion on demand, so that I remain in control of when I receive help.
7. As a Windows 使用者, I want to choose a playful interaction such as greeting or teasing the character, so that the product has personality rather than being only a notification surface.
8. As a Windows 使用者, I want to see the result of my interaction as animation and a text bubble, so that the response feels immediate and understandable.
9. As a Windows 使用者, I want backend-originated suggestions to arrive without repeatedly polling, so that the desktop client can react promptly and efficiently.
10. As a Windows 使用者, I want to dismiss an individual suggestion, so that I can continue my current task.
11. As a Windows 使用者, I want to temporarily mute proactive suggestions, so that I can focus without closing the application.
12. As a Windows 使用者, I want the client to make a best-effort reconnection after a network interruption, so that a transient outage does not permanently disable the assistant.
13. As a Windows 使用者, I want the client to remain usable when the backend is offline, so that I can still move, open, and close the character without confusing errors.
14. As a backend operator, I want user actions to be received as explicit events, so that recommendation logic can learn or apply rules without coupling to desktop rendering.
15. As a backend operator, I want each pushed event to have an ID and a typed payload, so that reconnecting clients can avoid accidental duplicate presentation.
16. As a product owner, I want proactive suggestions to respect a cooldown and client mute state, so that the assistant is helpful rather than annoying.
17. As a developer, I want a mockable API boundary, so that desktop behavior can be tested without a live recommendation engine.

## Implementation Decisions

- The MVP targets Windows only and uses Python 3.11+ with PySide6 for the native desktop UI. The desktop process owns window placement, animation state, menu actions, bubble presentation, SSE connection management, and local user preferences.
- The visual identity is an original retro productivity-assistant character. It must not copy Microsoft Office Assistant/Clippy names, artwork, sounds, or animation assets.
- The initial visual state set is deliberately small: `idle`, `greeting`, `thinking`, `happy`, and `sleeping`. Assets may initially be static images, GIFs, or Lottie animations behind one animation interface; advanced rigging is not an MVP requirement.
- The character window is frameless, transparent, always-on-top, draggable, and small enough to coexist with other applications. It must offer a visible way to close or hide itself; click-through behavior is deferred.
- REST carries client-to-server commands. The MVP command categories are: request a suggestion, record a named playful interaction, dismiss a suggestion, update temporary mute state, and retrieve effective settings.
- SSE carries server-to-client events over one long-lived HTTP connection. The MVP event types are `suggestion`, `avatar_state`, `error`, and `heartbeat`. SSE payloads are JSON; actionable events have stable event IDs and the client sends `Last-Event-ID` on reconnect when available.
- A `suggestion` event includes an ID, display text, optional title, optional action label, priority, and expiry. An `avatar_state` event contains a supported animation state plus an optional duration. Unknown event types or unsupported animation states are ignored safely and recorded for diagnostics.
- The desktop client places SSE reading outside the UI thread and marshals decoded events back to the UI event loop. It reconnects with bounded exponential backoff, resets the delay after a successful connection, and surfaces backend connectivity only in a non-intrusive status state.
- The MVP backend can be a FastAPI service. It owns suggestion generation, event persistence/replay policy, per-user cooldown, and deciding whether an event should be pushed. A deterministic mock mode is required before any LLM integration.
- A suggestion appears in a bubble only when the client is not muted and it has not already displayed the same event ID. The user can dismiss it immediately. Client mute is enforced locally for immediate UX and supplied to the server so it can avoid needless pushes.
- Configuration required for the MVP is API base URL, SSE endpoint, device/client identifier, and the temporary mute expiry. Secrets must not be embedded in the desktop package or event payloads.
- The single highest behavioral seam is the desktop-facing backend client interface: it exposes command submission, settings retrieval, connection lifecycle, and typed inbound events. The UI is tested against a fake implementation of this interface; the FastAPI API is tested against the same public contracts.

## Testing Decisions

- A good test observes visible client behavior or the public HTTP/SSE contract. It must not assert private widget fields, implementation-specific timers, thread objects, or a particular HTTP library.
- The desktop-facing backend client is tested with controlled REST responses and a finite SSE stream. Tests cover JSON decoding, unknown events, malformed payload handling, event-ID deduplication, reconnect backoff, and correct `Last-Event-ID` propagation.
- The UI controller/presenter is tested against a fake backend client. Tests cover on-demand suggestion requests, rendering a supported avatar state, presentation and dismissal of a suggestion, local mute behavior, offline behavior, and the guarantee that inbound events do not freeze the UI loop.
- The FastAPI service is tested at its public REST and SSE endpoints. Tests cover typed event serialization, heartbeat delivery, reconnect replay policy, cooldown/mute suppression, and rejection of invalid command payloads.
- A manual Windows acceptance pass verifies transparent rendering, always-on-top behavior, dragging, high-DPI scaling, bubble dismissal, and that reconnecting does not cause duplicate visible suggestions. Automated tests alone do not establish these native-window properties.
- No existing test suite provides relevant prior art; the first tests establish the public API and desktop-client seams described above.

## Out of Scope

- Copying or recreating Microsoft Office Assistant assets or branding.
- LLM-generated advice, autonomous task execution, browser automation, screen capture, global keyboard logging, or reading local documents.
- Per-user accounts, authentication design, cloud deployment, analytics, billing, or multi-device synchronization.
- Full accessibility and localization coverage beyond using text that can be localized later.
- Complex character rigging, voice input/output, games, plugin support, click-through mode, multi-monitor persistence guarantees, and system-tray-first operation.
- WebSocket support. SSE plus REST is the deliberate MVP transport choice.

## Further Notes

- The SSE/REST separation is intentional: the server pushes information and state, while the client sends explicit actions through ordinary HTTP commands. This keeps the first version simple while allowing future bidirectional features to reconsider WebSockets only if needed.
- Product success for the MVP is not the sophistication of advice. It is a trustworthy, responsive character that users can control, that never traps them under unwanted notifications, and that continues behaving sensibly when the API is unavailable.
- Before implementation, confirm that the desktop-facing backend client interface is the desired single testing seam. It is the point at which a mock backend can exercise all MVP UI flows without a live service.
