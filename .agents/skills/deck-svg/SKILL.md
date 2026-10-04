---
name: deck-svg
description: >
  Authors a vector presentation deck of live SVG/HTML slides (selectable text,
  entrance animations, speaker notes), suited to Traditional Chinese seminar,
  thesis, and reading-guide talks. Use when the user wants to build, extend, or
  edit a slide deck / 簡報 / presentation. Scaffolds a self-contained, offline,
  no-build deck from a fixed component vocabulary on the house-style look and
  deck-runtime shell; use it instead of hand-rolling reveal.js, Marp, or raw
  HTML. For slide-as-image decks use deck-image.
---

# deck-svg — vector, hand-authored decks (engine layer)

The top layer of the deck model. You author the **slides**; the look comes from
**house-style** and the navigation/print/presenter shell from **deck-runtime**.
You touch neither of those — you compose `<section class="slide">` elements from
the component vocabulary.

```
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
| `reference/content-shapes.md` | Content shape → pattern: which layout fits what kind of material, the storyboard format, and the anti-patterns. Read **first**. | No. |
| `reference/slide-patterns.md` | The component cheat-sheet (what classes exist). | No. |

## Scaffolding a new deck

The deck pulls from all three layers into one self-contained folder. `$SKILL_DIR`
is this skill's folder; the other layers are sibling skills.

```sh
DST=<unit>                              # the presentation unit's directory, e.g. units/02-presentation-<topic>
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
<unit>/
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
reaches them. `./fw deck-refresh <unit> [--dry-run]` re-copies every file in
`asset/` above from the current skills (the map `unit-init` uses), lists each
as new / updated / unchanged, skips one with uncommitted changes, and never
writes `deck.html`, `storyboard.md` or any other author file. Because
`deck.html` is yours, it only prints the `<script>`/`<link>` tags the current
starter loads and your deck lacks, with where each goes; add them by hand. A
local edit to an `asset/` file is replaced (it shows in `git diff`), so put a
needed component or theme into the framework's skill instead.

## Storyboard before slides

The deck is the bottom of one chain — report `draft.qmd` (every claim cited)
→ `points.md` (~8–12 points, each naming its report section) → storyboard →
`deck.html` — and nothing enters a lower layer that the layer above lacks,
because that is what lets every slide sentence trace back to a cited report
sentence; fix an error at the highest layer that has it, then carry it down
(the presentation protocol's § Source Files has the rules).

Write `<unit>/storyboard.md` (scaffolded by `unit-init`) before `deck.html`.
It opens with a bullet list of **前提** — title (main title + subtitle),
audience, time limit, room and projection (type floor, theme), wording
conventions — because those set type size, pace and terms for every slide.
Then one table row per slide with the point it condenses, its **content
shape** (numbered in `reference/content-shapes.md`), the pattern, the minutes, **畫面內容** (what is
on the slide), **口說重點** (explanation, citations with locators, transitions,
anticipated questions — the talk lives in the notes once the slide is sparse,
so the author reviews it here and it becomes `#speaker-notes` when the deck is
built — never derive the notes from the slides, which are the sparsest
layer), and **AI 協助** (what AI drafted or verified, what the author wrote or
changed), because courses increasingly ask for per-slide AI disclosure and it
is reliable only when recorded as the slide is planned. The author reviews the
storyboard; `deck.html` is written only after that sign-off.

The shape column exists because an agent choosing layouts from the class list
picks whatever is easiest to type — bullets, cards, `table.cmp` — and then
trims or reshapes the content to fit, so a 3×3 typology becomes a list and the
examples disappear. **The shape of the content chooses the layout; if no
pattern fits, add a component to `deck.css`, never bend the content.**
Putting the choice in a table the author reads makes a bad fit visible before
the slide exists. `./fw build` checks that the storyboard is there and that the
deck does not lean on one pattern (`table.cmp` share, bullets per slide); it
cannot judge fit — that is the review.

## Authoring slides

Each slide is `<section class="slide" style="--chapter:var(--cN)" data-label="…">`.
Compose the body from the pattern the storyboard names, using the classes in
`reference/slide-patterns.md` (claim, defn, matrix, spectrum, timeline, tiers,
debate, cards, grids, `table.cmp`, `blockquote.pull`, stats, `ul.clean`,
flowdiag, inline `svg.art`). Stagger entrance with
`class="rise d1|d2|d3|d4"`. Keep one idea per slide, graspable in about ten
seconds, because the audience is listening while it reads; detail goes to the
speaker notes. Time never justifies cramming or pre-cutting — the presenter
adjusts pace or skips slides live.

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
try `c` in the room before the talk. Colours come only from tokens, so a slide
that hard-codes one stays put when the theme changes.

**Speaker notes:** keep the `#speaker-notes` JSON array in lockstep with slide
order — one string per `<section>`, same sequence.

**Cited content:** follow `../house-style/reference/content-integrity.md`
(disputed claims stay disputes, speculation is labeled, citations stay attached).

Deeper slide-craft (font subsetting for a smaller deliverable, verification
discipline, worked examples) is in the project's
`assets/templates/presentation/presentation-protocol.md` — the upstream prose
this engine was carved out of; consult it for anything not covered here.

## Run & verify

- **Run:** open `deck.html` directly — no build, no server. Click = next; arrows/
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
- **Structure check (no browser):** `./fw deck-refresh <unit> --dry-run`
  reports stale assets and any tag the current starter loads that the deck
  does not. Otherwise confirm `deck.html` links `asset/tokens.css`
  + `asset/deck.css`, loads `asset/deck-check.js`, `asset/deck-theme-rules.js`,
  `asset/deck-palette.js` and `asset/deck-theme-controls.js` first (because
  deck-stage rewrites the `#debug` / `#theme=` hash to the slide number as it
  starts), then `asset/deck-stage.js`, `asset/presenter-stage.js` and
  `asset/deck-font-controls.js`, and that `#speaker-notes` has one entry per
  `<section class="slide">`. Run `node --check` on the seven JS assets and
  `./fw check-contrast <unit>` on the deck's `tokens.css`.
- **Present / PDF:** `P` pops the presenter console → **開啟簡報視窗** for the
  projector window; **列印投影片** (or browser Print → Save as PDF, enable
  "Background graphics") gives one 1920×1080 slide per page.
- **Note:** `file://` doesn't auto-reload — hard-reload (Cmd+Shift+R) before
  concluding a change did or didn't land.
