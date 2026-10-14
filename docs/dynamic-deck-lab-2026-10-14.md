# 動態簡報工作流試驗：2026-10-14

靜態簡報（`deck-plan` → `deck-svg`／`deck-image`，開 `file://` 上台）之外，另開一條比較活潑的**動態簡報**工作流：畫面隨口白逐句揭露，可輸出成影片，也可在瀏覽器自播或現場逐句操作。本文是第一次試驗的交接摘要：在一門課的期中口頭報告單元裡，用一個自寫的極簡引擎做出 2.8 分鐘的 PoC（前 5 段口白），作者看過後決定這條線值得開展，下一步要用現成框架試做；候選、評比與建議順序見文末；維護者 2026-10-14 同意先試 Remotion。試驗程式留在該課程 repo（私有）的 02 單元 `tools/video/`，commit `805a9eb`；本文只收框架層可移植的部分，不含課程內容。

## 做了什麼

```mermaid
flowchart LR
  M[Model：報告段落 pN.M] --> S[口白稿 video-script.md<br>每段標來源段落與秒數上限]
  S --> T[TTS 逐段 mp3<br>Edge TTS zh-TW]
  S --> J[timeline.json<br>每段每句的起訖秒]
  T --> J
  J --> E[video.html 場景引擎<br>seek(t) 定格]
  E --> F[CDP 逐幀截圖 PNG]
  F --> V[ffmpeg 合成 MP4<br>＋拼接音軌]
  T --> V
```

1. 口白稿由報告段落改寫成口語，只刪不增，每段標來源段落編號與秒數上限（受單一事實來源規則約束，改內容先改報告）。
1. `build-video.py` 用 `uvx edge-tts` 逐段合成 mp3；同一份稿量過四種語音與語速，全稿 15 至 19 分鐘不等。
1. `build-scenes.py` 讀稿與音檔長度，把每段切句、依字數比例估每句起訖秒，寫成 `timeline.json`；起本機 HTTP 給引擎讀。
1. `video.html` 是 1920×1080 的普通網頁。每個場景用 JS 建 DOM／SVG 元素，每個元素掛一筆「第幾秒開始、幾秒內完成、什麼效果」。關鍵是 `seek(t)`：給一個秒數就把整個畫面擺到該狀態，不靠瀏覽器自己的時間流逝，所以每一幀可重現。
1. `render-scenes.mjs` 用 Chrome DevTools Protocol 開無頭 Chromium，迴圈呼叫 `seek(t)` 並截圖；ffmpeg 把 PNG 序列編成 H.264 接上音軌。

| 項目 | 量測 |
| :--- | :--- |
| PoC 長度 | 5 段口白，166.7 秒 |
| 幀數與渲染時間 | 5,001 幀（30 fps），約 10 分鐘（CDP 單分頁截圖約 8 至 9 fps） |
| 輸出 | MP4 27 MB，H.264 CRF 19，AAC 160k |
| 引擎大小 | `video.html` 126 行，渲染腳本 21 行，建置腳本 42 行，無第三方相依 |

## 引擎契約（可移植）

- **定格函式**：`seek(t)` 冪等，只依 t 計算，不累積狀態。幀的來源因此可以換：時鐘加音檔（自播）、鍵盤（現場逐句）、捲動位置（網頁說明）、渲染迴圈（影片）。
- **場景**：`(seg, root) => {items, update?}`。`items` 每筆 `{el, at, dur, fx}`；`fx` 有 `fadeup`、`pop`、`draw`（SVG 路徑畫線）、`type`（逐字）、`count`（數字遞增）。`update(tl)` 給連續動畫（例如沿路徑移動的封包）。
- **時間點取自口白**：`seg.cue(k)` 回第 k 句的起始秒，`seg.cueMatch(regex)` 回第一句符合者的起始秒。場景只說「唸到『第二』時出第二張卡」，不寫死秒數，口白一改時間自動跟著變。
- **段間**：0.6 秒交叉淡入，前一景同時推進到 1.04 倍；整段有 4% 的緩推鏡頭。
- **字幕**：底部逐句燒入，36px、左右各留 120px，一行約 46 個全形字。

`timeline.json` 的結構：

