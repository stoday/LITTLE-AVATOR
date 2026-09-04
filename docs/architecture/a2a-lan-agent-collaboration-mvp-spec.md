# LITTLE_AVATOR：A2A 區網 Agent 協作（MVP 規格草案）

## 目的

受組織端點使用規範保護的公司區網內，使用者可對 LITTLE_AVATOR 說「找小明開會」。兩端 AVATOR 在背景確認已建立的裝置信任、協商可用時段，最後再依設定通知或請雙方確認。

這是受限制的「排程協商」，不是讓兩個 agent 任意聊天。

## 使用者體驗

1. 小華說：「找小明開 30 分鐘會議。」
2. 小華的 AVATOR 在區網找到小明的 AVATOR。
3. 兩個 agent 在背景比較允許透露的忙閒時段，提出合適時間。
4. AVATOR 顯示結果，例如：「已找到週三 14:00，等待確認。」
5. 雙方確認後才建立日曆事件。未來可為低風險會議開放自動建立。

使用者不需要輸入 IP、掃 QR code、處理憑證警告，或逐次允許 agent 互相說話。

## MVP 範圍

### 要做

- 同一受控公司區網內的 AVATOR 自動發現彼此。
- A2A 用於 agent 對 agent 的排程協商 task。
- A 與 B 都先驗證對方持有已記錄的裝置私鑰；成功後才交換協商資料。
- 首次遇到候選裝置時採自動首次信任（TOFU）；後續只信任持有相同裝置金鑰的對端。
- 只交換忙閒、會議時長、時區與允許的偏好；不交換完整行事曆內容。
- 候選時段可短期暫留（hold），避免多個 agent 同時搶到同一時段。
- 最終建立會議前保留使用者確認流程。

### 不做

- Internet 跨網路互通、公開 agent 搜尋或公開 Agent Card。
- 跨 Internet、跨未受控網路或跨組織的互通。
- 任意自由對話、任意檔案交換，或由遠端 agent 操作本機工具。
- 讀取、複製或轉送 EIP 瀏覽器 Cookie 或 session。
- 以 Telnet、裸 HTTP 或「有一條連線就鎖住整台 agent」處理安全或衝突。

## 信任與安全

### 區網自動發現：mDNS 負責找人，裝置金鑰負責延續信任

### 基本做法

每台完成本機 AVATOR 註冊的電腦，在允許的公司網路介面上宣告一個 mDNS 服務：

    _little-avator-a2a._tcp.local

mDNS 是區網的「附近裝置名單」。它不需要固定 IP、中央伺服器或使用者輸入位址；DHCP 讓 IP 改變後，新的宣告會被其他 AVATOR 自動看到。

### mDNS 如何找到正確端點

_little-avator-a2a._tcp.local 是區網服務類型名稱，不是公開網際網路網域。它的意思是：「這個區網中，誰提供 LITTLE_AVATOR 的 A2A TCP 服務？」

A 會對區網 multicast 發出 mDNS 查詢；提供服務的 B 回覆自己的服務實例、目前主機名稱與連接埠。A 再用 mDNS 取得該主機名稱目前對應的 IP，才嘗試建立連線。

mDNS 資料可理解為三層：

| 資訊 | 範例 | 用途 |
| --- | --- | --- |
| 服務類型 | _little-avator-a2a._tcp.local | 找「哪種服務」 |
| 服務實例 | agent-abc._little-avator-a2a._tcp.local | 找「哪一台 AVATOR」 |
| 目前位址 | 192.168.1.42:8443 | 實際建立連線的位置 |

服務實例與 agent ID 用來識別候選 AVATOR；目前 IP 與 port 只是一段時間內的連線位置。

### DHCP IP 變動如何處理

AVATOR 不應永久記住 192.168.1.42 這類 IP。mDNS 記錄帶有短暫 TTL，且 AVATOR 應監聽本機網路變更：

1. B 的 DHCP IP 從 192.168.1.42 改為 192.168.1.77。
2. B 偵測到網路變更後，重新宣告自己的 mDNS 服務與新位址。
3. A 的舊快取會到期；A 下次查詢或連線失敗後重試時，取得 192.168.1.77。
4. A 對新 IP 重建加密連線，並再次要求 B 證明持有已信任的裝置私鑰。

因此 IP 是「目前在哪裡」，不是「對方是誰」；穩定的 agent ID 與已記錄的裝置公鑰才是裝置身分。即使有人用 mDNS 假冒位址，也無法證明持有已信任裝置的私鑰。

宣告可包含的最小資料：

