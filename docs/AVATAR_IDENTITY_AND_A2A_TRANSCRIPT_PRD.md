# Avatar 身份命名與 A2A 對話紀錄 PRD

## 1. 目的

雙 Avatar 的協商必須讓 MOMO、兩位使用者與兩位秘書的名稱一致且可理解。使用者不應在結果視窗中看見 `agent-x-communicator`、`Local communicator` 或 `Peer communicator` 等內部名稱；協商 agent 也不得因缺少本機或對方身份資訊而用「對方使用者」等泛稱。

本 PRD 定義身份資料的來源、可信邊界、持久化快照與逐字稿 API。它是後續實作的依據，不代表本文件完成後已通過 live model、LAN 或部署驗證。

## 2. 目標與非目標

### 目標

- 定義三層固定名稱：產品人格 `MOMO`、擁有者名稱、對外協商身份 `<擁有者>的秘書`。
- 使一般 MOMO、local admin、outbound communicator 與 inbound communicator 都能取得完成職責所需的身份資料。
- 將名稱快照與 `context_id` 一起保存，保證舊協商在改名後仍以當時身份顯示。
- 以角色資料而非可見文字重建 communicator 的歷史訊息；UI 仍只渲染安全的 speaker/text。
- 維持一個「結論在前、雙方 communicator 對話在後」的終態結果視窗。

### 非目標

- 不改變正式 A2A Message 的 wire payload，也不將使用者姓名、行程、普通聊天或 prompt 傳給 peer。
- 不合併 local admin 與 communicator；兩者的私有上下文和職責仍分離。
- 不把 loopback 測試當成 LAN 或已部署驗證，亦不新增 mDNS、裝置信任或傳輸安全機制。
- 不要求模型逐字套用單一中文模板；要求是身份與協商語意正確、自然且可追溯。

## 3. 名詞與名稱規則

| 名詞 | 範例 | 用途 |
| --- | --- | --- |
| 產品人格 | `MOMO` | 使用者直接聊天時的產品角色。 |
| 擁有者名稱 | `小王`、`小美` | 該本機 Avatar 所服務的使用者。 |
| communicator 名稱 | `小王的秘書`、`小美的秘書` | A2A 協商發言者與結果逐字稿的可見名稱。 |
| 內部 agent ID | `agent-x-communicator` | 僅供程式路由、驗證與診斷；不得顯示在一般 UI 或模型對使用者／peer 的訊息中。 |

`start-dual-avatar.ps1` 的 `-NameA` 與 `-NameB` 是擁有者名稱。啟動器必須由此唯一來源衍生各 instance 的主 agent 顯示名稱與 communicator 名稱；不新增可獨立設定、可能與擁有者失配的秘書名稱參數。

一般聊天的 MOMO 可自稱「我是 MOMO，<擁有者>的秘書」。A2A 結果與逐字稿只使用 communicator 名稱，不混用產品人格或內部 ID。

## 4. 身份資料流與公開介面

### 4.1 本機設定

每個 backend 在啟動時取得下列衍生設定：

- `LITTLE_AVATAR_OWNER_NAME`：本機擁有者名稱。
- `LITTLE_AVATAR_COMMUNICATOR_NAME`：由擁有者名稱衍生的 `<owner>的秘書`。
- `LITTLE_AVATAR_A2A_PEER_IDENTITIES`：僅限本機信任 peer 的 mapping；以 peer agent ID 對應其 `owner_name` 與 `communicator_name`。

既有 contact directory 仍負責由使用者輸入的聯絡人名稱解析 peer agent ID。peer 身份也必須由本機此一受信任 mapping 解析，不能從未驗證的對方 A2A 文字或 payload 取得。

單 Avatar／舊啟動路徑未提供擁有者名稱時，安全退回為產品人格 `MOMO`；不得捏造使用者姓名。這類情況不應產生帶有人名的雙 Avatar 協商逐字稿。

### 4.2 Agent prompt 契約

