---
name: deck-svg
description: >
  Renders a talk's signed-off deck-plan storyboard as live SVG/HTML slides
  (selectable text, entrance animations, speaker notes) for Traditional
  Chinese seminar, thesis, and reading-guide talks. Use to build, extend, or
  edit a slide deck / 簡報 once its storyboard exists. Scaffolds a
  self-contained, offline, no-build deck from a fixed component vocabulary on
  the house-style look and deck-runtime shell, instead of reveal.js, Marp, or
  raw HTML. For slide-as-image decks use deck-image.
---

# deck-svg — vector, hand-authored decks (engine layer)

The engine layer of the deck model. You author the **slides**; what each one
says comes from the storyboard written with **deck-plan**, the look from
**house-style**, and the navigation/print/presenter shell from **deck-runtime**.
You change none of those here — you compose `<section class="slide">` elements
from the component vocabulary.

```
plan      deck-plan      points.md + storyboard.md                  (what each slide says — signed off first)
look      house-style    asset/tokens.css + ENSFont{,-Bold}.woff2   (themes — don't edit here)
runtime   deck-runtime   asset/deck-stage.js + presenter-stage.js  (shell — frozen)
engine    deck-svg       asset/deck.css + deck-font-controls.js + deck-theme-controls.js + deck-check.js + deck.html  ← you work here
```

## What's in the box (`template/`, `reference/`)

| File | Role | You edit it? |
|---|---|---|
| `template/variants/<thesis\|reading-guide>/deck.html` | The starter deck you author: `<deck-stage>` with placeholder slides + `#speaker-notes` + the number-counter script. Links `asset/tokens.css` and `asset/deck.css`. | **Yes** — this is the work surface. |
| `template/asset/deck.css` | Component / layout / motion CSS — the slide vocabulary. | Rarely (it's the engine style); extend here with a new component if a slide needs one, then `./fw deck-refresh`. |
| `template/asset/deck-font-controls.js` | Deck-wide font size: `+`/`=` and `-` step `--deck-font-scale` by 10% (80–150%), remembered per deck and synced across its windows. | No. |
| `template/asset/deck-theme-controls.js` | Live colour: `c`/Shift+C cycle the fixed themes in `tokens.css`, `g`/Shift+G generate or step back through seeded palettes; `#theme=<id>` or `#theme=r<seed>` loads one. Remembered per deck and synced across its windows like the font size. Needs house-style's `deck-theme-rules.js` + `deck-palette.js` loaded before it. | No. |
| `template/asset/deck-check.js` | The `deck.html#debug` self-check (type floor, overflow, rendered contrast, § Run & verify); does nothing without `#debug`. | No. |
| `reference/slide-patterns.md` | Content shape → pattern (read **first**: the storyboard row names the shape), then the component cheat-sheet. | No. |

## Scaffolding a new deck

The deck pulls from all three layers into one self-contained folder. `$SKILL_DIR`
is this skill's folder; the other layers are sibling skills.

```sh
DST=<talk>                              # a presentation unit root or units/NN-*/talks/<occasion>
mkdir -p "$DST/asset"

# engine: structure + component CSS
cp "$SKILL_DIR/template/variants/thesis/deck.html" "$DST/deck.html"   # or variants/reading-guide
cp "$SKILL_DIR/template/asset/deck.css"     "$DST/asset/deck.css"
cp "$SKILL_DIR/template/asset/deck-font-controls.js" "$DST/asset/"
cp "$SKILL_DIR/template/asset/deck-check.js" "$DST/asset/"
cp "$SKILL_DIR/template/asset/deck-theme-controls.js" "$DST/asset/"

# house-style: theme + font
cp "$SKILL_DIR/../house-style/assets/css/tokens.css"           "$DST/asset/tokens.css"
cp "$SKILL_DIR/../house-style/assets/fonts/ENSFont.woff2"      "$DST/asset/ENSFont.woff2"
cp "$SKILL_DIR/../house-style/assets/fonts/ENSFont-Bold.woff2" "$DST/asset/ENSFont-Bold.woff2"
cp "$SKILL_DIR/../house-style/assets/themes/deck-theme-rules.js"  "$DST/asset/"
cp "$SKILL_DIR/../house-style/assets/themes/deck-palette.js"      "$DST/asset/"

# deck-runtime: the shell
cp "$SKILL_DIR/../deck-runtime/template/asset/deck-stage.js"      "$DST/asset/"
cp "$SKILL_DIR/../deck-runtime/template/asset/presenter-stage.js" "$DST/asset/"
```

Resulting deck is portable and offline:

```
<talk>/
  deck.html              # you author this
  asset/
    tokens.css           # house-style (all themes; deck-refresh updates it)
    deck.css             # deck-svg (components)
    deck-font-controls.js # deck-svg (+/− font size)
    deck-theme-controls.js # deck-svg (c / g live themes)
    deck-check.js        # deck-svg (#debug self-check)
    deck-theme-rules.js  # house-style (palette rules, one source)
    deck-palette.js      # house-style (contrast check + seeded generator)
    ENSFont.woff2        # house-style (font, regular ≤500)
    ENSFont-Bold.woff2   # house-style (font, bold ≥600)
    deck-stage.js        # deck-runtime (shell)
    presenter-stage.js   # deck-runtime (presenter)
```

Verify it opens before authoring (see § Run & verify), then replace the
placeholder slides.

**Updating an existing deck.** The copies in `asset/` are frozen at scaffold
time so the deck opens offline, which also means a framework update never
reaches them. `./fw deck-refresh <talk> [--dry-run]` re-copies every file in
`asset/` above from the current skills (the map `unit-init` uses), lists each
as new / updated / unchanged, skips one with uncommitted changes, and never
writes `deck.html`, `storyboard.md` or any other author file. Because
`deck.html` is yours, it only prints the `<script>`/`<link>` tags the current
starter loads and your deck lacks, with where each goes; add them by hand. A
local edit to an `asset/` file is replaced (it shows in `git diff`), so put a
needed component or theme into the framework's skill instead.

## Start from the storyboard

deck-svg renders the **Views** of a talk: each `<section>` and its
`#speaker-notes` entry is written from one row of the signed-off
`<talk>/storyboard.md` and the declared Model passage that row's point names. The
storyboard and `points.md` are the Controller, written with **deck-plan**
before this skill starts; without a signed-off storyboard, plan first. The
split exists because choosing what to say while laying out slides is how a
deck ends up saying things the declared Model does not.

- The row's content shape picks the pattern (`reference/slide-patterns.md`
  § Shape → pattern) or a layout catalog code (`L-*` from `deck-plan`'s
  `reference/layout-catalog.md`). **If no pattern fits, add a component to `deck.css`;
  never bend the content**, because an agent choosing from the class list
  takes the easiest pattern and trims the content to fit — a 3×3 typology
  becomes a list and the examples disappear.