```json
{"segments":[{"index":0,"title":"…","start":0.0,"audio":14.568,"total":15.568,
  "cues":[{"text":"第一句。","start":0.4,"end":2.184},{"text":"第二句。","start":2.184,"end":12.292}]}]}
```

`start` 是全片絕對秒，`total` 含段前 0.4 秒與段後 0.6 秒留白；`cues` 的秒數是段內相對秒。

引擎核心去掉場景後長這樣：

```js
const FX = {
  fadeup:(it,p)=>{it.el.style.opacity=p; it.el.style.transform=`translateY(${(1-easeOut(p))*36}px)`},
  pop:   (it,p)=>{it.el.style.opacity=p; it.el.style.transform=`scale(${.82+.18*easeOut(p)})`},
  draw:  (it,p)=>{const L=it.len; it.el.style.strokeDasharray=L; it.el.style.strokeDashoffset=L*(1-easeOut(p))},
  type:  (it,p)=>{it.el.textContent=it.text.slice(0,Math.round(it.text.length*p))},
  count: (it,p)=>{it.el.textContent=it.fmt(Math.round(it.n*easeOut(p)))},
};
function seek(t){
  const idx = TL.segments.findIndex(s => t < s.start + s.total);
  const sc = SCENES[idx], seg = sc.seg, tl = t - seg.start;
  SCENES.forEach((s,i)=>{ s.root.style.display = (i===idx || (i===idx-1 && tl<.6)) ? 'block' : 'none' });
  const xf = idx>0 ? clamp(tl/.6) : 1;                                  // 交叉淡入
  sc.root.style.opacity = xf; if (idx>0) SCENES[idx-1].root.style.opacity = 1-xf;
  sc.root.style.transform = `scale(${1 + .04*clamp(tl/seg.total)})`;   // 整段緩推
  for (const it of sc.items) FX[it.fx](it, clamp((tl-it.at)/it.dur));  // 逐項揭露
  if (sc.update) sc.update(tl);                                         // 連續動畫
  const cue = seg.cues.find(c => tl>=c.start && tl<c.end);
  sc.root.querySelector('.cap').textContent = cue ? cue.text : '';     // 字幕
}
```

渲染端只有一個迴圈：`seek(t)` 後 `Page.captureScreenshot`，寫 PNG；最後 `ffmpeg -framerate 30 -i frame-%06d.png -i track.wav -c:v libx264 -crf 19 -pix_fmt yuv420p -c:a aac -movflags +faststart`。

## 踩到的坑

1. **網頁字型競態**：`document.fonts.ready` 在畫面上還沒有任何文字時就會 resolve，首批幀因此沒有字。要在建場景前對每個字重 `document.fonts.load("600 30px 'Font'")` 強制載入再等 `fonts.ready`。任何以網頁為畫布的渲染都會遇到，Motion Canvas 也要驗證。
1. **絕對定位卡片要 `box-sizing:border-box`**，否則 left 加 width 不等於實際佔位，卡片互相重疊。
1. **字幕與內容相撞**：每個場景底部要預留約 170px（兩行字幕）；單句超過 90 字會折成三行，切句時應連「；」也切，或限制單句長度。
1. **渲染吞吐**：CDP 單分頁 PNG 截圖約 8 至 9 fps，15 分鐘全片要近一小時。各段互相獨立，可多分頁平行，或先出低 fps 冒煙版檢查版面再全速算。
1. **逐句秒數是估的**：依字數比例配時與實際語音有偏差，揭露時機與字幕會提早或延後。正式版要用 whisperx 或 stable-ts 對音檔做強制對齊。
1. **轉場要放在留白裡**：目前交叉淡入與下一段第一句的 0.4 秒前導重疊，字幕會疊在轉場上。轉場應落在前一段的尾端留白，口白開始時畫面已乾淨。
1. **Edge TTS** 是免費但非官方的端點，zh-TW 語音唸英文原句口音生硬；課堂可用，公開發布或長期依賴應換作者自錄或正式服務。英文句可另用 en-US 語音合成後拼接。
1. **`file://` 下 `fetch('timeline.json')` 會被擋**。若要像靜態 deck 一樣雙擊即開，時間軸要照 `deck-theme-rules.js` 的做法包成 `.js` 指派，音檔用 `<audio src>` 相對路徑即可。

