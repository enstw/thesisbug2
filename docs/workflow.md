# JSON workflow（課程實驗功能）

這組指令只用於 thesisbug2 課程的 unit，需明確啟用。一般專案先沿用自己的文件與可用的 `context-cleanup` skill；框架更新與 `unit-init` 都不會自動轉換資料。執行環境沿用 Python／uv，沒有 jq 或資料庫依賴。

## 啟用與遷移

所有指令從課程根目錄執行，`hw` 可替換成 unit 短名、完整名稱或路徑。

```bash
./fw workflow hw init --json
./fw workflow hw init --apply --expect <上一步的fingerprint>
```

空白或未改過的 scaffold 可直接預覽；已經寫過的狀態文件需提供遷移計畫，因為工具不能自行判定哪些文字是現行決策。計畫是 JSON，內容例如：

```json
{
  "context": {
    "progress": "- 階段：第一章草稿\n- 下一步：查核引用",
    "requirements": "- 繳交格式：PDF"
  },
  "tasks": [{"title": "核對第一章引用", "details": "逐條對照原文"}],
  "decisions": [{"title": "引用格式", "rule": "使用 APA", "reason": "課程指定", "scope": "本作業"}]
}
```

```bash
./fw workflow hw init --from plan.json --json
./fw workflow hw init --from plan.json --apply --expect <fingerprint>
```

預覽不寫入。fingerprint 同時涵蓋計畫與原始文件，來源改變就必須重新預覽。原本 `PROGRESS.md`、`DECISIONS.md` 的完整文字保存在 `.workflow/migration.json`，只在需要追溯時讀；使用者仍需核對重要規則及未完成事項是否已納入計畫。

## 待辦與決策

```bash
./fw todo hw add "核對第二章引用" --details "確認來源與頁碼"
./fw todo hw list --status blocked --limit 10 --json
./fw todo hw show <id>
./fw todo hw start <id> --expect <revision>
./fw todo hw block <id> "等待全文" --expect <revision>
./fw todo hw done <id> --evidence "已對照原文" --expect <revision>
./fw todo hw reopen <id> --expect <revision>
./fw todo hw update <id> --title "新的標題" --expect <revision>

./fw decision hw add "引用格式" --rule "使用 APA" --reason "課程指定"
./fw decision hw revise <id> --rule "使用 Chicago" --reason "教師修改要求" --expect <revision>
./fw decision hw retire <id> --reason "不再適用" --expect <revision>
./fw decision hw history <id> --limit 10
./fw decision hw show <id> --revision <歷史revision>
```

`id` 是固定 UUID，可用至少 8 字元的無歧義前綴。`revision` 來自最新的 `list`／`show`，可用至少 12 字元的雜湊前綴；工具拒絕拿舊版本覆蓋已變更的項目。`add --id <UUID>` 允許呼叫者安全重試同一筆初始資料。

列表預設最多 20 項，只列未完成待辦／有效決策；`--status all` 才包含完成／撤回項目。`--find <關鍵字>...` 採 AND 篩選，`--offset` 分頁，`--limit` 範圍為 1–100。`show` 才回傳單項完整內容；`history` 也分頁，待辦同樣支援歷史查詢。

## 現況與交接

```bash
./fw workflow hw context --json
./fw workflow hw context --progress "- 階段：第二章草稿" --expect <revision>
./fw workflow hw check
./fw workflow hw handoff --json
./fw workflow hw render
```

啟用後，`PROGRESS.md` 與 `DECISIONS.md` 是完整的生成檢視；現況與外部要求由 `context` 管理，待辦與決策由各自指令管理。手改檢視會被檢查指出；一般項目修改也會拒絕覆蓋這些手改內容。先核對並把有效修改寫回來源，再明確執行 `render` 重建檢視。

交接只查目前工作與阻礙，不追加紀錄；重複查詢、render 與無變化更新不產生修訂。完成待辦會從預設列表消失；值得保留的里程碑另用 `./fw log hw "一行里程碑"` 記錄，避免每個小操作都進入 CHANGELOG。

`check-progress` 與 `build` 會檢查 JSON 和檢視一致性，HTML 簡報也會檢查。交接前執行 `handoff`，因為查資料或修改文件的 session 未必需要 build。

## 儲存與失敗處理

`.workflow/tasks/`、`decisions/` 各項一個 JSON，`context.json` 保存現況摘要；每項檔案含 schema 版本、固定 ID 與完整修訂鏈，最新修訂定義現況。資料與修訂跟著課程 Git 同步；`.lock` 不追蹤。

單項修改先驗證、鎖定，再原子替換。跨機出現分岔修訂時會拒絕載入，需先解決內容衝突；本機鎖不能協調離線機器，也不提供跨多項資料的交易。修訂內容校驗用於發現不一致，不是防竄改的安全簽章。

若 JSON 已保存、檢視更新失敗，指令回傳狀態碼 `3` 與 `saved: true`、項目 ID、revision、恢復指令。執行 `workflow render` 恢復，避免重新新增造成重複。一般資料／版本錯誤回傳 `1`，參數錯誤回傳 `2`。