| 欄位 | 用途 | 是否可當信任依據 |
| --- | --- | --- |
| service type | 表示這是一個 LITTLE_AVATOR A2A 服務 | 否 |
| instance / agent ID | 隨機且不含姓名的裝置識別 | 否 |
| host / port | 本機 A2A HTTPS 端點的位置 | 否 |
| protocol version | 例如 A2A 與 schedule-meeting.v1 版本 | 否 |
| device public-key fingerprint hint | 加速比對與偵錯的提示 | 否，必須再做私鑰持有證明與本機 trust record 比對 |

不要在 mDNS TXT record 放使用者姓名、部門、EIP Cookie、行事曆內容、私鑰或可直接登入的 token。mDNS 封包可被同網段裝置看到。

### 發現到連線的流程

    1. AVATOR 啟動，確認目前網路屬於允許的公司網路。
    2. 它以 UDP 5353 宣告或查詢 _little-avator-a2a._tcp.local。
    3. 收到候選端點後，只把端點暫存為「未信任候選」。
    4. 使用者說「找小明開會」時，A 以本機聯絡人別名或另一個已決定的名稱來源找出預期 agent ID；mDNS 不以姓名作為信任依據。
    5. A 對候選端點建立加密連線，並要求 B 以私鑰簽署新的 challenge。
    6. 若已存在 B 的 trust record，A 比對 agent ID、public-key fingerprint 與簽章；首次遇到時依 TOFU 建立 trust record 並留下稽核紀錄。
    7. B 對 A 做相同驗證；雙方通過本機 capability policy 後，A 才可建立 A2A schedule-meeting task。
    8. 連線失敗、簽章不符、未知的金鑰變更或政策拒絕時，丟棄候選端點並留下稽核紀錄；不顯示技術性確認對話框。

因此，「同一區網」只讓 A 知道 B 可能在哪裡；裝置金鑰連續性只證明它是曾建立信任的那台 AVATOR，不能證明它目前仍是 EIP 官方認定的特定員工。

### 名稱與裝置金鑰對應

不要以裸 IP 作為裝置身分，因為 IP 會因 DHCP 改變。AVATOR 在首次本機註冊時產生穩定 agent ID 與非匯出的永久金鑰對，例如：

    agent-<uuid>

私鑰應由 Windows 安全儲存區或 TPM 保護，public-key fingerprint 與 agent ID 寫入本機 trust record。mDNS 只負責把候選名稱解析到目前的 IP；連線端以 challenge-response 驗證私鑰持有，並比對 trust record。這樣即使 IP 改變，已建立的裝置信任仍不變。

### 網路與防火牆需求

- UDP 5353 multicast：用於 mDNS 查詢與宣告。
- 一個指定或受控範圍的 TCP port：只提供 A2A HTTPS/WSS。
- AVATOR 只監聽公司網路介面；公用 Wi-Fi、未知網路與 VPN 依組織政策預設不宣告。
- 防火牆只允許必要的區網來源，不將 A2A port 對 Internet 開放。
- Agent Card 與 task endpoint 只在加密連線、裝置私鑰持有證明與本機 policy 成功後提供完整資訊。

### 同一組織不一定等於同一個 mDNS 網段

mDNS 通常只在同一個 Layer-2 網段或 VLAN 內傳播。若 A 與 B 分屬不同 VLAN、樓層網段，或公司網路封鎖 multicast，不能假設自動發現會成功。

此時可採組織網路提供的 relay 或 directory：

    AVATOR -> directory 查詢候選端點
            -> 仍以加密連線與裝置金鑰驗證建立 A2A 連線

directory 只解決「在哪裡」，不能取代本機 trust record 與 capability policy。第一版應先由網管確認公司網路是否允許 mDNS，再決定直連、directory，或兩者並存。

## 本機裝置信任是 MVP 的信任根

EIP 沒有 AVATOR 可呼叫的裝置註冊、憑證簽發或身分驗證 API；MVP 不假設這些能力存在。使用者在受組織規範保護、由本人使用的電腦上登入 EIP，是初始註冊的使用者程序門檻，不是可由對端驗證的密碼學聲明。

每台 AVATOR 在本機產生永久非對稱金鑰對；私鑰只留在 Windows 安全儲存區或 TPM，public-key fingerprint 與 agent ID 可被記錄。它們代表「這台曾被註冊、持續持有此私鑰的 AVATOR」，不代表 EIP 官方保證其操作者目前仍在職、仍屬特定組織。

### 首次註冊與自動首次信任

```text
使用者在受控電腦上完成 EIP 登入，並在 AVATOR 按下「此裝置代表我」
AVATOR 於安全儲存區產生 private key，建立 agent ID 與本機 device identity
首次遇到候選 peer 時，AVATOR 自動建立只含 agent ID、public-key fingerprint、首次見到時間與允許 capability 的 trust record
後續連線只接受能證明持有相同 private key 的 peer
```