- When using layout catalog codes with slot micro-syntax in `storyboard.md`, run
  `./fw deck-compile <talk>` to compile the slides automatically and deterministically
  with seeded depth variants (preview all combinations live with `./fw deck-compile --explorer`).
  You can still hand-edit or extend `deck.html` afterwards.
- Write the note's 講法 in `<talk>/speaker-notes.md` from the row's 口說重點
  and the Model passage, never from the slide, because the slide is the
  sparsest View and a note rebuilt from it loses the explanations and the
  locators. `./fw deck-notes <talk> --init` seeds the file;
  `./fw deck-notes <talk>` adds the unit glossary and Q&A entries the row names and
  writes `#speaker-notes` (presentation protocol § Speaker notes). Do not
  write term explanations or answers into the 講法: they are facts, and they
  belong in `<unit>/notes/glossary.md` and `<unit>/notes/qa.md`, where the gates check them.
- A fact that turns out wrong while building is corrected in its owning
  factual layer (Model or unit backup knowledge), then in the rows and slides
  that use it; an order or emphasis change goes back to the storyboard
  (presentation protocol § Source Files).

## Authoring slides

Each slide is `<section class="slide" style="--chapter:var(--cN)" data-label="…">`.
Compose the body from the pattern the storyboard names, using the classes in
`reference/slide-patterns.md` (claim, defn, matrix, spectrum, timeline, tiers,
debate, cards, grids, `table.cmp`, `blockquote.pull`, stats, `ul.clean`,
flowdiag, inline `svg.art`). Stagger entrance with
`class="rise d1|d2|d3|d4"`. Keep one idea per slide, graspable in about ten
seconds, because the audience is listening while it reads; detail goes to the
speaker notes, and a prose-heavy passage becomes a short on-slide statement
with the full detail in the note. Time never justifies cramming or
pre-cutting — the presenter adjusts pace or skips slides live.

