# Windows 編碼、權限與 sandbox 避雷流程

## 觸發背景

本次 Little Avatar 工作區曾遇到：一般 `exec_command` 在建立 runner pipe 時逾時；內建 `apply_patch` 在 Windows sandbox helper 讀檔時逾時；PowerShell 主控台以 CP950 顯示 UTF-8 中文而看似亂碼；Git 操作則需要 elevated 權限才能正常執行。這些症狀不應直接判定為程式或檔案損壞。

## 建議流程

1. **先做最小、唯讀的狀態檢查**：`git status --short --branch`、`git branch -vv`、必要時 `git diff --check`。不要在狀態未知時直接 merge、commit 或覆寫檔案。
2. **runner pipe 啟動逾時**：同一命令只重試一次；若連 `git --version` 或 `Get-Location` 都無法啟動，停止盲目重試，改用明確、最小範圍的 `require_escalated` 命令，並在回報中說明這是執行器啟動問題。
3. **Git 權限錯誤**：若出現 `.git/index.lock: Permission denied`，先檢查 `.git\index.lock` 是否真的存在；不存在時不要刪除 lock。優先使用受限的 elevated Git 命令。Windows sandbox 的 unelevated 設定可能阻止 Git 建立 lock，即使工作區本身可寫。
4. **`apply_patch` sandbox/helper 逾時或 restricted-token 錯誤**：不要連續重試相同 patch。先將目標檔案備份到明確的 `C:\tmp\<project>-backup`，再以穩定 ASCII marker 或精確 regex 做最小替換。保留備份直到驗證完成。
5. **UTF-8 文件 fallback**：使用 `[IO.File]::ReadAllText($path, [Text.Encoding]::UTF8)` 與 `[IO.File]::WriteAllText($path, $text, [Text.UTF8Encoding]::new($false))`，避免 `Set-Content` 的版本相依編碼與 BOM 問題。只在 `apply_patch` 確實不可用時採用此 fallback，並明確回報。
6. **驗證文件編碼**：以 bytes 確認沒有 UTF-8 BOM（除非專案明確要求），用 UTF-8 strict read 回讀，掃描 U+FFFD replacement character，再跑 `git diff --check`。PowerShell 顯示中文亂碼不等於檔案已損壞，應以 bytes/strict decode 判斷。
7. **PowerShell/Python 輸出**：Windows CP950 可能無法顯示 Akasha verbose、emoji 或中文。需要執行專案 Python 時使用 `C:\Python313\python.exe`；需要印出診斷時先把 stdout/stderr 設為 UTF-8 並以 `backslashreplace` 或等效策略處理。
8. **命令列 `apply_patch` 編碼**：PowerShell pipeline 可能以非 UTF-8 傳送 patch，即使文字看起來正確；不要把一般 here-string pipe 給 wrapper 當成可靠方案。優先使用內建 apply_patch；失敗後走第 5 步的明確 UTF-8 fallback。
9. **Git merge/commit 的範圍安全**：在 unborn branch、剛完成 merge 或大量未追蹤檔案存在時，commit 前再次檢查 `git diff --cached --name-status` 與 `git status --short`；若預期只提交一個檔案，先確認 index 真的只有該檔案，再執行 commit。不要把「已 staged」當成未追蹤檔案不會被納入的充分證據。
10. **Graphify 或其他工具不存在**：先記錄實際錯誤（例如 `No module named graphify`），再依規範改用 `rg`、目標檔案讀取與 focused checks；不可把工具未執行當成程式現況已被圖譜驗證。

## 最小驗證清單

- `git status --short --branch`
- 目標檔案 UTF-8 strict read、U+FFFD 掃描、BOM 檢查
- `git diff --check`
- 需要時使用 `C:\Python313\python.exe` 做 `py_compile` 或 focused test
- 回報時分清：source diff、focused test、瀏覽器/視覺驗證、部署驗證

## 本次具體教訓

- `FETCH_HEAD` 與 `origin/main` 合併時，未追蹤 `.gitignore` 會阻擋 read-tree；應先備份明確衝突檔案，再合併並恢復本地內容。
- commit 前只想提交 README，但實際 commit 包含整個專案；之後必須在 commit 前檢查 index 與提交統計，若範圍不符應先停止，不要事後猜測。
- README 原始 bytes 是合法 UTF-8；PowerShell 顯示的 CP950 mojibake 不能代替編碼驗證。