這是 TOFU（trust on first use）：移除逐位同事 QR／確認碼配對的摩擦，但首次接觸若遭同網段冒充者攔截，可能信任錯誤裝置。這不是企業 PKI 的替代品；MVP 以受控端點、區網限制、低風險 capability、正式日曆確認與可解除信任來限制風險。

### A 與 B 如何驗證

發起 A2A task 前，先建立加密傳輸通道；協定須使用經審核的現有 TLS/Noise 類加密與簽章元件，不得自創密碼學演算法。流程為：

```text
A 宣告 agent ID 與 public-key fingerprint，並以 private key 簽署 B 提供的新 challenge
B 驗證簽章、比對 A 的 trust record 與本機 capability policy
B 也對 A 執行相同的 challenge-response 與 policy 檢查
雙邊皆通過，才開始 A2A 排程協商
```

challenge 必須每次新連線產生，避免舊簽章被重放。private key、EIP Cookie、session、帳密與任何可重用登入 token 均不得傳給其他 agent。public-key fingerprint 是系統背景比對資訊，不作為個資顯示。

### 金鑰變更、解除信任與區網傳輸

首次見到未知 agent ID 時可依 TOFU 建立 trust record；但已知 agent ID 的 public-key fingerprint 改變時，系統不得自動覆蓋舊 trust record。它必須拒絕自動協商、留下稽核紀錄，並要求使用者從本機解除舊信任後才能重新建立。

使用者可隨時解除對端 trust record；遺失、換機、重裝或懷疑遭他人操作時，也應解除本機 device identity 並重新註冊。Windows 工作階段鎖定時，不得發起或確認協作。

區網 IP 仍只是位址，不是身分。傳輸使用加密通道，防止同網段裝置竊聽或竄改；裝置私鑰持有證明與 trust record 才提供對端連續性。

## 端到端流程

```text
使用者 A：「找 B 開 30 分鐘會議」
  -> AVATOR A 解析對象與條件
  -> 區網 discovery 找到 B
  -> 加密連線：雙方驗證已信任裝置的私鑰持有證明與 capability policy
  -> A2A 建立 schedule-meeting task
  -> 兩端 Calendar Coordinator 比對忙閒並暫留候選時段
  -> A2A 回傳 1 到 3 個候選方案或等待確認狀態
  -> 使用者確認或取消
  -> 將有效 hold 轉為正式日曆事件，或釋放 hold
```

## A2A 的角色

A2A 是 A 與 B 的工作溝通協定，不是日曆資料庫，也不是鎖定機制。

MVP 對外只宣告一項 A2A skill：

```text
schedule-meeting.v1
```

| 狀態 | 意義 |
| --- | --- |
| `working` | 正在取得忙閒或協商候選時段 |
| `input-required` | 已有候選結果，等待使用者確認或補充條件 |
| `completed` | 已成功建立會議，或完成設定允許的結果 |
| `canceled` | 任一方取消 |
| `rejected` | 對方無排程權限、政策不允許或拒絕協商 |
| `failed` | 網路、裝置信任驗證、日曆寫入或暫留過期失敗 |

協商訊息使用結構化資料，不以自由文字作為機器決策依據：

```json
{
  "skill": "schedule-meeting.v1",
  "negotiation_id": "uuid",
  "duration_minutes": 30,
  "time_zone": "Asia/Taipei",
  "privacy_level": "free_busy_only",
  "requires_human_confirmation": true
}
```

## 通用協作決策：排程只是第一個 capability

A2A 不應只用於橋會議，也不應變成讓 agent 任意聊天、任意決定的通道。設計上應提供一個通用的 Collaboration Module；它集中處理本機裝置信任、A2A task、權限政策、狀態、重試與稽核。

外部呼叫者只需要建立或回應協作 task；各種具體決策則由 capability adapter 處理：

    Collaboration Module
      -> 驗證、授權、A2A task、狀態、稽核
      -> capability adapter
           - calendar.negotiate.v1
           - document.review.v1
           - resource.allocate.v1
           - workflow.route.v1

排程是第一個 adapter，不是整個協定的限制。

### 通用 task 外殼

每一個協作 task 都有相同的基本資料；每個 capability 再定義自己的結構化 constraints 與結果：

    {
      "task_id": "uuid",
      "capability": "calendar.negotiate.v1",
      "goal": "安排 30 分鐘會議",
      "participants": ["agent-a", "agent-b"],
      "constraints": {},
      "authority": "recommend",
      "expires_at": "2026-08-30T10:05:00Z",
      "idempotency_key": "uuid"
    }

