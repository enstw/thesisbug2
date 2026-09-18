---
name: topic-scout
description: >
  Turns a vague research interest into 2–5 comparable candidate topics, each
  with a research question, bilingual search plan, traceable literature scan,
  and evaluation-matrix score, ending in a topic decision and handoff. Use when
  the user is choosing a thesis / journal / homework topic or asks to 選題 / 想題目 /
  find a research question / plan a literature search, and for the
  /topic_discovery, /prep_start, /search_plan, /lit_scan, /screen,
  /topic_decision, /handoff macros.
user-invocable: true
---

# topic-scout — evidence-first topic selection (選題)

把模糊興趣收斂成「可被資料回答、可被文獻定位、可在篇幅內完成」的研究問題。這是
`preparation` work type 的方法論層；產出不是正文，而是**選題決策包**。深入方法論
（主題≠問題、puzzle、題目公式、新聞訊號 TRIZ 法、評估矩陣、常見失誤）見
[`reference/methodology.md`](reference/methodology.md)。

## 角色與產出

- **AI 角色**：研究選題助理、文獻搜尋規劃者、初步文獻評估者。
- **選題決策包**包含：2–5 個候選題目與研究問題、雙語關鍵詞與查詢式、可追溯的搜尋
  紀錄、初步文獻清單與全文取得狀態、最終建議題目與下一步 work type。

## 工作原則

1. **先證據，後題目。** 不要太早把題目寫死。每個候選題目須通過三道門檻：文獻可得、
   問題可問、範圍可控。
1. **戰略層次優先。** 技術背景用來理解材料，但題目判斷要回到國際關係、戰略研究、
   國家安全、地緣政治或軍事安全層次。偏純技術/產品比較/合規稽核者，主動提出如何
   轉回戰略問題，或標示不適合本 repo 學術工作流。
1. **可追溯性。** 書目進 `<unit>/references.bib`；全文進 `<unit>/refs/`（取得流程見
   **source-kit** skill）；PDF 用 `p.`、網頁存檔用 `para.` 標位；找不到全文時記錄
   不可得原因，不可憑摘要推論不存在的內容。

## 五階段流程

| Phase | 目標 | 交付物 |
| :--- | :--- | :--- |
| **1 建立候選題目** | 把興趣整理成可比較的候選題目，不直接定案。 | 每題：暫定題名、研究問題、研究對象與範圍、初步重要性、主要風險。 |
| **2 設計搜尋策略** | 建立可重複執行的搜尋路徑。 | 中文關鍵詞、英文關鍵詞、布林查詢式、來源類型、篩選條件。 |
| **3 蒐集與下載文獻** | 建一個小而可信的初步文獻庫。 | `references.bib` + `<unit>/refs/`（→ **source-kit**）。下限：短作業/簡報 8–12 筆、期末/journal 12–20 筆、碩論 20+ 筆且涵蓋理論/案例/方法/反方。 |
| **4 摘要與評估文獻** | 判斷文獻能否支撐題目（非完整文獻回顧）。 | 每筆核心文獻：研究問題、方法/材料、核心論點、可引頁碼/段落、可用位置、與其他文獻關係。 |
| **5 決定題目與下一步** | 產出可執行 handoff。 | 建議題目、研究問題定稿、範圍界定、暫定論點/假設、文獻缺口、下一步 work type。 |

**輸出位置**因 work type 而異（`preparation` 寫入哪個 `.qmd` 區段見
`assets/templates/preparation/preparation-protocol.md`）。

## 互動巨集

| 指令 | 功能 |
| :--- | :--- |
| `/topic_discovery` | 使用者只給大領域時，先用近期新聞與政策訊號做 TRIZ 式矛盾抽取，產出不少於 5 個候選題目（見 methodology § 新聞訊號驅動的矛盾式選題法）。 |
| `/prep_start` | 依興趣或 `/topic_discovery` 結果建立 3–5 個可比較的候選題目。 |
| `/search_plan` | 為目前候選題目建立雙語關鍵詞、查詢式與來源清單。 |
| `/lit_scan` | 根據搜尋結果整理初步文獻清單與全文取得狀態（取得交給 **source-kit**）。 |
| `/screen` | 用題目評估矩陣比較候選題目，標示保留、排除或待查。 |
| `/topic_decision` | 產出建議題目、研究問題、範圍界定與下一步 work type。 |
| `/handoff` | 把 preparation 結果整理成可轉入 `journal`/`thesis`/`homework`/`presentation` 的摘要。 |

## 相關 skill

- **source-kit** — Phase 3 的文獻取得、儲存與審核。
- **cite-check** — 引用格式與一致性檢查。
- **fix-terms** — 兩岸用語與術語校正。
- **house-style** `reference/content-integrity.md` — 引用內容的誠信規則。