## 與框架現有決定的關係

- **MVC 不變**。Controller（`points.md`、`storyboard.md`）仍決定順序、版型與口說重點；動態簡報只是另一種 View。畫面文字一律由報告段落參照取得、只刪不增，口白稿也標段落編號，所以 `pararef` 式的涵蓋檢查可以同樣跑在影片上。
- **深度變化與主題**仍由 house-style 的色票規則與字型子集化管；本試驗直接沿用 deck 的字型與色票，視覺上與靜態版是同一家。
- **投影片時間不驅動刪減**的決定對現場版仍成立；影片版則相反，口白超時就刪句子不加快語速。兩條線的差別在此，應寫進 presentation-protocol 的動態版分支，而不是改動靜態版規則。

## 若繼續自養引擎的路線圖

1. **多種驅動**：同一個 HTML 加 `<audio>` 與 requestAnimationFrame 就是會自己講的網頁簡報；加鍵盤逐句前進且不播音檔就是上台版。一份來源同時產出投影片、旁白影片、現場報告。
1. **語音對齊**取代字數比例，順便做逐字高亮字幕。
1. **宣告式場景規格**：幾種版型（封面、研判加要點卡、時間軸、流程圖、對照、引文、表格）加段落參照，由產生器回報告取字，不再手寫 JS；這一步之後 agent 新增一段只要寫幾行規格。
1. **搬進框架**當共用資產並加 `fw` 子命令；單元只留口白稿與場景規格。原因是 `./fw update` 會覆寫 `.claude/skills`，留在單元裡的工具每門課都要複製一次。
1. **輸出端**：按段平行渲染；指定某段輸出 GIF 迴圈；每句結尾各出一張 PNG 當講義；整份輸出 PDF。

### 轉場語彙

只準備四種，各有固定意義，不追求花樣；轉場只發生在口白留白裡，絕不在觀眾該讀字時移動文字；進場 ease-out、鏡頭 ease-in-out，0.4 至 0.8 秒。

1. **淡入**（預設）：同章換話題。
1. **推進**：同章內的順序關係，方向固定，讀成「接下來」。
1. **鏡頭推入元素**：進入細節，例如從時間軸某節點放大接到該事件的機制圖；回總結時反向拉遠。
1. **章節卡**：換章暫停一拍，全暗出章名約 1.5 秒。

比轉場更有力的是**跨景延續**：元素不消失只改位置。兩條時間軸合成一條長線由鏡頭平移；結尾要點卡從原位滑回形成首尾呼應；流程圖切換版本時方塊不動只換封包行為。實作用 FLIP：相鄰兩景中同一個 `data-id` 的元素量出位置差再內插。

## 下一步：候選工具與建議順序

四個候選放在同一張表上比，評比項目取自上面的坑與框架規則。Motion Canvas 在討論中先被點名，但只是舉例；依這張表，**建議先試 Remotion**，Motion Canvas 第二，自養引擎是已經能動的退路。維護者 2026-10-14 同意此順序。

