# Motion catalog — 動態變化目錄

分鏡表的「動態」欄填這裡的代碼，一頁一個（最多再加一個轉場）。它決定活潑模式（deck-svg § Lively mode）裡這一頁怎麼逐拍出現；`./fw deck-compile` 會把能自動加的代碼變成 `data-beat`／`data-fx`／`data-enter` 屬性，要手寫的代碼留在分鏡當作意圖，由 deck-svg 的作者加屬性。沒有這一欄、或填 `—`，投影片就是靜態的，整頁一次出現。

機器讀的版本在 `scripts/_deck_motion.py`（`VARIATIONS`）；測試檢查這份文件列了裡面的每個代碼。

## 怎麼選

兩條路，二選一：

1. **自己列舉**：寫分鏡時照下表挑，依「適合」與「代價」兩欄。
1. **交給 Jev**：`./fw deck-motion-pick <talk>` 把每一頁變成一題選擇題（只列編譯做得到的代碼），連同前提、規則與整份投影片順序送給 Jev（jev-decide 技能的 runner，付費，要作者確認後加 `--ack`），答案寫回「動態」欄；全場規則（M-SCRAMBLE 只用一次、M-ZOOM 最多兩次、不連續推進）在送出後由腳本補套並列出改了哪幾頁。沒有 runner 時它仍會產生題目檔，可以手答再用 `--answers` 餵回去。

選完跑 `./fw deck-compile <talk>`，再開 `deck.html` 按 `M` 看。

## 代碼

| 代碼 | 台下看到什麼 | 編譯會自動加 | 適合 | 代價 |
| :--- | :--- | :--- | :--- | :--- |
| `M-STEP` | 版型原本的進場順序改成一拍一組：標題、導語隨頁出現，每張卡／節點／階層按一次出一個，收束框最後 | ✓ | 預設；任何版型 | 卡多的頁要按很多下 |
| `M-POP` | 同 M-STEP，方塊類元素縮放彈入 | ✓ | 卡片、流程節點、階層、時間軸 | 段落文字不適合；連頁用會膩 |
| `M-TYPE` | 導語逐字打出，其餘同 M-STEP | ✓ | 一句話撐起的頁 | 長句打太久；只對純文字元素 |
| `M-CHARS` | 標題逐字彈入，其餘同 M-STEP | ✓ | 封面、分節、結論 | 一份簡報三次以內 |
| `M-LINES` | 標題整行從遮罩下升起，其餘同 M-STEP | ✓ | 正式場合、多行標題 | 單行短標題看不出差別 |
| `M-COUNT` | 大數字從 0 遞增（保留前後綴、千分位） | ✓ `L-STAT-HERO` | 數字頁 | 口徑不同的數字並列時遞增會誤導 |
| `M-SCRAMBLE` | 大數字從亂碼解出 | ✓ `L-STAT-HERO` | 全場唯一的關鍵數字 | 一次就夠；台下要等它解完 |
| `M-PUSH` | 進頁時前一頁往左推出 | ✓ | 同一主題連續幾頁 | 連用會暈；主題換了不要推 |
| `M-ZOOM` | 前一頁放大推入（手寫 `data-zoom-from` 可指定從哪個元素） | ✓ | 從總覽進細節 | 一兩次；真的是上一頁的細節才用 |
| `M-DRAW` | SVG 線條自己畫出 | 手寫 `data-fx="draw"` | 自繪流程圖、時間軸軌道 | 版型目錄的流程與時間軸是 DOM，不是 SVG |
| `M-PACKET` | 元素沿 SVG 路徑循環移動 | 手寫 `data-along`（加 `data-rotate` 跟著轉向） | 資料流 | 要手寫路徑與封包 |
| `M-CONTINUE` | 同 `data-id` 的元素從前一頁位置滑過來 | 手寫兩頁的 `data-id` | 圖裡的小字長成下一頁的大數字 | 兩頁都要標 |
| `M-REGROUP` | 同一批卡片換 class 重排，從舊位置飛到新位置 | 手寫 `data-relayout="n:cls …"` | 同樣的事實換個分類 | 要寫兩套版面 class |
| `M-MORPH` | SVG path 變形成另一個形狀 | 手寫 `data-morph="n:#sel …"` | 概念轉換（標籤→鏈） | 要畫兩個以上形狀 |
| `M-NONE` | 不標拍，整頁一次出現 | ✓（什麼都不加） | 分節頁、引文頁、一句話的頁 | — |

## 全場的節制規則

- 每頁一個代碼；要加轉場就再寫一個 `M-PUSH` 或 `M-ZOOM`（例：`M-POP M-PUSH`）。
- `M-SCRAMBLE` 全場一次，`M-ZOOM` 最多兩次，連續兩頁不要同一種轉場——花俏的效果用第二次就失效。
- 台下約十秒要看懂一頁；拍越多講者按越多次，不確定就選較克制的（`M-STEP`、`M-NONE`）。
- 版型的收束框永遠是最後一拍；編譯會把拍號壓成連續的，不會有「按了沒反應」的空拍。

## 編譯後長什麼樣（手寫投影片時照這個寫）

`M-STEP` 把版型的 `.rise d1`–`.d4` 讀成拍號：沒有 dN 的是第 0 拍（隨頁），dN 是第 N 拍，再壓成連續。`M-POP` 給 `.card`、`.tl`、`.flownode`、`.tier` 等方塊加 `data-fx="pop"`；`M-TYPE` 給 `.lead`／`.hero__sub`／`.onesentence` 加 `data-fx="type" data-dur="1.6"`；`M-CHARS`／`M-LINES` 給 `h1`／`h2` 加 `data-fx="chars"`／`"lines"`；`M-COUNT`／`M-SCRAMBLE` 給 `.stat-hero__num` 加 `data-beat="1" data-fx="count"`／`"scramble"`；`M-PUSH`／`M-ZOOM` 給 `<section>` 加 `data-enter`。元素保留原本的 class，引擎執行時自己拿掉 `.rise`。完整屬性表在 deck-svg SKILL.md § Lively mode。
