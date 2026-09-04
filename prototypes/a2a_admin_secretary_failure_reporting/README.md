# Throwaway：A/B admin 與秘書協商失敗回報

此原型有四個真實 Akasha agents：

- agent-a-admin：接收使用者邀約並委派 agent-a。
- agent-a：A 的秘書，讀 A 的偏好與行程，對外協商。
- agent-b：B 的秘書，原本不知道任務，收到 A 的邀約後才開始協商。
- agent-b-admin：原本不知道任務；失敗後才首次收到 agent-b 的詳細報告。

A 只可接受火鍋、鹹粥；B 只可接受牛排、咖哩飯。因此沒有共同可接受餐點。外層政策會拒絕任何不符合雙方偏好檔的假共識，且不會授權寫入行程。

失敗報告包含：任務來源、原始邀約、B-admin 事前未知狀態、雙方可接受限制、完整對話、無法成功的原因、未寫入行程事實與建議後續行動。

執行：

    python .\prototypes\a2a_admin_secretary_failure_reporting\run.py --self-check
    python .\prototypes\a2a_admin_secretary_failure_reporting\run.py
