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
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(pwd)
  - Bash(ls *)
  - Bash(mkdir *)
  - Bash(cp *)
  - Bash(node --check *)
---

# deck-svg — vector, hand-authored decks (engine layer)

The top layer of the deck model. You author the **slides**; the look comes from
**house-style** and the navigation/print/presenter shell from **deck-runtime**.
You touch neither of those — you compose `<section class="slide">` elements from
the component vocabulary.

```
look      house-style    asset/tokens.css + ENSFont{,-Bold}.woff2   (theme — don't edit here)
runtime   deck-runtime   asset/deck-stage.js + presenter-stage.js  (shell — frozen)
engine    deck-svg       asset/deck.css + deck.html         ← you work here
```

## What's in the box (`template/`, `reference/`)

| File | Role | You edit it? |
|---|---|---|
| `template/deck.html` | The deck you author: `<deck-stage>` with placeholder slides + `#speaker-notes` + the number-counter script. Links `asset/tokens.css` and `asset/deck.css`. | **Yes** — this is the work surface. |
| `template/asset/deck.css` | Component / layout / motion CSS — the slide vocabulary. | Rarely (it's the engine style); extend with a new component if a slide needs one. |
| `reference/slide-patterns.md` | The component cheat-sheet (what classes exist and when to use them). | No. |

## Scaffolding a new deck

The deck pulls from all three layers into one self-contained folder. `$SKILL_DIR`
is this skill's folder; the other layers are sibling skills.

```sh
DST=<unit>                              # the presentation unit's directory, e.g. units/02-presentation-<topic>
mkdir -p "$DST/asset"

# engine: structure + component CSS
cp "$SKILL_DIR/template/deck.html"          "$DST/deck.html"
cp "$SKILL_DIR/template/asset/deck.css"     "$DST/asset/deck.css"

# house-style: theme + font
cp "$SKILL_DIR/../house-style/assets/css/tokens.css"           "$DST/asset/tokens.css"
cp "$SKILL_DIR/../house-style/assets/fonts/ENSFont.woff2"      "$DST/asset/ENSFont.woff2"
cp "$SKILL_DIR/../house-style/assets/fonts/ENSFont-Bold.woff2" "$DST/asset/ENSFont-Bold.woff2"

# deck-runtime: the shell
cp "$SKILL_DIR/../deck-runtime/template/asset/deck-stage.js"      "$DST/asset/"
cp "$SKILL_DIR/../deck-runtime/template/asset/presenter-stage.js" "$DST/asset/"
```

Resulting deck is portable and offline:

```
<unit>/
  deck.html              # you author this
  asset/
    tokens.css           # house-style (theme — swap to re-theme)
    deck.css             # deck-svg (components)
    ENSFont.woff2        # house-style (font, regular ≤500)
    ENSFont-Bold.woff2   # house-style (font, bold ≥600)
    deck-stage.js        # deck-runtime (shell)
    presenter-stage.js   # deck-runtime (presenter)
```

Verify it opens before authoring (see § Run & verify), then replace the
placeholder slides.

## Authoring slides

Each slide is `<section class="slide" style="--chapter:var(--cN)" data-label="…">`.
Compose the body from the component vocabulary in `reference/slide-patterns.md`
(hero, topbar/eyebrow, kicker/lead, cards, grids, `table.cmp`, `blockquote.pull`,
stats, `ul.clean`, flowdiag, inline `svg.art`). Stagger entrance with
`class="rise d1|d2|d3|d4"`. Keep one idea per slide; push detail into speaker
notes.

**Keep look and structure separate (the whole point of the split):**
- Re-theme by editing token *values* in `asset/tokens.css` — never hard-code
  colours in `deck.html`. Use `var(--chapter)`, `var(--text)`, etc.
- Don't paste the `@font-face` or palette back into `deck.html`; they live in
  `tokens.css`.
- Add a genuinely new visual? Add a component class to `asset/deck.css`, don't
  inline a one-off `<style>` blob.

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
  Esc/digits secondary; `F` = fullscreen; `P` = presenter console.
- **Self-check:** `deck.html#debug` — the runtime sets `document.body.dataset`
  `minfont` (`ok` = every arrival's text ≥ 30px @1080p) and `overflow` (`none` =
  nothing escapes its frame). Headless via the global `browser-cdp` skill:
  ```sh
  SHOT=~/.claude/skills/browser-cdp/scripts/shot.sh
  "$SHOT" --dump 'deck.html#debug' | grep -oE 'data-(minfont|overflow)="[^"]*"'
  ```
- **Structure check (no browser):** confirm `deck.html` links `asset/tokens.css`
  + `asset/deck.css`, loads `asset/deck-stage.js` then `asset/presenter-stage.js`,
  and that `#speaker-notes` has one entry per `<section class="slide">`. Run
  `node --check` on the two JS assets.
- **Present / PDF:** `P` pops the presenter console → **開啟簡報視窗** for the
  projector window; **列印投影片** (or browser Print → Save as PDF, enable
  "Background graphics") gives one 1920×1080 slide per page.
- **Note:** `file://` doesn't auto-reload — hard-reload (Cmd+Shift+R) before
  concluding a change did or didn't land.
