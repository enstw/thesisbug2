# deck-svg slide-pattern cheat-sheet

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
- `.title` (76px) / `.kicker` (56px) — headline; `.hl` inside = accent colour.
- `.lead` (34px) — body paragraph; `strong` = bright, `em` = accent (not italic).
- `.muted` — dimmed; `.mt` — top margin.

## Layout containers
- `.grid.two` / `.grid.three` — equal-column grid.
- `.cols.split` — two centred columns (e.g. text + art).

## Components
- `.card` (+ `.tag`, `h3`, `p`, `ul.clean`) — bordered panel with accent top-rule.
- `table.cmp` — comparison table (`caption`, `thead th`, row-header `tbody th`).
- `blockquote.pull` (+ `cite`) — large pull quote with accent bar.
- `.stats` > `.stat` (`.n` number, `.l` label) — metric trio; `.n` with `data-to="47.2"` animates the count on arrival.
- `ul.clean` (+ `.lead-size`) — dotted bullet list with accent markers.
- `.flowdiag` > `.flownode` / `.flowarrow` — left-to-right process diagram.

## Inline SVG art
- `svg.art` — responsive inline SVG (vector-crisp; keep CJK as `<text>`, never rasterize).
- Loop animation hooks: `.flow` (dashed stroke march), `.pulse` (`.b`/`.c` = phase offsets), `.aurora` (slow drift). All freeze under `prefers-reduced-motion` and in print.
- `.art-cap` — centred caption under art.

## Special slides
- `.hero` — title slide: `.hero__layers` (`.grid-layer` + aurora SVG), `.hero__inner` (`h1`, `.hero__sub`, `.hero__meta`), `.hero__hint` (key hints).
- `.finale` — centred closing slide (結論 / Q&A): `h2` + `.onesentence`.

## Discipline
- New visual need → add a component class to `deck.css`, don't inline a one-off `<style>`.
- Re-theme → edit token values in `asset/tokens.css` only.
- Keep `#speaker-notes` one entry per slide, in order.
