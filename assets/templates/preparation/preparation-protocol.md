# Preparation_Protocol.md

選題與初步文獻搜尋的**方法論已抽離為 cross-agent 的 `topic-scout` skill**
（`.framework/.agents/skills/topic-scout/SKILL.md`）。選題方法、五階段流程、題目評估矩陣、常見失誤、
新聞訊號 TRIZ 選題法與互動巨集，一律以該 skill 為準（深入內容見其
`reference/methodology.md`）。本檔只保留 `preparation` work type 專屬的角色定位、
產出位置與相關 skill 指引。

## 角色與產出

* **AI 角色**：研究選題助理、文獻搜尋規劃者與初步文獻評估者。
* **使用者身分與學門**：以科目根目錄的 `COURSE.md` 為準；本協定不記載個人資訊。
* **工作重點**：協助使用者從模糊興趣收斂到可執行題目，建立足以支撐後續 `journal`、
  `thesis`、`homework` 或 `presentation` 的初步文獻基礎。
* **產出**不是正式正文，而是「選題決策包」：候選題目與研究問題、雙語關鍵詞與查詢式、
  可追溯的文獻搜尋紀錄、初步文獻清單與全文取得狀態、最終建議題目與下一步 work type。

## 產出位置（preparation work type 專屬）

topic-scout 的五階段在本 work type 寫入下列位置：

| topic-scout 階段 | 寫入位置 |
| :--- | :--- |
| Phase 1 建立候選題目 | `<unit>/preparation.qmd` 「候選題目」「選題概況」 |
| Phase 2 設計搜尋策略 | `<unit>/preparation.qmd` 「搜尋策略」 |
| Phase 3 蒐集與下載文獻 | `<unit>/references.bib`、`<unit>/refs/`（取得流程見 **`source-kit`** skill）、`<unit>/preparation.qmd` 「文獻清單」 |
| Phase 4 摘要與評估文獻 | `<unit>/preparation.qmd` 「文獻摘要」 |
| Phase 5 決定題目與下一步 | `<unit>/preparation.qmd` 「選題決策」、`<unit>/PROGRESS.md` |

## 相關 skill

* **`topic-scout`** — 選題方法論與 `/topic_discovery`、`/prep_start`、`/search_plan`、
  `/lit_scan`、`/screen`、`/topic_decision`、`/handoff` 巨集。
* **`source-kit`** — Phase 3 文獻取得、儲存與審核（landing page / CDN 處理）。
* **`cite-check`** — 引用格式與一致性檢查。
* **`fix-terms`** — 兩岸用語與術語校正。