- 一般 MOMO 與 local admin prompt 都收到本機產品人格、擁有者名稱和 communicator 名稱；local admin 仍只對本機使用者報告。
- outbound communicator prompt 收到本機身份、受信任對方身份、委派請求、目前逐字稿及其本機可用的 Skill；不收到對方私有資料。
- inbound communicator 以已驗證的 `peer_agent_id` 查詢本機 peer identity mapping，收到雙方身份、peer 訊息、逐字稿和本機資訊；不可使用固定的「對方使用者」。
- 第一則主動邀約必須自我介紹為 `<本機>的秘書`，點名 `<對方>的秘書`，並清楚詢問 `<對方擁有者>` 的可用性。後續訊息需明確說明哪位擁有者是否方便。暫定或終態回覆必須指出將向哪位本機擁有者回報／請求最終確認。

### 4.3 逐字稿與結果 API

`GET /api/collaborations/{context_id}/transcript` 的目標回應是 envelope：

```json
{
  "local_communicator_name": "小王的秘書",
  "peer_communicator_name": "小美的秘書",
  "entries": [
    {"role": "local", "speaker": "小王的秘書", "text": "..."},
    {"role": "peer", "speaker": "小美的秘書", "text": "..."}
  ]
}
```

`role` 的值為 `local` 或 `peer`，只供 API consumer 與 agent history 還原發言方向；不在 UI 顯示。`speaker` 與 `text` 是 UI 可呈現的資料。實作必須保留原有交換的方向資料，不能再以 `speaker == "Local communicator"` 判斷角色。

結果視窗標題為「`<本機 communicator> 與 <對方 communicator> 的對話紀錄`」。它先顯示既有的本機 admin 結論，再顯示 envelope 的 `entries`；普通聊天仍不重複呈現該逐字稿。

## 5. 快照、相容性與隱私

建立協商 task 時，持久化本機／peer 的 `owner_name` 與 `communicator_name` 快照，並讓其隨 task、exchange 與結果 API 使用。後續修改啟動名稱或 mapping 不得回寫既有 context 的可見身份。

既有資料庫紀錄沒有身份快照時，API 要以安全泛稱提供可讀的逐字稿，並帶出明確 `role`；不得宣稱舊紀錄代表某位特定使用者。新 API 可在一個相容期間接受舊 list-shaped transcript consumer，或同步更新唯一 desktop consumer；完成遷移後所有內部 consumer 均使用 envelope。此相容處理不得導致舊紀錄的 assistant/user 角色反轉。

保存與顯示的內容僅限已送出的 communicator 訊息、快照姓名與終態所需資料。不得寫入或回傳 system prompt、推理、憑證、未送出的本機上下文、完整排程或普通聊天內容。私有 `[[A2A_STATE:...]]` marker 在送出與持久化前一律剝除。

## 6. 驗收與測試

### Focused automated tests

- 雙 Avatar 以小王／小美設定時，雙方 communicator prompt 都取得正確的本機與 peer 身份；一般 MOMO／local admin 也知道自己服務的擁有者。
- outbound 與 inbound 協商都可形成角色正確的 `{role, speaker, text}` 順序，且 peer agent ID 經本機可信 mapping 解析。
- 首次邀約、反提案與最終暫定確認的訊息包含正確的使用者與秘書身份；測試斷言必要語意，不鎖死模型的完整逐字措辭。
- 改名後，新 context 使用新名稱，舊 context 仍以建立時快照顯示。
- 舊資料庫 context 能安全顯示且不反轉角色；內部 ID 不出現在結果視窗、一般聊天或可見逐字稿。
- 結果視窗顯示「小王的秘書 與 小美的秘書 的對話紀錄」、結論優先、僅呈現 `speaker`／`text`，並維持 Close-only 行為。
- 隱私回歸測試確認 transcript 與 API 不含 prompt、credentials、reasoning、完整 schedule、普通聊天或 A2A state marker。

### 驗證聲明邊界

Focused tests 證明 API、資料保存與 UI 契約；雙 backend loopback 測試僅證明本機跨程序整合。只有經過真實兩機、可信傳輸與網路失敗情境的驗證後，才可聲稱 LAN 整合成功；部署驗證另需其自身的執行環境證據。

## 7. 實作前審閱關卡

本文件完成後必須先由產品／使用者審閱並明確確認，才可修改 launcher、backend、資料庫、API、desktop UI 或測試。審閱通過前，本 PRD 是唯一預期變更。
