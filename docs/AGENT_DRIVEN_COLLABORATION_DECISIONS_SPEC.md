# Agent 驅動的協商後續決策規格

## Problem Statement

目前普通聊天視窗以固定確認詞、直接 confirmation API 與預設聯絡人捷徑處理部分協商流程。這會把自然語言意圖錯誤地縮減成 UI 規則，造成「確定！」等合理回覆落入不相關的模型錯誤路徑，也無法處理拒絕、調整、追問或多筆待決事項。

## Solution

所有使用者輸入一律送入本機 MOMO admin。MOMO 在每一輪可取得最小必要的本機待決協商摘要與 context 識別，依完整語句決定確認、拒絕、調整、追問或普通聊天；只有 MOMO 呼叫受控 Tool 才能變更持久化 confirmation task。UI 不根據詞表、按鈕或預設聯絡人自行決策。

## User Stories

1. 作為本機使用者，我可以用任何自然語言確認、拒絕或要求調整，而非背誦固定詞。
2. 作為本機使用者，我可以在待決協商存在時繼續普通聊天，不會被 UI 強制確認。
3. 作為本機使用者，我可以要求釐清，MOMO 應追問而非寫入確認結果。
4. 作為本機使用者，我可以同時有多個待決事項，MOMO 應根據安全摘要選擇正確事項或請求釐清。
5. 作為本機使用者，我只會看到本機 admin 的安全摘要，不會看到 peer 私密內容、prompt 或推理。
6. 作為系統，只有明確的 MOMO Tool 呼叫可以改變本機 confirmation task；模型文字本身不構成確認。
7. 作為系統，Tool 成功後即使模型漏掉 final answer，也會回覆 Tool 登記的安全結果。
8. 作為開發者，我可以新增不同 domain 的 Tool，而不需新增 UI 關鍵字或晚餐／排程分支。

## Implementation Decisions

- 待決協商以既有 `context_id` 與持久化 task 為權威；終局 local-admin report 建立或取得需要使用者決定的 task。
- 每個普通聊天 turn 都在 prompt 中附帶最小必要的待決事項清單：context、當地摘要與可用決策，不附原始 A2A transcript。
- MOMO admin 取得通用的受控 Tool，用 context ID 記錄確認或拒絕；調整或資訊不足由 agent 以自然語言處理，必要時使用既有 communicator Tool。
- ChatPanel 不解析確認詞、不直接 POST confirmation API，也不保留「預設聯絡人直接協商」的替代流程。
- confirmation task 是審計與副作用邊界，不是 UI 文案或詞彙判斷器。
- 排程是 `momo-notes` Skill 的現有 domain 能力；核心協商與 confirmation 機制不得假設晚餐、時間或可用性。

## Testing Decisions

- API/SSE seam：待決事項會進入 MOMO prompt；agent 呼叫確認 Tool 後產生安全 answer 與 completed；空 final answer 仍會使用 Tool 回覆。
- ChatPanel seam：任意文字（含「確定！」）都送 ordinary conversation client，不會被字串判斷或直接 confirmation client 攔截。
- 持久化 seam：Tool 只變更指定 context 的 task；不相符或不明確的 context 不會寫入。
- 既有 API 與 PySide6 focused tests 是 prior art；使用 deterministic fake agents，不以 live Gemini 文案當作測試證據。

## Out of Scope

- 將目前排程 Skill 改寫成通用業務引擎。
- 自動將本機確認傳送給 peer 或執行外部副作用；這仍需各 domain Skill 明確定義。
- 實際 LAN、部署或 live-model 成功宣稱。

## Further Notes

舊的晚餐流程文件是歷史範例，不是核心決策規格；本規格優先。issue tracker 未在此工作區設定，因此依使用者要求將此文件保存於 `docs`。
