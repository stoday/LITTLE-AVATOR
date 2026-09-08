---
name: dtri-meeting-room
description: 操作數位轉型研究院（數轉院）的內部會議室 CLI，進行登入、可用時段查詢與已明確授權的預約。使用者要透過此專案查詢或預約數轉院會議室時使用。
---

# 數位轉型研究院（數轉院）會議室

透過基礎 Tool `run_command` 執行已安裝的 `dtri-meeting-room`：將
`executable` 設為 `dtri-meeting-room`，並把 CLI 參數逐項放入
`arguments`。不得把整條命令放在單一字串內。

## 可用時段與登入

- `view` 顯示的是**可借時段**，不是已預約時段。需要最新網站資料時，使用 `view --refresh`。
- 使用者詢問「今天」、「目前」、「現在」或「還有」哪些時段時，依受信任的
  runtime 日期執行 `view --refresh --date YYYY-MM-DD`。CLI 會列出整天資料；其中
  開始時間早於 runtime 當地時間的時段必須排除，不得回報為「還有空」。只能回報
  CLI 成功輸出的資料。
- `login` 會開啟此專案獨立的 Playwright 設定檔，登入必須由使用者手動完成。
- 不得檢視、輸出、匯出或提交瀏覽器 cookie、工作階段、token、密碼或 ASP.NET 隱藏欄位。設定檔位於 `.dtri-meeting-room/profile/`，且刻意設為 Git 忽略。

若使用者同時要求把查詢結果記起來，必須先完成本 Skill 的查詢並取得成功輸出，
下一個模型回合再載入 `momo-notes`，使用其 `create` 指令保存日期、snapshot 時間與
所有仍可借的會議室時段；只保存過濾後仍可借的時段。不得在同一個模型回合平行呼叫
兩個 `load_skill`；查詢失敗時也不得建立內容不完整的筆記。

## 預約

- `run_command` 是單次單向呼叫；預約時一律使用非互動命令，絕不可使用未附 `--confirm YES` 的 `reserve`。
- 必須取得使用者明確的預約指示，以及 room ID、`YYYY-MM-DD` 日期與 `HH:MM-HH:MM` 時段；不得自行推定任一值。會議事由不是必要輸入，省略時使用預設值。
- 未提供會議內容時，使用：`reserve <room-id> <YYYY-MM-DD> <HH:MM-HH:MM> --confirm YES`。CLI 會以「工作進度討論」作為事由，且不得再要求使用者輸入任何內容。
- 使用者已提供會議內容時，使用：`reserve <room-id> <YYYY-MM-DD> <HH:MM-HH:MM> --confirm YES --reason <會議內容>`。將每個參數分開放入 `arguments`，不加入 shell 引號。
- CLI 仍會在送出前重新檢查目標時段；不可自動重試失敗的寫入操作。
- 伺服器回應中的 `Borrowed` 結果表代表預約成功。若無法辨識回應，應將結果視為未確定，並請使用者在內網系統確認。

## 範圍

`cancel` 尚未實作。不得宣稱已取消預約，也不得虛構取消流程。
