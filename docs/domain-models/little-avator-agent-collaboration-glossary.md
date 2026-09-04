# LITTLE_AVATOR Collaboration

## Agent collaboration roles

**Admin Agent (`agent-x-admin`)**:
The local user-facing agent that delegates collaboration work and receives a privacy-safe report from its own Communicator Agent. It is not an A2A peer.
_Avoid_: treating a desktop notification, database row, or remote communicator as the Admin Agent

**Communicator Agent (`agent-x-communicator`)**:
The local private representative that exchanges A2A Messages with a peer Communicator Agent. When the discussion reaches any terminal outcome, it reports that outcome to its own Admin Agent.
_Avoid_: reporting only to the initiating side or directly to the remote Admin Agent

**Terminal Discussion Outcome**:
The final local interpretation of a discussion: tentative agreement, no agreement, failure, cancellation, or safety-limit termination. Both Communicator Agents independently report it to their respective Admin Agents.
_Avoid_: assuming that the final peer message alone informs both Admin Agents

**Admin Report**:
A local, privacy-safe handoff from a Communicator Agent to its own Admin Agent containing the terminal outcome, relevant proposal or failure reason, and any required local confirmation. It is domain state, not a UI delivery mechanism.
_Avoid_: Admin notification, SSE event, chat bubble

**UI Notification**:
A presentation of an Admin Agent's report to its local user. It may use SSE or another desktop mechanism, but it neither creates nor replaces the Admin Report.
_Avoid_: communicator report, A2A result

LITTLE_AVATOR 讓受信任的 agent 代表使用者協作、提出決策，並在明確授權下使用外部依賴。

## Language

**Device Identity**:
由 AVATOR 在本機安全儲存區產生的永久非對稱金鑰對、agent ID 與 public-key fingerprint 所構成的裝置身分。它證明同一 private key 的持有連續性，不證明操作者目前的 EIP 人事或組織狀態。
_Avoid_: EIP 官方身分、使用者登入 session

**Trust Record**:
本機保存的 peer agent ID、public-key fingerprint、首次見到時間、允許 Capability 與解除信任狀態。它是 peer 是否可協作的本機信任依據。
_Avoid_: 公開目錄、全組織人員名冊

**Trust on First Use (TOFU)**:
首次遇到未知 peer 時自動建立 Trust Record 的規則。後續只接受同一 agent ID 與 public-key fingerprint 的 peer；既有 agent ID 的金鑰改變不能自動覆蓋。
_Avoid_: QR 配對、企業 PKI 保證、首次連線即永遠正確

**Device Continuity Proof**:
peer 以 private key 對每次新連線產生的 challenge 做簽章，並由對端以 Trust Record 的 public key 驗證的過程。
_Avoid_: IP 位址、mDNS 宣告、可重放的舊簽章

**Local Capability Policy**:
本機依 Trust Record、網路狀態與 Capability 決定 peer 可否 `observe`、`recommend` 或 `commit` 的規則。它不依賴 peer 自己在 task 中宣稱的權限。
_Avoid_: 對端自我宣告、通用登入權限

**Resource**:
協作 task 可觀察、使用、修改或消耗的受管理依賴。Resource 的種類刻意開放，不以任何特定日曆、應用程式或 CLI 為模型限制。
_Avoid_: 固定資源清單、把示例當分類

**Integration**:
連接 Resource 並提供其允許操作的受管理來源。
_Avoid_: Resource、工具

**Action**:
對特定 Resource 執行的一個具名、受授權操作。
_Avoid_: 任意命令、自由工具呼叫

**Resource Definition**:
專案擁有的宣告，描述一個 Resource 可透過哪些 Integration 與 Action 被使用，以及其授權與衝突規則。第一版的 Resource Definition 隨專案版本發布，不接受 agent 動態加入未定義 Resource。
_Avoid_: 動態資源探索、任意外部存取

**Action Readiness**:
某個 Action 在目前已通過其定義的必要前置條件與可用性檢查的狀態。它不保證未來執行一定成功；執行時仍須回報外部失敗或輸入錯誤。
_Avoid_: 健康保證、永久可用

**Capability**:
可處理一類協作 task 的領域契約。Capability 的種類刻意開放；每個 Capability 必須定義其結構化輸入、結果與可用 Action。
_Avoid_: 自由聊天、隱含業務操作

**Intent Coordinator**:
代表一位使用者登記、關聯與協調其協作 task 的權威 Module。它區分重送、相關任務與不同議題的 Resource 衝突。
_Avoid_: 單一 agent、聊天記錄

**Resource Conflict**:
兩個或多個仍有效的 task 對同一 Resource 提出無法同時滿足的需求。它不表示 task 必定重複。
_Avoid_: 重複議題