可擴充的例子：

| capability | 協作內容 |
| --- | --- |
| calendar.negotiate.v1 | 時段、時長、與會者 |
| document.review.v1 | 修改提案、審核意見 |
| resource.allocate.v1 | 會議室、設備、人力 |
| workflow.route.v1 | 工作認領、處理者與優先順序 |

### 通用 task 狀態

    requested
    -> negotiating
    -> proposal_ready
    -> awaiting_authorization
    -> committed / rejected / canceled / expired / failed

這些狀態描述協作流程；它們不代表每個 capability 都有相同的業務動作。

### 權限只有三種

裝置連續性與操作授權必須分開。challenge-response 與 trust record 只回答「這是不是曾建立信任的裝置」；authority 才回答「它可做什麼」。

    observe     只能取得允許的資訊
    recommend   可提出建議，但不能改變外部狀態
    commit      可執行正式、可能不可逆的動作

例如，文件審核通常使用 observe 與 recommend；正式送出決策、建立日曆事件或修改外部系統則需要 commit。

Calendar 的 hold 不另列為通用 authority。它是 Calendar Adapter 為了處理同時協商而使用的短效、可自動到期併發控制實作；它不代表使用者已經同意，也不是其他 capability 必須實作的權限。

## 防止多方撞期：hold，而不是鎖連線

多個 agent 可以同時協商；不可因為 A 與 B 正在溝通，就禁止 C 對 B 提出需求。

每位使用者的 Calendar Coordinator 對特定時段執行：

```text
check_and_hold(slot, negotiation_id, expiry)
release_hold(negotiation_id)
confirm_hold(negotiation_id)
```

`hold` 是短期、可到期的時段保留，例如 5 分鐘。到期、取消或確認失敗即釋放。正式建立日曆事件時，仍必須再次原子檢查衝突。

## 無打擾的預設政策

在受控公司網路內，已通過 trust record 與 capability policy 的 AVATOR 預設可發起 `schedule-meeting.v1`；不需要每次跳「是否允許對方 agent 說話」。

政策可限制：

- 只對同部門或聯絡人群組協商。
- 只透露忙閒，不透露會議名稱、地點、參與者或備註。
- 只在工作時間提出候選時段。
- 預設只產生暫定方案；正式建立事件必須由各方確認。

已知 agent ID 的未知或已變更 public-key fingerprint、已解除信任的 peer，或沒有 `schedule-meeting` 權限的請求，直接拒絕並留下稽核記錄，不彈出讓使用者判斷的技術性對話框。

## 組織與平台需要確認的能力

1. 受控電腦、Windows 帳號鎖定與「EIP 帳號不得交由他人使用」的現行端點使用規範是否適用於 AVATOR 使用者？
2. Windows 安全儲存區或 TPM 是否可供 AVATOR 保存不可匯出的裝置私鑰？
3. 組織網路是否允許 AVATOR 之間的指定 LAN port 與 mDNS discovery？若否，是否提供內網 relay 或 directory？
4. 「小明」可由何種非信任來源解析成預期 agent ID：本機聯絡人、使用者管理的別名，或未來的組織 directory？
5. 日曆是否已有可安全查詢忙閒與建立事件的 API？其衝突與 idempotency 規則是什麼？
6. 未來若 EIP 提供裝置註冊、簽發憑證或短效委派 token，是否要以版本化的 trust provider adapter 將其作為可選的強信任模式？

## 驗收條件

- 已註冊的 A 與 B 在同一區網可互相發現，並在不需要 IP、QR code 或逐次同意的情況下完成私鑰持有證明與 trust record 驗證。
- 已知 agent ID 的 public-key fingerprint 不符、已解除信任或 policy 不允許的 peer，無法建立 A2A 排程 task。
- A2A task 只能呼叫 `schedule-meeting.v1`，只交換約定的結構化欄位。
- 兩個以上協商同時進行時，不會建立重疊的正式日曆事件。
- hold 到期、取消、網路中斷及重送後，狀態可恢復，且不會產生重複會議。
- EIP Cookie、session、硬體私鑰、完整行事曆內容與可重用登入 token 不會離開其應在的位置。

## 待決定事項

- MVP 是否一律要求雙方確認，或允許特定群組或規則自動建立會議？
- 「小明」的解析來源是本機聯絡人、使用者管理的別名，還是未來的組織 directory？
- 暫留預設期限要多長？建議先採 5 分鐘。
- 第一版採 AVATOR 對 AVATOR 直連，還是採組織內網 relay 或 directory？若網路政策嚴格，後者通常較容易維運。
