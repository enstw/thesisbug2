---
name: house-style
description: >
  The shared look every presentation and paper engine draws from: the ENSFont
  CJK font, deck design tokens (tokens.css), the CJK xelatex preamble fragment,
  and the content-integrity rules for cited academic work. A base library the
  deck and paper engines copy from when scaffolding. Invoke directly only to
  change the house look or the content rules (palette, font, quoting and
  dispute-handling rules).
---

# house-style — the shared look (base skill)

This skill owns the parts of the look that are **common across formats**, so an
engine never re-decides them and a change lands in one place. It is the bottom
of a three-layer model:

```
look      house-style          font · tokens · CJK preamble · content rules
runtime   deck-runtime         the <deck-stage> HTML shell (nav/print/presenter)
engine    deck-svg, deck-image, deck-beamer   one skill per engine
```

Each reason to change lives in exactly one layer: change the **theme** → edit
house-style tokens; change the **navigation/print** → edit deck-runtime; change
**how slides are produced** → edit the engine skill.

## What's in the box (`assets/`, `reference/`)

| Path | Role | Consumed by |
|---|---|---|
| `assets/fonts/ENSFont.woff2` + `ENSFont-Bold.woff2` | Full-glyph CJK web font, Regular + real Bold (no tofu, no subsetting needed). | deck-svg, deck-image |
| `assets/css/tokens.css` | `@font-face` + design tokens: theme 1 on `:root`, the other fixed themes as complete token sets on `:root[data-deck-theme="<id>"]`, key order in `--deck-themes`. **Theme = token values.** | every deck engine (linked as `asset/tokens.css`) |
| `assets/themes/deck-theme-rules.js` | Every palette rule (pairs, thresholds, colour-vision ΔE, generator ranges), JSON in a `.js` wrapper because a `file://` deck cannot fetch JSON. | `./fw check-contrast`, `deck-palette.js` |
| `assets/themes/deck-palette.js` | The same checker in JS plus the seeded OKLCH palette generator. | deck-svg (`asset/`) |
| `assets/tex/preamble-cjk.tex` | xeCJK font + Chinese line-breaking fragment. | deck-beamer, paper engines |
| `reference/content-integrity.md` | Disputed-claims / speculation / citation / do-not-misphrase rules for graded work. | every engine that renders cited content |

This skill is the **canonical home for ENSFont (web).** The old duplicate
copies (presentation scaffold, retired engines) were removed — house-style is
now the one source of `ENSFont.woff2`. The xelatex **`.ttf`** still lives at the framework's
`assets/fonts/ENSFont-Regular.ttf` because the Beamer build (template-based,
not yet a skill) consumes it via `preamble.tex`'s `Path=../assets/fonts/`; it
moves into `assets/fonts/` here when **deck-beamer** is built and the build path
is rewired. `assets/tex/preamble-cjk.tex` documents the fragment for that step.

## How an engine draws from house-style (the convention)

Skills have **no native import**, so the dependency is by convention: an engine
skill's scaffold step copies what it needs out of this skill's `assets/`. Sibling
skills resolve as `$SKILL_DIR/../house-style/…`. Typical deck scaffold:

```sh
HS="$SKILL_DIR/../house-style/assets"
cp "$HS/css/tokens.css"             <deck>/asset/tokens.css
cp "$HS/fonts/ENSFont.woff2"        <deck>/asset/ENSFont.woff2
cp "$HS/fonts/ENSFont-Bold.woff2"   <deck>/asset/ENSFont-Bold.woff2
cp "$HS/themes/deck-theme-rules.js" "$HS/themes/deck-palette.js" <deck>/asset/
```

The engine links `asset/tokens.css` from its `deck.html` and ships the font
beside it. The produced deck is **self-contained** (a frozen copy of the look at
scaffold time); `./fw deck-refresh <unit>` re-pulls the latest look into an
existing deck. That is the "central source + frozen instance" model — update
here, adopt per deck with deck-refresh.

## Changing the house look

- **Theme / palette / type:** edit token *values* in `assets/css/tokens.css`
  only — never the component or motion CSS (that lives in the engines). Existing
  decks adopt it with `./fw deck-refresh <unit>`. A deck's own `asset/tokens.css`
  is a copy that deck-refresh replaces, so a deck picks its starting theme with
  `data-deck-theme-default` in `deck.html` (deck-svg) instead of editing it.
