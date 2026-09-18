---
name: house-style
description: >
  The shared look every presentation and paper engine draws from: the ENSFont
  CJK font, deck design tokens (tokens.css), the CJK xelatex preamble fragment,
  and the content-integrity rules for cited academic work. A base library the
  deck and paper engines copy from when scaffolding. Invoke directly only to
  change the house look or the content rules (palette, font, quoting and
  dispute-handling rules).
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(pwd)
  - Bash(ls *)
  - Bash(cp *)
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
| `assets/css/tokens.css` | `@font-face` + `:root` design tokens (palette, type scale, easing). **Theme = token values.** | every deck engine (linked as `asset/tokens.css`) |
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
```

The engine links `asset/tokens.css` from its `deck.html` and ships the font
beside it. The produced deck is **self-contained** (a frozen copy of the look at
scaffold time); re-running the engine's scaffold re-pulls the latest look. That
is the "central source + frozen instance" model — update here, adopt per deck on
re-scaffold.

## Changing the house look

- **Theme / palette / type:** edit token *values* in `assets/css/tokens.css`
  only — never the component or motion CSS (that lives in the engines). Existing
  decks adopt it when re-scaffolded or by re-copying `tokens.css`.
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

## Verify

- `assets/css/tokens.css` must define two `@font-face { font-family:'ENS Font' … }`
  blocks — `src: url('ENSFont.woff2')` weight 100 500 and
  `src: url('ENSFont-Bold.woff2')` weight 600 900 (relative — the fonts ship
  beside it).
- `assets/fonts/ENSFont.woff2` and `ENSFont-Bold.woff2` present and non-empty
  (the xelatex `.ttf`s live at the framework's `assets/fonts/` until the
  deck-beamer migration).
- This skill produces no deck of its own — verification is that an engine
  scaffolds against it cleanly (see deck-svg § Run & verify).
