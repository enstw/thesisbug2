# deck-svg slide-pattern cheat-sheet

This is the class list. Which class a slide uses is decided by the shape of
its content, which the storyboard row names (deck-plan
`reference/content-shapes.md`), not by this list: start from the map below.

## Shape → pattern

| # | Content shape | Pattern (classes) |
| :--- | :--- | :--- |
| 1 | One claim | `.claim` (+ one `.lead` line beneath) |
| 2 | Definition | `.defn` (`.term` + `.example`) |
| 3 | Theory primer | `.grid.two`/`.three` of `.card` (`.tag` = theory name, `p` = plain-language explanation, `ul.clean` = where it appears) |
| 4 | Two-axis typology | `.matrix` (`.axis-y`, `table`, `.axis-x`; `td.hi` for the highlighted cell) |
| 5 | Spectrum | `.spectrum` (`.marks` > `.mark`, `.bar`, `.ends`) |
| 6 | Two-sided contrast | `.cols.split` of `.colblock`, or `.grid.two` of `.card`; for claims against weaknesses, `.colblock.against` + `.verdict` |
| 7 | Multi-item comparison | `table.cmp` (`caption`, header row, row-header `th`; `.tight` for six or more rows) |
| 8 | Process / causal chain | `.flowdiag` (`.flownode` + `.flowarrow`), or inline `svg.art.dg` for branches or a redrawn source figure |
| 9 | Timeline | `.timeline` of `.tl` (`time`, `b`, `p`) |
| 10 | Levels / hierarchy | `.tiers` of `.tier` (`h3` + `p`) |
| 11 | Numbers | `.stats` of `.stat` (`.stats.four` for four); a worked numerical example goes in `.matrix` |
| 12 | Quotation | `blockquote.pull` + `cite` with page |
| 13 | Discussion question | `.debate` (`.claim`, `.sides` > `.side`, `.ask`) |
| 14 | Section break | `.slide` with `.kicker` only; `.hero` for the title, `.finale` for the close |

No pattern for a shape → add a component class to `template/asset/deck.css`
and run `./fw deck-refresh`, never bend the content into the nearest class.

Every class below is defined in `template/asset/deck.css`. Colours come from
house-style tokens — drive accents off `var(--chapter)` (set per slide via
`style="--chapter:var(--cN)"`, N = 1–4), never hard-coded hex.

## Slide frame
- `<section class="slide" style="--chapter:var(--c1)" data-label="研究背景">` — one 1920×1080 slide. `data-label` shows in the presenter console.
- `.railtop` — the 4-colour gradient bar; drop one in per slide.
- `.topbar` > `.eyebrow` (section kicker, accent) + `.chap` (right-aligned context, `<b>` for emphasis).
- `.content` — vertically-centred body region.

## Entrance
- `.rise` + `.d1`/`.d2`/`.d3`/`.d4` — staggered fade-up; plays when the slide becomes active. Respects `prefers-reduced-motion`.

## Type
Sized for a classroom projector at 1920×1080: body 40px, tables / labels / captions 34px at least, `.hero__hint` key hints the only smaller text (presenter chrome). `deck.html#debug` reports anything under 34px.
- `.title` (76px) / `.kicker` (56px) — headline; `.hl` inside = accent colour.
- `.lead` (40px) — body paragraph; `strong` = bright, `em` = accent (not italic).
- `.muted` — dimmed; `.mt` — top margin.

## Layout containers
- `.grid.two` / `.grid.three` — equal-column grid.
- `.cols.split` — two centred columns (e.g. text + art).

## Components
- `.card` (+ `.tag`, `h3`, `p`, `ul.clean`) — bordered panel with accent top-rule.
- `table.cmp` — comparison table at 34px (`caption`, `thead th`, row-header `tbody th`); `.tight` halves the cell padding for six or more rows, instead of shrinking the text. Past about four columns × five rows, split it across slides.
- `blockquote.pull` (+ `cite`) — large pull quote with accent bar.
- `.stats` > `.stat` (`.n` number, `.l` label) — metric trio; `.n` with `data-to="47.2"` animates the count on arrival; `.stats.four` for four figures.
- `ul.clean` (+ `.lead-size`) — dotted bullet list with accent markers.
- `.flowdiag` > `.flownode` / `.flowarrow` — left-to-right process diagram.

## Content-shape components (see § Shape → pattern for when)
- `.claim` (+ `.hl`) — one statement, 64px; an optional `.lead` beneath.
- `.defn` > `.term` (`h3` + `small` + `p`) and `.example` (`b` label + `p`) — term, definition, example.
- `.matrix` > `.axis-y`, `table` (`thead th` column values, `tbody th` row values, `td` cells, `td.hi` highlight, `td.dim`), `.axis-x` — 2×2 / 3×3 typology or payoff matrix.
- `.spectrum` > `.marks` (`.mark` with `style="left:NN%"`, `b` + `span`), `.bar`, `.ends` — continuum with marked positions.
- `.timeline` > `.tl` (`time`, `b`, `p`) — equal-width dated columns on a rail.
- `.tiers` > `.tier` (`h3` + `p`) — stacked levels, top = highest.
- `.debate` > `.claim`, `.sides` > `.side` (`h3` + `p`), `.ask` — contested claim, two positions, the question to the room.

## Inline SVG art
- `svg.art` — responsive inline SVG (vector-crisp; keep CJK as `<text>`, never rasterize).
- `svg.art.dg` — a redrawn source figure in theme colours: `.box` (`.hi` outlined, `.fill` tinted), `.edge` (`.off` dashed) with `.ah` arrowheads, `.seg` (`.big`/`.mid`/`.small`) for shares, `.kline` threshold line; `text` is 34px, `.sub` secondary, `.acc` chapter colour, `.b` bold. Size the viewBox to the slide pixels the figure fills so the text is not scaled down.
- `.cols.split` of `.colblock` (`h3` + `ul.clean`) — two text columns; `.colblock.against` on the rebuttal column keeps its heading neutral, and a `p.verdict` (with `em`) under the columns closes on the judgment.
- Loop animation hooks: `.flow` (dashed stroke march), `.pulse` (`.b`/`.c` = phase offsets), `.aurora` (slow drift). All freeze under `prefers-reduced-motion` and in print.
- `.art-cap` — centred caption under art.

## Special slides
- `.hero` — title slide: `.hero__layers` (`.grid-layer` + aurora SVG), `.hero__inner` (`h1`, `.hero__sub`, `.hero__meta`), `.hero__hint` (key hints).
- `.finale` — centred closing slide (結論 / Q&A): `h2` + `.onesentence`.

## Discipline
- New visual need → add a component class to `deck.css`, don't inline a one-off `<style>`.
- Re-theme → edit token values in `asset/tokens.css` only.
- Keep `#speaker-notes` one entry per slide, in order.