- **Themes and contrast:** 14 fixed themes, 7 dark (夜幕 default, 石墨, 深海,
  森夜, 暮紫, 黑板, 投影高對比・暗) and 7 light (投影高對比・亮, 紙白, 米黃, 霧藍,
  石灰, 薄荷, 杏粉), because classroom lighting cannot be tested before the talk;
  the two 投影高對比 themes are for a washed-out projector. A theme defines every
  colour token in the rules file so no dark default leaks into a light theme.
  After any token edit run `./fw check-contrast` (exit 1 on failure); change a
  threshold only in `deck-theme-rules.js`, since Python and the deck both read it.
  To keep a seeded palette someone liked on stage (toast 「隨機 #4821」), run
  `./fw check-contrast --emit r4821` (needs `node`; without it, open the deck at
  `#debug&theme=r4821` and copy the block from the console), paste the block
  into `tokens.css`, give it an id and `--theme-name`, and add the id to
  `--deck-themes`.
- **Citation style:** the CSL files do NOT live here — their canonical home is
  the framework's `assets/`: `apa.csl` (paper & thesis default), `apa-zh-TW.csl`
  (paper option, `./fw unit-init --citation apa-zh`, with `multibib.lua`), and
  `chicago-fullnote-bibliography.csl` (journal & preparation). Each template's
  `_quarto.yml` wires its CSL as `csl: ../assets/<name>.csl`. They migrate into
  this skill if/when **deck-beamer** is built and starts consuming them.
- **Font:** replace the four artifacts together so web decks and xelatex
  stay identical — `assets/fonts/ENSFont.woff2` + `ENSFont-Bold.woff2`
  (here) and the framework's `assets/fonts/ENSFont-Regular.ttf` +
  `ENSFont-Bold.ttf`. Both stacks use the real Bold face (since v4.3.0):
  xelatex via `BoldFont=ENSFont-Bold`, web via the second `@font-face`
  (Regular covers weight 100–500, Bold 600–900). (The ttfs merge into this
  skill at the deck-beamer migration.)
- **Content rules:** edit `reference/content-integrity.md`; it is the single
  source those rules are quoted from.

## The look is a free variable

| Fixed — always honored | Free — varies per deck |
| :--- | :--- |
| the engine's contract and hard rules (deck-runtime, deck-svg) | theme: light or dark |
| the contrast rules in every theme, 1920×1080 frame, one slide per `<section>` | palette and the `--chapter` accents |
| CJK typography in the tokens: body `line-height:1.78`, headings `1.3`, no italics (`em` is upright colour emphasis, because slanted Hanzi is synthetic and looks wrong) | typography, art style and density, layout |

Every accent on a slide derives from one `--chapter` variable, so swapping
token *values* retints a whole deck without touching layout or motion CSS.
When flipping light ↔ dark, recheck accents: saturated colours that pass on
black often fail on white.

### Taking a look from another design source — tokens only

A palette may come from anywhere: an installed design skill such as
`ui-ux-pro-max` (discover its `SKILL.md`; it is optional and lives in the
host's user-level skills, never in the course's linked skill directories,
which point into the framework submodule), a design application, or a hand-
picked palette. Take it as `:root` token values only and never let it write
deck markup or layout CSS, because the engine's layout does two jobs a web-
page generator overwrites: `.content` fills the 1080 px frame so content sits
in the optical middle, and type is sized in px on the 1920×1080 canvas, then
scaled to the viewport. A generator falls back to top-aligned document flow
and `rem`/`vw` type, which gives top-weighted slides with tiny text.

- Ask it for "a CSS `:root{}` block only — palette, type scale, effects; no
  HTML, no `.slide`/`.content`/layout CSS".
- Pin its type scale to the slide canvas (body ~40px, title ~76px), never a
  ~16px web base, which scales down to unreadable.
- Paste the variables into `tokens.css` here, run `./fw check-contrast`, and
  leave the structure alone.

## Font

Decks ship the **full** ENSFont (~18k CJK ideographs), so any Traditional
Chinese renders without tofu and nothing needs regenerating. Subsetting is an
optional size optimisation for a final file (e.g. emailing one `.html`), and
must be redone whenever the text changes. Collect the glyphs the deck and its
notes use — ASCII, CJK punctuation, and the visible text with `<style>` and
non-JSON `<script>` removed — into a charset file, then (uv only):

```bash
uvx --with brotli --from fonttools pyftsubset assets/fonts/ENSFont-Regular.ttf \
  --text-file=<charset.txt> --output-file=<unit>/asset/ENSFont.woff2 \
  --flavor=woff2 --layout-features='*' --no-hinting --desubroutinize
```

Run it from the framework root (the `.ttf` path is the framework's), and the
same for `ENSFont-Bold.ttf` → `ENSFont-Bold.woff2`. The `meta NOT subset …
dropped` warning is harmless. `./fw deck-refresh` puts the full font back,
because the subset is a copy of a framework-owned asset.

## Verify

- `assets/css/tokens.css` must define two `@font-face { font-family:'ENS Font' … }`
  blocks — `src: url('ENSFont.woff2')` weight 100 500 and
  `src: url('ENSFont-Bold.woff2')` weight 600 900 (relative — the fonts ship
  beside it).
- `./fw check-contrast` passes for every theme.
- `assets/fonts/ENSFont.woff2` and `ENSFont-Bold.woff2` present and non-empty
  (the xelatex `.ttf`s live at the framework's `assets/fonts/` until the
  deck-beamer migration).
- This skill produces no deck of its own — verification is that an engine
  scaffolds against it cleanly (see deck-svg § Run & verify).