**Keep look and structure separate (the whole point of the split):**
- Never hard-code colours in `deck.html`; use `var(--chapter)`, `var(--text)`,
  etc. To start the deck on a theme other than theme 1, set it on the root
  element — `<html lang="zh-Hant" data-deck-theme-default="projector-light">`
  — with a theme id from `--deck-themes` or a seed (`r4821`). Set it when the
  room is known, e.g. a lit classroom → a light theme, because the first slide
  is what the audience sees before anyone presses `c`. Precedence: `#theme=` in
  the URL > the viewer's stored `c`/`g` choice > this default > theme 1. A new
  theme or palette goes into house-style's `tokens.css`, not the deck's copy,
  which `deck-refresh` replaces.
- Don't paste the `@font-face` or palette back into `deck.html`; they live in
  `tokens.css`.
- Add a genuinely new visual? Add a component class to this skill's
  `template/asset/deck.css` and run `./fw deck-refresh`, don't inline a
  one-off `<style>` blob — an edit made only to the deck's `asset/deck.css`
  is lost at the next refresh, and other decks never get the component.
- Keep body text at 40px and nothing the audience reads below 34px (tables,
  labels, captions; the stock components already comply), because type that
  reads on a laptop washes out on a classroom projector. Only presenter chrome
  such as the title slide's key hints is smaller.
- Write every text size as `calc(<n>px * var(--deck-font-scale, 1))`, in
  `deck.css` and in any inline style, because a bare `px` size ignores the
  `+`/`−` keys and is left behind when the presenter resizes for the room.

**Design for the projector, not the laptop.** Spend free space on larger
type, a diagram, a primary-evidence screenshot, or a small table (about four
columns × five rows at most) rather than on whitespace, because the back row
reads size, not elegance. When content does not fit, split the slide rather
than cramming it or shrinking the type. Keep contrast high — no muted-grey
secondary text, no thin weights — since projectors wash out low-contrast text;
in a lit classroom a light theme usually projects better than a dark one, so
before the talk project one dark and one light slide from the back row and
keep whichever reads (`c` cycles the themes live; house-style lists them). Colours come only from tokens, so a slide
that hard-codes one stays put when the theme changes.

**Speaker notes:** `#speaker-notes` is generated — edit `speaker-notes.md`
and rerun `./fw deck-notes`, because the next assembly overwrites a hand edit
in `deck.html`. Adding, removing or moving a slide means renumbering the
sections of `speaker-notes.md` and the storyboard rows to match; `deck-notes`
compares each section's label with the slide's `data-label` and refuses a
mismatch, since an unnoticed shift attaches every later note to the wrong
slide.

**Cited content:** follow `../house-style/reference/content-integrity.md`
(disputed claims stay disputes, speculation is labeled, citations stay attached).

## Diagrams and art

A deck is plain HTML with **no Mermaid runtime**: a ` ```mermaid ` block shows
as literal text, so use one of these instead.

1. **Hand-authored inline SVG** — the default for deck art and simple process
   chains (`.flowdiag`, `svg.art.dg`). Strokes and fills use `var(--chapter)`
   or `currentColor`, so the art follows the theme.
1. **PlantUML → SVG** for structured diagrams kept as source (the **diagram**
   skill): render with `./fw plantuml2svg`, commit both files, and inline the
   SVG markup into the `<section>` so it scales with the canvas and inherits
   theme colour, or `<img src="<name>.svg">` it. The Quarto `![](…)` figure
   form is for `.qmd` documents, not the deck.
1. **Raster art** (painterly or photographic backgrounds, textures) comes from
   supplied images or Codex image generation — the provider exception the
   framework `AGENTS.md` records; report the asset as pending when no backend
   works instead of switching providers. Save it under `<talk>/` so the deck
   stays self-contained, and name the deck's palette and mood in the prompt,
   because a bitmap cannot inherit `--chapter` and must be regenerated when
   the theme changes. Diagrams and icons stay SVG; whole-slide bitmaps are
   deck-image's job.

## Hard rules

These hold on every slide, so verification does not depend on an external
design skill:

1. SVG icons and illustrations only — never emoji, which render differently
   per system and cannot take the theme colour.
1. Every animation is disabled under `prefers-reduced-motion` (the starter's
   `@media` block); transitions run 150–300 ms, eased.
1. Contrast: body text ≥ 7:1 and labels, muted and accent text ≥ 4.5:1 in
   every theme the deck offers, stricter than WCAG AA because projection
   washes contrast out. The numbers live only in house-style
   `deck-theme-rules.js`; `./fw check-contrast` checks the tokens and `#debug`
   the rendered slides.
1. Art is theme-aware (`--chapter` / `currentColor`), never a hard-coded
   one-off accent.
1. Any interactive element (a link, a button) has a visible focus state and
   `cursor:pointer`.

## Motion and print

