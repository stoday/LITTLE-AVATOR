# Throwaway：雙 Akasha agent 邀約協商與行程寫入

此原型驗證：A 由使用者指令發出「請問你何時有空，想約你吃東西的邀約」，A/B 各自讀自己的食物偏好與今日行程，用回覆文字多輪協商；外層只在雙方同意相同時段與餐點後，才允許兩方各自寫入自己的行程。

## 私有資料

- preferences/a_private_preferences.txt、preferences/b_private_preferences.txt：只有個人食物偏好，沒有本次議題。
- schedules/a_today.txt、schedules/b_today.txt：各自今天的文字行程。

每個 agent 只有三個 tools：讀自己的食物偏好、讀自己的行程、寫自己的行程。寫入工具在外層確認共識前一律拒絕。

## 共識與寫入

協商回覆末尾必須是：

    [[STATE:continue]]
    [[STATE:agree|15:00-16:00|意麵]]

外層確認雙方相同後，才開啟一次性寫入授權，讓 A/B 各自呼叫自己的 write_today_schedule。輸出 discussion.md 顯示討論、外層解析和寫入結果；result.json 留下行程內容。

## 執行

    .\.venv\Scripts\Activate.ps1
    python .\prototypes\a2a_multiturn_negotiation\run.py --self-check
    python .\prototypes\a2a_multiturn_negotiation\run.py