| 項目 | 自養引擎（本試驗） | Remotion | Motion Canvas | Revideo（Motion Canvas 分支） |
| :--- | :--- | :--- | :--- | :--- |
| 畫面怎麼畫 | 瀏覽器 DOM／CSS | 瀏覽器 DOM／CSS（React 元件，無頭 Chrome 逐幀截圖） | HTML5 Canvas 2D | HTML5 Canvas 2D |
| 中文排版 | 瀏覽器版面引擎：自動換行、避頭尾、中英混排都是現成的 | 同左 | `Txt` 節點自己量字排版，換行與標點規則有限，**要先驗證** | 同 Motion Canvas |
| 沿用 deck 的字型與色票 | 直接沿用 | 直接沿用（CSS 原樣），`@remotion/fonts` 的 `loadFont()` 會等字型就緒，正好解掉字型競態 | 要另寫 | 要另寫 |
| 無頭／命令列渲染 | 自寫 CDP 迴圈，可行 | 內建 `remotion render`，可指定並行數，進 `fw build` 最順 | 以編輯器為主，命令列渲染待查 | 主打程式化與無頭渲染 |
| 旁白對齊與字幕 | 要自己接 whisper | `@remotion/install-whisper-cpp` 加 `@remotion/captions` 直接出逐字時間與字幕 | 時間事件在編輯器拖到波形上對齊，可手調但要逐句拖 | 同 Motion Canvas 的時間事件 |
| 自播網頁與現場模式 | 同一個 HTML 加 `<audio>` 與鍵盤即可 | `@remotion/player` 把同一支影片元件嵌進網頁播放；現場逐句模式要自己加 | 編輯器可播，獨立自播頁要另外做 | 同左 |
| 轉場與鏡頭 | 要自己寫四種轉場與 FLIP | `@remotion/transitions`（fade、slide、wipe、flip）；鏡頭用 CSS transform | 內建 slide／zoom／fade 轉場與 `Camera` 節點，這是它最強的一項 | 同 Motion Canvas |
| 授權 | 無 | 個人、三人以下公司與非營利免費，含商業用途；四人以上公司要買授權；5.0 版授權條款預告會微調 | MIT | MIT |
| 維護與生態 | 自己 | 活躍、版本密集、文件齊 | 版本更新在 3.x 後明顯放慢，最新版號與維護狀態本次查不到，**要先確認** | 較年輕、社群小 |
| 代價 | 整張路線圖都要自己做 | 要吃 React 與 Node 工具鏈，專案比 126 行重得多 | TypeScript 加 Vite，generator 寫時序要學一套 | 同左 |

判斷的核心只有一條：這條工作流的畫面是**由 agent 依 storyboard 產生的文字密集場景**，不是人手逐格調的動態圖形。文字密集就要瀏覽器的版面引擎，所以 DOM 系（Remotion、自養）勝過 Canvas 系（Motion Canvas、Revideo）；要進 `fw build` 就要命令列渲染，Remotion 又勝過自養。Motion Canvas 的優勢在人手調動畫的編輯器體驗與內建鏡頭，若日後要做的是片頭或機制示意這類手工動畫，再用它補那幾段。

### Remotion（建議先試）

`useCurrentFrame()` 就是本試驗的 `seek(t)`：元件只依目前幀號算畫面，同樣冪等、同樣可逐幀重現，所以引擎契約那一節的思路可以原樣搬過去，`<Sequence from={幀} durationInFrames={幀}>` 對應每段，`interpolate` 與 `spring` 對應 `FX`。

| 官方寫法 | 本機 |
| :--- | :--- |
| `npx create-video@latest` | `pnpm create video@latest` |
| `npx remotion studio` | `pnpm exec remotion studio`（預覽與時間軸） |
| `npx remotion render <id> out.mp4 --concurrency 4` | `pnpm exec remotion render <id> out.mp4 --concurrency 4` |
| `npm i @remotion/transitions @remotion/captions @remotion/player @remotion/fonts` | `pnpm add …` |

第一天要驗證的五件事，依風險排序：

1. **中文排版與字型**：把 deck 的 `tokens.css` 與字型原樣套進去，確認換行、避頭尾、字型載入（`loadFont()` 配 `delayRender()`）與 1920×1080 畫布下的字級。
1. **旁白對齊**：用既有的逐段 mp3 跑 whisper.cpp，拿到逐字時間，確認中文辨識品質足以切句；若不足，退回「逐句比例估時加人工修」。
1. **命令列渲染**：`remotion render` 在本機無頭跑通，量 1080p 每秒幾幀、並行數開到多少最划算；這決定 `fw` 子命令的形狀。
1. **自播網頁**：`@remotion/player` 把同一支元件嵌進一頁 HTML，確認 `file://` 下能否開（它是打包後的 JS，應可），以及音檔同步。
1. **授權確認**：以個人或非營利身分使用符合免費條款；框架是公開的，要在文件寫明四人以上公司使用需自行取得授權，並留意 5.0 版條款。

### Motion Canvas（第二候選）