The starter wires the deck's motion: `.rise` entrance with `.d1`–`.d4`
stagger, replayed when a slide becomes active; cheap looping SVG transforms
(`.flow`, `.pulse`, `.aurora`); a count-up on `.stat .n[data-to]`. Keep its
`@media print` block in every deck you author:

```css
@media print {
  .rise { opacity:1 !important; transform:none !important; animation:none !important; }
  .flow,.pulse,.aurora { animation:none !important; }
}
```

`.rise` starts at `opacity:0` and reveals only on the active slide, and
deck-stage's print CSS can force the `<section>`s visible but not their
descendants, so without this block Print → Save as PDF emits one real slide
and blank pages for the rest.

The deck ships the full ENSFont, so any Traditional Chinese renders without
tofu; subsetting it to shrink a final file is optional (house-style § Font).

## Run & verify

- **Run:** open `deck.html` directly — no build, no server. To check the
  presenter's slide thumbnails, serve the unit over HTTP
  (`python3 -m http.server 8000` in the unit directory), because Chrome blocks
  them over `file://`; notes and navigation work either way. Click = next; arrows/
  Esc/digits secondary; `F` = fullscreen; `P` = presenter console; `+`/`−` =
  whole-deck font size; `c`/Shift+C = next/previous fixed theme; `g`/Shift+G =
  new seeded palette / previous one (toast 「隨機 #4821」; `#theme=r4821`
  reloads it). All of these also work from the presenter console; Cmd/Ctrl +/−
  stays browser zoom. Print uses the active theme.
- **Self-check:** open `deck.html#debug` and step through every slide.
  `asset/deck-check.js` checks each slide once its entrance animation ends and
  sets `document.body.dataset` `minfont` (`ok` = all visible text on the
  checked slides ≥ 34px at 1920×1080 design size, else `small`) and
  `overflow` (`none` = no text leaves the slide, no `.content` overflows into
  the header, no clipping container cuts text, else `found`); offenders are
  listed in `minfontBad` / `overflowBad` as `<slide number> <element> <px>`,
  checked slide numbers in `checked`, and on the console. It also sets
  `contrast` (`ok` = every visible text ≥ the label floor, 4.5:1, against its
  composited background, else `low`, offenders in `contrastBad`);
  `contrastNote` lists body-size text (38–42px nominal) under the body floor,
  7:1, and `contrastUnknown` text over an image, which is reported rather than
  guessed. Thresholds come from `asset/deck-theme-rules.js`. `+`/`−`, `c` and
  `g` reset the results and recheck the current slide; combine as
  `#debug&theme=paper`. Use the available browser tools; if
  `browser-cdp` is installed, read its discovered `SKILL.md` for the current
  capture commands.
  Do not assume a home-directory path, because agents install skills differently.
  Without browser access, run the structure check and mark visual QA as pending.
- **Structure check (no browser):** `./fw deck-refresh <talk> --dry-run`
  reports stale assets and any tag the current starter loads that the deck
  does not. Otherwise confirm `deck.html` links `asset/tokens.css`
  + `asset/deck.css`, loads `asset/deck-check.js`, `asset/deck-theme-rules.js`,
  `asset/deck-palette.js` and `asset/deck-theme-controls.js` first (because
  deck-stage rewrites the `#debug` / `#theme=` hash to the slide number as it
  starts), then `asset/deck-stage.js`, `asset/presenter-stage.js` and
  `asset/deck-font-controls.js`, and that `#speaker-notes` has one entry per
  `<section class="slide">`. Run `node --check` on the seven JS assets and
  `./fw check-contrast <talk>` on the deck's `tokens.css`. In a browser
  console, notes alignment is
  `document.querySelectorAll('deck-stage>section').length` against
  `JSON.parse(document.getElementById('speaker-notes').textContent).length`,
  with no empty string among the notes.
- **Reduced motion:** emulate `prefers-reduced-motion: reduce` and confirm
  every `.rise` is visible and the loops stop.
- **Present / PDF:** with the projector as an extended screen, `P` puts the
  deck fullscreen on the projector and the presenter console on the laptop
  screen (Chromium-based browsers; allow the one-time window-management
  prompt, then press `P` again if the console did not open). Browser Print →
  Save as PDF (enable "Background graphics") gives one 1920×1080 slide per page; check there is
  no key-hint overlay and no trailing blank page. For the `_output/<unit>.pdf`
  name or Pandoc-rendered references, use the Beamer fallback instead.
- **Note:** `file://` doesn't auto-reload — hard-reload (Cmd+Shift+R) before
  concluding a change did or didn't land.
