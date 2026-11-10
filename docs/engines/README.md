# Slide engine previews

The images in this directory show what each slide engine makes of **the same storyboard row**. They are the previews in the top-level [`README.md`](../../README.md). The talk is an invented one about brewing tea, so nothing here comes from coursework.

| File | Engine | What it shows |
| :--- | :--- | :--- |
| `deck-svg.png` | deck-svg, compiled by `./fw deck-compile` | the row as a live HTML slide, `projector-light` theme, every step revealed |
| `deck-svg-lively.gif` | deck-svg, lively mode | the same slide revealing one beat per key press (`M-STEP`) |
| `deck-image.jpg` | deck-image | the row as one generated full-bleed image |
| `deck-3d.gif` | deck-3d | the camera flying from the section title into the row's first scenes, `Esc` to the overview map, and a click on a tile there |
| `deck-slidev.png` | deck-slidev | the row as a Slidev slide (default theme) |
| `beamer.png` | Quarto Beamer fallback | the row as a Beamer frame, with the section bar on top |

These are screenshots and recordings of running engines, not diagrams: there is no text source a viewer could render them from, so they are committed as images. Replace them when an engine's look changes.

## The source

A scratch course with one unit and one talk, whose `storyboard.md` is:

```markdown
# 分鏡稿

## 前提

- 標題：泡一壺茶
- 聽眾：第一次泡茶的人
- 場地與投影：教室投影機；淺色、高對比主題；字級下限 34px。
- Seed: 7

## 投影片

| # | 來源論點 | 內容形狀 | 版型 | 動態 | 講 | 畫面內容 | 講者備註 | AI 協助 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0 | P0 | 封面 | L-HERO-TITLE | — | 1 min | title: 泡一壺茶<br>sub: 從茶葉、水溫到時間<br>meta: thesisbug2 · 引擎示範 | — | 示範 |
| 1 | P1 | 章節 | L-HERO-TITLE | — | 1 min | title: 一、認識茶葉<br>sub: 發酵程度決定泡法 | — | 示範 |
| 2 | P2 | 分類 | L-3CARD-VERDICT | M-STEP | 2 min | label: 一、認識茶葉 · 對象：第一次泡茶的人<br>title: 茶葉依發酵程度分三類，發酵越重，水溫越高<br>lead: 水溫決定苦澀與香氣：同一把茶葉，差十度就是兩種味道<br>cards:<br>- [綠茶] 不發酵: 用 80°C 左右的水，浸泡一到兩分鐘；水太燙，苦澀會先跑出來<br>- [烏龍茶] 部分發酵: 用 90 到 95°C 的水，先溫潤泡再正式沖；葉片舒展後香氣才出來<br>- [紅茶] 全發酵: 沸水直沖，浸泡三分鐘；耐泡，適合加奶<br>verdict: 先看發酵程度，再決定水溫與時間<br>verdict_label: 口訣 | — | 示範 |
| 3 | P3 | 數字 | L-STAT-HERO | M-COUNT | 1 min | title: 綠茶最怕燙<br>stat_number: 80°C<br>stat_label: 沖泡綠茶的建議水溫<br>context: 沸水離火後靜置約三分鐘<br>implications:<br>- 太燙: 苦澀先跑出來，香氣被蓋住<br>- 太涼: 葉片泡不開，茶湯淡而無味 | — | 示範 |
| 4 | P4 | 章節 | L-HERO-TITLE | — | 1 min | title: 二、動手沖泡<br>sub: 三個步驟，一壺好茶 | — | 示範 |
| 5 | P5 | 流程 | L-FLOW-3STAGE | M-STEP | 2 min | title: 沖泡的三個步驟<br>stages:<br>- 溫壺: 先用熱水燙過茶壺與茶杯，倒掉<br>- 沖泡: 依茶葉種類注入對應水溫的水，計時<br>- 分杯: 時間一到全部倒出，不讓茶葉繼續泡<br>verdict: 時間到就倒乾，下一泡才不會苦 | — | 示範 |
```

Row 2 (`L-3CARD-VERDICT`) is the one every preview shows. The other rows give the 3D flight a section to start from and the Beamer section bar something to list.

## How each preview was made

All commands run from the scratch course root; `<talk>` is the talk directory.

1. **`deck-svg.png`.** `./fw deck-compile <talk>`, then `./fw deck-notes <talk>`. The deck was opened in a headless Chromium at 1280×720 with `data-deck-theme-default="projector-light"` on `<html>`, moved to the slide, stepped four times with the right arrow key so every `M-STEP` beat is visible, and captured with the DevTools protocol (`Page.captureScreenshot`).
1. **`deck-svg-lively.gif`.** The same deck with lively mode switched on (`M`). The motion was slowed to a quarter (`gsap.globalTimeline.timeScale(0.25)`) so that screenshots, which take tens of milliseconds each, sample it smoothly; the frames were taken with `Page.captureScreenshot` while the beats played, and ffmpeg assembled them at 10 frames per second:

    ```bash
    ffmpeg -framerate 30 -i f%04d.jpg -vf "select='not(mod(n,2))',setpts=N/10/TB,fps=10,tpad=stop_mode=clone:stop_duration=2.5,scale=560:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=full[p];[b][p]paletteuse=dither=none:diff_mode=rectangle" deck-svg-lively.gif
    ```

1. **`deck-3d.gif`.** `./fw deck-3d <talk>` (6 rows become 2 islands and 13 scenes), then `<talk>/deck3d/index.html` in the same browser. Animations were slowed with `Animation.setPlaybackRate` at 0.25 and one screenshot was taken every 400 ms, which is a tenth of a second of deck time, so the frames play back at 10 per second with no frame selection. The recording starts on the first section title, advances two scenes into the row, presses `Esc` for the overview map, moves the pointer to another section's first tile and clicks it (`Input.dispatchMouseEvent`, so the page receives a real click). The frames were assembled with the filter above from `scale` onward, a 48-colour palette and a two-second hold on the last frame.
1. **`deck-slidev.png`.** `./fw deck-slidev <talk>`, then in `<talk>/slidev/`:

    ```bash
    pnpm install
    pnpm exec slidev export slides.md --format png --output export --executable-path <chromium>
    ```

1. **`deck-image.jpg`.** One Codex image generation (deck-image, route 1) from a prompt that names the layout (kicker, headline, lead, three cards, takeaway), the look (watercolour on warm off-white paper, one accent colour) and every string of row 2 verbatim. The Traditional Chinese text in the result was proofread against the row before it was kept.
1. **`beamer.png`.** The presentation template's `_quarto.yml` and `preamble.tex` (`assets/templates/presentation/`) with `{{FW}}` filled in, a `presentation.qmd` whose `#` headings are the talk's sections and whose `##` frame holds row 2 as a table, then `quarto render presentation.qmd --to beamer` and one page of the PDF rasterised with Ghostscript.

The PNG files were reduced to 255 colours without dithering (`magick … +dither -colors 255`), which keeps flat areas flat.

The capture scripts are not in this repository. They are a few dozen lines around a DevTools-protocol client, and any tool that can press keys and take screenshots in a headless browser (Playwright, Puppeteer) reproduces them.
