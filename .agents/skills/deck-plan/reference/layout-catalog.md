# Layout Catalog — 簡報版型目錄 (v1.0)

本目錄列出 `thesisbug2` 支援的 16 種標準版型代碼（5 大族群）。在撰寫 `<talk>/storyboard.md` 時，「版型」欄位直接填入版型代碼，「畫面內容」欄位則填入對應的**槽位微語法（Slot Micro-syntax）**。

執行 `./fw deck-compile <talk>` 時，編譯腳本會讀取 `storyboard.md` 前提中的 `Seed`（隨機種子），以確定性（Deterministic）演算法自動挑選深度視覺變體（Variants）與色彩節奏，毫秒級編譯出語意結構精準、符合投影機字級規範的 `deck.html`。

> 💡 **互動展示工作台**：可開啟 [`docs/layout-explorer.html`](file:///Users/j/homework/thesisbug2/docs/layout-explorer.html)（或執行 `./fw deck-compile --explorer` 取得連結），在瀏覽器中動態切換 16 種版型、深度變體與 14 種主題，並一鍵複製分鏡語法。

---

## 語意槽位微語法（Micro-syntax）

在 `storyboard.md` 表格的「畫面內容」欄位中：
- 欄位之間以 `<br>` 換行。
- 鍵值格式為 `key: value`。
- 清單項目以 `-` 或 `*` 開頭：
  - 卡片清單：`- [tag] 標題: 說明文字`（亦支援 `- [tag] 標題 | 說明文字`）
  - 無標籤清單：`- 標題: 說明文字`
  - 純文字清單：`- 要點文字`
- 內嵌字典支援 JSON 或簡寫：`side_a: {camp: "現實主義", points: ["要點 1", "要點 2"]}`。

### 通用選填槽位：收束框的標籤

有收束框的版型（`verdict`、`ask_or_verdict`、`takeaway`、`core_focus`、`theoretical_puzzle`）都會在框前加一個粗體標籤，各版型預設不同：「結論」「定論」「裁決／提問」「最終均衡」「歷史啟示」「核心焦點」「理論謎題／意涵」。同一個框實際可能放機制意涵、案例觀察或討論流程，固定的「定論」就會替內容下錯判斷，所以每頁可以改：

- `verdict_label: 機制意涵`：把標籤換成這個詞。
- `verdict_label: none`：不加標籤。

不寫就沿用版型預設。

---

## 一、 宣告與定性類（Declarative & Thesis）

### 1. `L-HERO-TITLE`（開場主封面）
- **使用情境**：簡報首頁（第 0 頁）。
- **槽位規格**：
  - `title` *(必填)*：主標題
  - `sub` *(選填)*：副標題（交代個案或範疇）
  - `meta` *(選填)*：導讀人、場合或日期
- **畫面內容範例**：
  ```text
  title: 大國競爭下的供應鏈重組策略<br>sub: 台灣半導體生態系的戰略抉擇<br>meta: 國際關係專題研討 · 2026 年秋
  ```

### 2. `L-FINALE-SUMMARY`（閉幕與核心結論）
- **使用情境**：簡報結尾頁（最後一頁），統整全篇核心貢獻或拋出問答。
- **槽位規格**：
  - `heading` *(必填)*：大標題（如「結語與討論」）
  - `onesentence` *(選填)*：一句話核心總結
  - `points` *(選填)*：條列核心收穫或提問
  - `points_align` *(選填)*：寫 `left` 讓條列靠左（大標仍置中），因為較長的條列換行後置中排列不好讀
- **畫面內容範例**：
  ```text
  heading: 結論：韌性與效率的權衡<br>onesentence: 地緣經濟碎片化正以安全之名重構全球生產網絡。<br>points:<br>- 區域化生產必然推升資本與營運邊際成本<br>- 台灣需以技術無可替代性維繫戰略矽盾
  ```

---

## 二、 平行展開與收束類（Parallel Expansion & Synthesis）

### 3. `L-3CARD-VERDICT`（三子項展開＋底部定論）
- **使用情境**：闡述三個關鍵機制、面向或現象，並在底部收束出明確的定性結論。
- **深度變體**：`top-rail`（頂部彩條）、`tint-elevated`（微漸層高亮）、`side-border`（左側邊框條）。
- **槽位規格**：
  - `title` *(必填)*：頁面大標
  - `lead` *(選填)*：背景導言句
  - `cards` *(必填，3 項)*：`- [tag] 標題: 內容`
  - `verdict` *(必填)*：底部收束結論句
- **畫面內容範例**：
  ```text
  title: 供應鏈在地化的三重摩擦<br>lead: 逆全球化政策面臨結構性阻力<br>cards:<br>- [資本] 支出激增: 赴美建廠資本支出攀升 40%<br>- [生態] 聚落斷層: 缺乏在地化學品與封測即時支援<br>- [人才] 治理文化: 跨國派駐文化與技術工會磨合<br>verdict: 區域化雖提升地緣安全，但實質犧牲三十年累積的極限效率
  ```

### 4. `L-4CARD-GRID`（四象限／四支柱均等網格）
- **使用情境**：4 個平行維度、4 種政策工具或 2×2 的概念平鋪。
- **深度變體**：`grid-2x2`（標準網格）、`numbered-1-4`（帶 01~04 數字水印）。
- **槽位規格**：`title`, `lead` *(選填)*, `cards` *(必填，4 項)*, `verdict` *(選填)*
- **畫面內容範例**：
  ```text
  title: 經濟脅迫的四大工具箱<br>cards:<br>- [關稅] 懲罰性關稅: 針對戰略產業精準加徵<br>- [封鎖] 出口管制: 限制雙用途核心零組件<br>- [審查] 外資限制: 嚴格過濾敏感領域跨境並購<br>- [標準] 監管壁壘: 設置資料在地化與合規門檻
  ```

### 5. `L-BENTO-FOCUS`（便當盒非對稱焦點）
- **使用情境**：1 個最具衝擊力的核心焦點卡（佔較大版面）＋ 2 個次要衍生要點。
- **深度變體**：`left-heavy`（左側大卡）、`top-heavy`（上方通欄大卡）。
- **槽位規格**：`title`, `hero_card` `{tag, head, body}`, `sub_cards` *(2 項)*, `verdict` *(選填)*
- **畫面內容範例**：
  ```text
  title: 戰略安全思維的主導轉變<br>hero_card: {tag: "典範轉移", head: "國家安全壓倒比較優勢", body: "自 2018 年起，主要大國經貿戰略已由追求生產效率全面轉向追求供應鏈去風險與戰略自主。"}<br>sub_cards:<br>- [防護] 友岸外包: 限縮於信任夥伴同盟圈<br>- [備援] 戰略囤儲: 關鍵礦物與晶片戰備存量倍增<br>verdict: 經貿政策已徹底武器化
  ```

### 6. `L-SPLIT-ANCHOR`（1:2 概念錨點式）
- **使用情境**：左側大字粗體核心金句／命題（Anchor），右側垂直列出 2~3 個具體支持條目。
- **深度變體**：`quote-style`（大引號強對比）、`card-list`（卡片序列）。
- **槽位規格**：`title`, `anchor_statement` *(必填)*, `items` *(2~3 項)*, `footer_cite` *(選填)*
- **畫面內容範例**：
  ```text
  title: 相互依存的武器化結構<br>anchor: 誰掌控了網絡的樞紐節點，誰就擁有非對稱的結構性權力。<br>footer_cite: Farrell & Newman (2019)<br>items:<br>- 全球結算管道: 環球銀行金融電信協會 (SWIFT)<br>- 技術核心節點: 極紫外光曝光機 (EUV) 專利網<br>- 關鍵雲端中樞: 跨國海底電纜與超大規模資料中心
  ```

---

## 三、 關係、分類與對抗類（Relational & Contrast）

### 7. `L-VS-CONFRONT`（兩造交鋒對峙）
- **使用情境**：兩派學說、理論對立或政策辯論（中間帶有 VS 徽章）。
- **深度變體**：`split-rail`（中央分割軌道）、`card-versus`（雙色卡片對抗）。
- **槽位規格**：`title`, `issue` *(選填)*, `side_a` `{camp, points}`, `side_b` `{camp, points}`, `ask_or_verdict`
- **畫面內容範例**：
  ```text
  title: 避險還是制衡？台灣戰略抉擇<br>issue: 面对台海局勢升溫，小型行為者的最優戰略為何？<br>side_a: {camp: "全面對美結盟", points: ["獲取最高階安全承諾", "技術標準深度綁定"]}<br>side_b: {camp: "雙重避險策略", points: ["保留市場多元迴旋空間", "避免過早承擔邊緣戰略風險"]}<br>ask_or_verdict: 當安全保證與經濟利益不可兼得時，政策底線在哪裡？
  ```

### 8. `L-MATRIX-DEEPDIVE`（2×2 矩陣＋焦點象限引出）
- **使用情境**：雙維度分類法（Typology），並特別將特定象限放大拉出解讀。
- **深度變體**：`split-note`（左矩陣右解讀）、`floating-callout`（全寬矩陣下浮動條）。
- **槽位規格**：`title`, `axis_x` `{name, low, high}`, `axis_y` `{name, low, high}`, `cells` *(4 項)*, `focus_quadrant` (1..4，或 `none`), `deepdive_note`, `note_label` *(選填)*
- **不預設象限**：類型學若是拿來提問、案例還沒定位，寫 `focus_quadrant: none`，任何一格都不高亮，因為高亮會讓聽眾以為案例已經被放進那一格；右側解讀框的標籤預設是「焦點象限特寫 (Qn)」，沒有焦點時是「解讀」，可用 `note_label` 改寫。
- **畫面內容範例**：
  ```text
  title: 威懾政策矩陣分類<br>axis_x: {name: "承諾明確度", low: "戰略模糊", high: "戰略清晰"}<br>axis_y: {name: "軍事部署烈度", low: "前沿威懾", high: "縱深防衛"}<br>cells:<br>- Q1: 傳統模糊平衡 (現狀)<br>- Q2: 延伸威懾強化<br>- Q3: 刺蝟防衛島鏈<br>- Q4: 全面安全條約<br>focus_quadrant: 3<br>deepdive_note: 本研究聚焦第 3 象限：在維持政治彈性的同時，大幅提升不對稱拒止能力的有效性。
  ```

### 9. `L-SPECTRUM-POLES`（光譜軸線＋端點案例錨定）
- **使用情境**：非二元對立的概念連續體，標記多個案例在此軸線上的相對位置。
- **深度變體**：`gradient-bar`（漸層粗軌道）、`step-pills`（膠囊進度步進）。
- **槽位規格**：`title`, `pole_left`, `pole_right`, `markers` *(2~4 項)*, `verdict` *(選填)*
- **畫面內容範例**：
  ```text
  title: 國家干預程度的政策光譜<br>pole_left: 自由放任自由市場<br>pole_right: 國家資本主義戰略<br>markers:<br>- [label: 早期矽谷, pct: 20, desc: 國防部早期研發補助]<br>- [label: 歐洲晶片法, pct: 55, desc: 補貼與合規性規範]<br>- [label: 產業政策全面主導, pct: 85, desc: 國家大基金與集中採購]<br>verdict: 現代半導體競爭已無純粹自由市場
  ```

---

## 四、 歷時演進與因果推進類（Temporal & Causal Progression）

### 10. `L-FLOW-3STAGE`（三階段機制推演鏈）
- **使用情境**：A 導致 B，B 再觸發 C 的邏輯因果推演。
- **深度變體**：`node-arrow`（節點與箭頭）、`chevron-step`（連續燕尾色帶）。
- **槽位規格**：`title`, `lead` *(選填)*, `stages` *(3 項)*, `verdict` *(選填)*
- **畫面內容範例**：
  ```text
  title: 灰色地帶侵擾的升級機制<br>stages:<br>- 常態化海空巡航: 壓縮預警反應時間與防空識別區心理界線<br>- 法律戰與管轄宣示: 發布海警執法規定，實質挑戰既有現狀權限<br>- 隔離性封控演練: 以演習名義實施局部海空管制與航道干擾<br>verdict: 以切香腸戰術在不跨越戰爭門檻的前提下重塑戰略邊界
  ```

### 11. `L-TIMELINE-RAIL`（軌道式大事記時間軸）
- **使用情境**：依歷史順序梳理 3～5 個關鍵歷史轉折點。
- **深度變體**：`top-rail`（頂部發光軌道）、`alternating`（上下交錯排列）。
- **槽位規格**：`title`, `events` *(3~5 項)*, `takeaway` *(選填)*
- **畫面內容範例**：
  ```text
  title: 美中科技競爭的升級軌跡<br>events:<br>- 2018 年 | 實體清單祭出: 中興與華為通訊業務受限<br>- 2020 年 | 外國直接產品規則: 切斷台積電晶片代工管道<br>- 2022 年 | 1007 出口管制新規: 全面限制高階運算晶片與設備銷往中國<br>- 2024 年 | 同盟多邊協調機制: 荷蘭與日本同步跟進先進光刻機管制<br>takeaway: 管制手段由點狀個別企業懲罰走向體系級全面圍堵
  ```

### 12. `L-CASCADE-FUNNEL`（漏斗層層收斂）
- **使用情境**：宏觀到微觀、或多層次分析框架（體系層 → 國內層 → 決策層）。
- **深度變體**：`stacked-tiers`（梯形階層堆疊）、`concentric-cards`（收斂卡片）。
- **槽位規格**：`title`, `levels` *(3 項)*, `core_focus` *(選填)*
- **畫面內容範例**：
  ```text
  title: 外交政策決策的三層分析架構<br>levels:<br>- 體系層 (Systemic): 大國實力對比結構與無政府狀態下的相對獲益競爭<br>- 國內層 (Domestic): 選民偏好、國會立法約束與關鍵產業利益遊說團體<br>- 領導層 (Individual): 決策者歷史經驗、危機認知基模與風險偏好特質<br>core_focus: 本文聚焦國內層政治如何扭曲體系層的結構性壓力傳導
  ```

---

## 五、 學術批判、文本與實證類（Scholarly Critique & Evidence）

### 13. `L-QUOTE-CRITIQUE`（文獻原話引述＋三重解構）
- **使用情境**：展示原作者經典引文（附頁碼），並從三個面向批判其漏洞。
- **深度變體**：`quote-top`（上引文下三卡）、`quote-left`（左引文右三條）。
- **槽位規格**：`title`, `quote` *(必填)*, `citation` *(必填)*, `critiques` *(必填，3 項；`- [tag] 要點` 或 `- [tag] 標題: 說明`，後者標題與說明都上畫面)*
- **畫面內容範例**：
  ```text
  title: 對「攻勢現實主義」核心假說的批判<br>quote: 無政府狀態迫使所有大國最大化其相對權力，因為這是確保自身生存的唯一安全途徑。<br>citation: Mearsheimer (2001), p. 29<br>critiques:<br>- [前提] 單一偏好假設: 忽略國家除生存外可能追求的經濟繁榮與制度合法性<br>- [實證] 歐洲統合反例: 無法解釋後冷戰歐洲安全共同體內部的自願去武裝化<br>- [邏輯] 螺旋困境忽視: 最大化權力的行動往往加速引發周邊制衡聯盟
  ```

### 14. `L-HYPOTHESIS-TEST`（理論假設 vs 實證落差）
- **使用情境**：理論預期 vs 實證發現的衝突對比（理論謎題）。
- **深度變體**：`contrast-pillars`（對照立柱）、`conflict-flow`（實證矛盾箭頭）。
- **槽位規格**：`title`, `hypothesis`, `finding`, `theoretical_puzzle`
- **發現的標籤**：`finding` 的標籤預設是「實證發現」；原文若只是提出待解釋的現象、沒有做實證，寫 `finding: {label: "待解釋現象", ...}`，和 `hypothesis` 的 `label` 用法相同。
- **畫面內容範例**：
  ```text
  title: 貿易相互依存與衝突機率檢驗<br>hypothesis: {label: "古典自由主義假說", head: "雙邊貿易依存度越高，武力衝突機率越低", logic: "戰爭帶來的經貿損失高於潛在領土收益"}<br>finding: {head: "在特定高技術依賴領域，經濟制裁與衝突頻率顯著上升", status: "實證結果與假說背馳"}<br>theoretical_puzzle: 相互依存並未消除衝突，反而提供了非對稱打擊的新弱點槓桿。
  ```

### 15. `L-STAT-HERO`（單一震撼數據指標）
- **使用情境**：單一巨大數據（110px 大字）配上背景說明與兩大現實意涵。
- **深度變體**：`stat-left`（左側大數字）、`stat-center`（置中大數字）。
- **槽位規格**：`title`, `stat_number`, `stat_label`, `context`, `implications` *(2 項)*
- **畫面內容範例**：
  ```text
  title: 全球高階製程的集中度風險<br>stat_number: 92%<br>stat_label: 台灣佔全球 10 奈米以下先進晶片代工市佔率<br>context: 數據來源：波士頓諮詢公司 (BCG) 2021 年全球半導體供應鏈脆弱性報告<br>implications:<br>- 戰略不可替代性: 全球主要經濟體在技術上高度依賴單一地理節點的安全<br>- 供應鏈脆弱樞紐: 任何局部海空封鎖將引發全球電子產業的即時斷鏈危機
  ```

### 16. `L-DEFN-EXAMPLE`（概念界定與典型例證）
- **使用情境**：術語或新概念界定，同時給出正向典型例證與邊界反例。
- **深度變體**：`dict-card`（詞典式邊框）、`split-cards`（正反例獨立卡）。
- **槽位規格**：`title`, `term`, `etymology`, `formal_definition`, `positive_example`, `negative_boundary`
- **畫面內容範例**：
  ```text
  title: 概念操作化：經濟治國方略<br>term: 經濟治國方略 (Economic Statecraft)<br>etymology: 語源：Baldwin (1985)<br>formal_definition: 行為者運用經濟工具（作為手段）試圖影響其他行為者的營運環境或政策行為（作為目標）的外交行動總和。<br>positive_example: 凍結特定跨國銀行資產以施加外交政策談判壓力。<br>negative_boundary: 純粹基於國內特定產業保護所實施的反傾銷關稅（非外交戰略目標）。
  ```
