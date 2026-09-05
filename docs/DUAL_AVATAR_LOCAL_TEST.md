# 同一台電腦的雙 avatar A2A 測試

在 PowerShell 啟動兩個獨立的 Momo 後台與桌面視窗：

```powershell
.\scripts\start-dual-avatar.ps1 -PortA 18765 -PortB 18766 -NameA "小王" -NameB "小美"
```

此例中，A 是「小王的 Momo（發起者）」、B 是「小美的 Momo（受邀者）」。
請在小王的視窗輸入：

> 幫我跟小美說，我想約她吃晚餐，請問她什麼時候有空、想吃什麼？

## 時間表與兩回合協商

每個後台有自己的 `momo-notes` 資料目錄與時間表：

- A：`data/dual-avatar/avatar-a/schedule.md`
- B：`data/dual-avatar/avatar-b/schedule.md`

第一次執行時，啟動器會從下列可版控範本建立它們；之後不會覆寫你的修改：

- [A 的範本](dual-avatar-schedules/avatar-a.schedule.md)
- [B 的範本](dual-avatar-schedules/avatar-b.schedule.md)

格式是每個時段一行：

```md
- Wednesday 19:00 | available
- Wednesday 18:00 | busy
```

只有 `available` 會由 `momo-notes` 讀出並告知對方；`busy` 與 `unavailable`
不會離開本機。流程為 A 傳出自己的可約時段與餐點選項，B 用自己的
`schedule.md` 找交集並提出暫定時間，A 再送第二回合請 B 驗證該提案。雙方
各自收到本機 admin 摘要時，會彈出獨立的「協商結果」視窗：上方是本機 admin
結論，下方是實際交換的 communicator 訊息。原來的聊天視窗不會附加 A2A 對話紀錄，
結果視窗也只有關閉按鈕；不會出現一般 Momo 提示泡泡的建議、逗我或聊天操作。此紀錄
不含 system prompt、思考過程、憑證或未送出的本機資料。

這些 communicator 訊息、暫定提案與雙方 admin 摘要均使用繁體中文。

收到暫定結果後，直接在各自聊天視窗輸入「我同意」或提出新的自然語句意見；
不使用 **Discuss** 或 **Confirm locally** 按鈕控制流程。

關閉兩個桌面視窗或在 PowerShell 按 Ctrl+C，即可停止兩個後台。

這是同一台電腦上的跨 process 驗證；不代表已完成實體 LAN、mDNS、TLS、
裝置信任連續性或防火牆測試。