優點：MIT、TypeScript、場景即程式（generator 寫時序，`yield*` 一行一動作），內建 `slideTransition`／`zoomInTransition`／`fadeTransition` 與自訂轉場，2D 套件有 `Camera` 節點可做「鏡頭推入元素」，`waitUntil('事件名')` 的時間事件可在編輯器裡拖到音檔波形上對齊，3.8 版起新專案預設帶 FFmpeg 匯出器可直接出 MP4。

| 官方寫法 | 本機 |
| :--- | :--- |
| `npm init @motion-canvas@latest` | `pnpm create @motion-canvas@latest` |
| `npm install` ／ `npm start` | `pnpm install` ／ `pnpm start`（編輯器在 `http://localhost:9000`） |
| `npm install @motion-canvas/ffmpeg` | `pnpm add -D @motion-canvas/ffmpeg`，並在 `vite.config.ts` 註冊為 plugin |

若試它，第一天同樣先驗證：`Txt` 的中文換行與標點、`@font-face` 字型就緒、`makeProject({scenes, audio})` 匯入旁白與 `waitUntil` 事件能否由腳本從對齊結果直接寫入（據我所知事件存在場景旁的 `.meta` 檔，未查證）、命令列渲染是否可行（不行就用瀏覽器自動化開編輯器觸發，或改用 Revideo）、含音軌 MP4 與 PNG 序列的輸出。另外先到官方 GitHub 看最新 tag 與日期，確認維護狀態。

### 兩者共同的內容流

單一事實來源不變：`storyboard.md` → 產生 `scenes.json`（只含版型代碼與段落參照）→ 少數通用場景元件讀 JSON 畫面；文字不寫死在 TSX 或 TS 檔。時間軸仍由口白稿與音檔算出，對齊後再寫入各框架的時間結構。

參考：[Remotion 授權與價格](https://www.remotion.dev/docs/pricing)、[Remotion LICENSE.md](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md)、[Motion Canvas 3.8.0 發布說明](https://motioncanvas.io/blog/version-3.8.0)、[Motion Canvas 3.15.0](https://motioncanvas.io/blog/version-3.15.0/)、[Rendering video](https://motioncanvas.io/docs/rendering/video)、[Time events](https://motioncanvas.io/docs/time-events)、[Revideo FFmpeg exporter](https://docs.re.video/api/core/exporter/FFmpegExporterClient)、[三者比較](https://www.pkgpulse.com/guides/remotion-vs-motion-canvas-vs-revideo-programmatic-video-2026)。

## 轉向：現場鍵控版（2026-10-14 下午）

維護者看過上面的評比後改了方向：先不做 TTS 與影片輸出，場景改成**教室投影機上的現場報告**，講者按一次「下一步」鍵就播下一個動作；工具只用免費或有免費方案的；而且**不受既有 deck-runtime 約束**，先做一個獨立的原型看 looks and feel，合適了才考慮與 `deck-stage` 整合。原型放在同一門課的 02 單元 `tools/motion/live.html`（私有 repo），雙擊即開（`file://`），字型與色票直接連結該單元的 `asset/tokens.css`，所以 14 套主題用 C 鍵就能切，投影機淺色主題也在內。

引擎與上面的 `seek(t)` 同一套效果，只把時間軸換成**拍（beat）**：每個元素標在第幾拍出現，`→` 播下一拍，拍播完再按就進下一景；`←` 瞬間退一拍，或回到上一景的全展開狀態。七個場景把 PoC 契約裡的強項都放進展示：

1. 封面：事件句逐字打出，標題彈入。
1. 研判：主句加三張要點卡逐拍出現。
1. 章節卡轉場（全暗出章名）進入「一、指控內容」。
1. 上半年時間軸：線畫出、節點逐拍彈入。
1. 推進轉場加跨景延續：上半年的三個節點縮成小點滑進 9 月時間軸的左側邊欄（同 `data-id` 的元素量出位置差再內插，FLIP）。
1. 鏡頭推入 9/10 節點，接到轉送流程圖：主線畫出、方塊彈入、封包沿線流動，講到「回應送回來」才多出回程。
1. 流程圖裡的小字「5,380」長成下一景的大數字，其餘三個數字遞增；結尾景把封面標題與研判三張卡從它們原來的位置滑回來（跨景延續不限相鄰景：來源在更早的景時暫時排版那一景量位置）。

四種轉場（fade／push／zoom／chapter）由上一景宣告，文字不重疊：前景先在前半段淡出、後景在後半段淡入。鏡頭隨拍數緩推 4%。`prefers-reduced-motion` 下全部瞬間完成。

若作者接受這個 look and feel，整合的方向是：把「拍」做成靜態 deck 的漸進增強（投影片元素標 `data-beat`、`data-fx`，由一支新的 engine 腳本在 `deck-stage` 的 `→` 之前攔截，拍未播完就不換頁；講者視窗顯示第幾拍），縮圖、列印與 `#debug` 檢查一律全展開；轉場與跨景延續則需要 `deck-stage` 多一個換頁前的可取消事件。這些都還沒做。

**完結（2026-10-14 晚）**：維護者看過原型後裁定，要留下的是引擎帶來的特色而不是版面，於是這整套進了框架，成為靜態 deck 的選用活潑模式：deck-svg 新增 `asset/deck-motion.js`（屬性詞彙見該 skill § Motion and print），deck-runtime 只多一個換頁前的可取消事件 `deckstep` 與講者視窗的拍數顯示，`docs/DESIGN.md` 有決定條目。`live.html` 留在課程單元當參考；這門課的 `deck.html` 前七頁已標上拍與延續作為實證。

## 引擎 PoC：四個引擎跑同一套七景（2026-10-14 深夜）

活潑模式定案後，維護者問為什麼投影機情境不能用 Remotion、Motion Canvas、GSAP、anime.js，並要求把 Motion Canvas 的簡報模式也納入。於是把原型的七景與效果宣告抽成引擎契約（`scenes.js` 宣告「哪個元素第幾拍、什麼效果」，`shell.js` 管縮放、HUD、按鍵、主題，引擎只實作 `init / goTo / next / prev / reverse? / replay? / speed?`），同一套場景跑四個引擎：手寫、GSAP 3.15、anime.js 4.5（三者 `file://` 雙擊即開）、Motion Canvas 3.17（七景用 TSX 重寫，走它的 Presenter）。對照表、數字與踩到的坑在課程單元 `tools/motion/README.md`；這裡只記對框架有意義的結論。

| | 手寫（＝deck-motion.js 的路線） | GSAP | anime.js | Motion Canvas |
| :--- | :--- | :--- | :--- | :--- |
| 引擎碼／函式庫 | 86 行／0 | 89 行／121 KB | 80 行／118 KB | 305 行／133 MB `node_modules`＋Vite |
| 授權 | — | 免費含外掛，非 MIT | MIT | MIT |
| 動畫倒退、變速 | ✗ | ✓ | ✓ | ✗（倒退＝重跑到上一拍末狀態） |
| 跨景延續 | 自己量 | Flip 外掛 | 自己量 | 無，手動放座標 |
| `file://`、主題沿用 | ✓ | ✓ | ✓ | ✗ |

1. 手寫路線站得住：七景的全部效果 86 行、零相依，正是活潑模式進框架時的規模；沒有一個引擎讓同樣的效果更短。
1. GSAP 是記錄在案的後繼，這次實測確認了對應關係：Flip、DrawSVG、SplitText 對 `data-id`、`draw`、`chars` 一對一，多出來的是動畫式倒退、重播、全域變速，代價是 121 KB 與非 MIT 的免費授權。什麼時候換：講者要「倒放這一拍」而不是瞬間退的時候。
1. anime.js 沒有 GSAP 做不到的事，又少了 Flip；不列候選。
1. Motion Canvas 的簡報模式是真的（`beginSlide` 一拍一個、拍清單側欄、鍵控、全螢幕），逐字、畫線、數字遞增、三種轉場都有原生寫法，先前擔心的中文換行其實沒問題（它用隱藏 DOM 量尺寸再畫到 Canvas）。擋住它的是別的：要開發伺服器、不能 `file://`、tokens.css 的 14 套主題不能沿用、`Camera` 的子節點不在座標鏈上導致淡入時文字被切（3.17.2）、最後一版 2025-02。它適合從零做的影片或簡報，不適合疊在既有靜態 deck 上。`docs/DESIGN.md` 活潑模式條目的理由據此修正。

