---
name: deck-image
description: >
  Builds an image-based presentation deck where every slide is one full-bleed
  PNG. Use when asked for an image slide deck, "generate slides as images",
  "deck-image", or to turn AI-generated or hand-drawn slide images into a
  presentation. Plans slides, renders each via Codex image generation or an
  HTML-to-PNG renderer, or assembles images supplied by the user,
  then build-deck.py assembles a self-contained 16:9 deck-stage HTML deck. For
  live, editable HTML slides use deck-svg instead.
---

# /deck-image — slide-as-image decks

Each slide is one PNG; the deck is a thin HTML shell (`<deck-stage>`) that
displays the images full-bleed. This skill owns only the *workflow*: plan
slides → render one image per slide (via a **renderer**) → assemble the deck.
Where the PNG comes from is pluggable — the assembly half never cares.

Pipeline:

```
slide specs ──(per slide)──▶ renderer ──▶ generated-slides/NN-*.png
                                                   │
                                   build-deck.py ◀─┘ ──▶ deck.html (+ asset/)
```

This is an **engine** layer in the deck stack (alongside `deck-svg`): it
produces the slides, then leans on the sibling **`deck-runtime`** skill for
the `<deck-stage>` shell. `build-deck.py` copies the runtime JS from
`$SKILL_DIR/../deck-runtime/template/asset/` — no bundled copy here, one
source of truth. (`$SKILL_DIR` = this skill's own folder.)

## Renderers

The host agent may vary, but **AI image generation uses Codex**, the
maintainer's currently stable backend. A Codex native image tool, the
`genimage-img2` Codex wrapper, browser capture of authored HTML, and supplied
PNGs all satisfy the same assembly input. External skills are not bundled here;
discover their actual paths and read their instructions instead of assuming
a vendor's home directory.

| Renderer | How | Best for | Pre-condition |
| :--- | :--- | :--- | :--- |
| Codex image generation | Codex native image tool, or the discovered `genimage-img2` Codex wrapper for another host | photographic or illustrated slides | a working Codex generation path; the wrapper requires an installed, authenticated Codex CLI |
| Authored HTML → PNG | fixed 1920×1080 HTML captured by available browser tools; optional `genimage-canvas` integration | typography-heavy slides with editable source text | browser capture; external integrations may have additional dependencies |
| Supplied images | copy the user's PNGs into the deck | already-approved slide images | readable image files |

The required output is an existing PNG at the manifest's path. Some external
wrappers report `IMAGE_OK <abs_path>` / `IMAGE_FAIL <reason>`; honor that
contract when documented, but native tools need not emit those strings.

**Boundary vs deck-svg:** if the slides should stay *live* HTML — selectable
text, entrance animations, re-editable components — this is deck-svg's job.
Use deck-image when slides are genuinely images: AI-generated art, or
authored compositions you want frozen as images.

## Pre-flight (per renderer actually used)

For AI generation, use Codex's native image tool when available; otherwise
discover and read `genimage-img2` and use its Codex wrapper. Verify that path's
dependencies through its documented interface. Do not infer login state from
a credential file or probe unrelated providers, because installation paths and
authentication differ by host. Do not silently substitute another provider
when Codex is unavailable; the provider exception exists for reliability.
Supplied PNGs need no generator. If no renderer is available, finish the slide
specs and report image production as pending; do not call an image deck complete
or change the requested deliverable without the user's agreement.

## Inputs

Two ways in:

1. **Slide specs provided** — the user hands you a per-slide list of on-slide
   copy + image prompts (e.g. a `prompts-and-page-content.md`). Use them
   as-is; skip planning.
1. **Source content provided** — a doc/outline to turn into slides. Plan it
   into N slides yourself (Step 2). Keep planning light; the focus is the
   render + assemble workflow, not authoring.

Ask the user for the deck's **output directory**, **renderer** (if not
implied), and **visual style** if not given. One consistent aesthetic line
reused across every slide is what makes the deck look like a deck and not N
unrelated images.

## Step 1: Establish the output structure

Pick a deck directory (default `./<deck-name>/`), and create:

```
<deck>/
  generated-slides/        # the per-slide PNGs (NN-slug.png)
  asset/                   # deck runtime, copied by build-deck.py
  prompts-and-page-content.md   # audit: exact copy + prompt/spec per slide
  slides.json              # manifest consumed by build-deck.py
  deck.html                # final deck (written by build-deck.py)
```

## Step 2: Plan the slides (skip if specs were provided)

For each slide decide: a short `slug`, the **exact on-slide copy** (title,
numbers, bullets, takeaway), `label` (nav/presenter), `alt`, optional speaker
`notes`, the **renderer** (default: one renderer for the whole deck), and —
for the AI renderers — a **self-contained image prompt**. Record all of it to
`prompts-and-page-content.md` so any slide can be regenerated later.

Prompt template that works well for seminar-style slides with the AI
renderers (adapt the visual concept per slide; keep the leading aesthetic
sentence identical across slides for cohesion):

```text
Create a complete 16:9 presentation slide in <language>. <one fixed aesthetic
line, e.g.: Polished university-seminar style, dark editorial fintech
aesthetic, crisp readable typography>, no extra text beyond the specified copy.

Slide title text, exactly:
<TITLE>

<Other on-slide copy — numbers / bullets / labels — each "text, exactly:" so
the model renders it verbatim>

Visual concept: <layout + imagery for THIS slide>.
Ensure all <language> characters are correct and sharp. No logos, no flags, no watermark.
```

Prompt rules:
1. Quote every piece of on-slide text **verbatim** under a "text, exactly:"
   line — image models render dense/multilingual headings well but invent
   text if you leave it vague.
1. Keep each prompt fully self-contained (the model has no memory across calls).
1. State layout explicitly (title left / number right, two side-by-side panels,
   four-quadrant grid…) and end with the "No logos/watermark" guard.

## Step 3: Render one image per slide

Target: `generated-slides/<NN>-<slug>.png` at 16:9 for every slide, whichever
renderer produces it. Run from the deck directory.

### Codex image generation

Send each slide's prompt through the Codex native tool or discovered wrapper
and save its output at the planned PNG path. Keep prompts in files or structured tool arguments
to preserve exact text. Track completion and errors per slide; retry only a
failed slide after identifying a fix. Use the host's long-job mechanism where
needed; no particular shell-tool API is required.

### Drawn renderer

Per slide: author a self-contained 1920×1080 HTML composition (fixed-size
stage, no scroll), using house-style's ENSFont for
CJK text: copy `$SKILL_DIR/../house-style/assets/fonts/ENSFont.woff2` and
`ENSFont-Bold.woff2` beside the HTML and declare the same two `@font-face`
blocks as house-style `tokens.css` (family `'ENS Font'`, Regular weight
`100 500` + Bold weight `600 900`). Capture at 1920×1080 using the available
browser workflow. If `browser-cdp` or `genimage-canvas` is installed, follow
its discovered instructions for capture; do not assume it is dependency-free.

Keep the HTML sources in `<deck>/slide-src/` so any slide can be re-edited
and re-rendered; the deck itself only references the PNGs.

**Regenerate a single slide** later: re-run just that slide's renderer call —
the deck HTML doesn't change, so a browser refresh shows the new image.

## Step 4: Assemble the deck

Build `slides.json`, then run the assembler (copies the shared deck-runtime
`deck-stage.js` + `presenter-stage.js` into `asset/` and writes the HTML):

```bash
python3 "$SKILL_DIR/build-deck.py" "<deck>/slides.json"
# $SKILL_DIR = this skill's folder (.agents/skills/deck-image). The runtime JS
# is pulled from the sibling deck-runtime skill; override with --assets <dir>.
# prints  DECK_OK <path>  and warns (stderr) about any missing image file
```

`slides.json` schema (full reference in `build-deck.py`'s header):

```json
{
  "title": "Deck title",
  "description": "one-line meta description",
  "lang": "zh-Hant",
  "slides_dir": "generated-slides",
  "asset_dir": "asset",
  "out": "deck.html",
  "slides": [
    {"file": "01-title.png", "label": "標題", "alt": "...", "notes": "speaker notes…"},
    {"file": "02-...png",    "label": "...",  "alt": "...", "notes": "..."}
  ]
}
```

The first slide automatically gets a `→ / P` hint overlay (disable with
`"hint": false`). `notes` populate the presenter window (press **P** in the deck).

## Step 5: Verify and show

1. Confirm every referenced PNG exists and looks 16:9
   (`file generated-slides/*.png`); heed any build-deck.py missing-file warning.
1. **Proofread every AI-rendered slide against its source copy** — read each
   PNG with your image reader and compare every string and digit with the
   slide's content in the manifest. This is a full pass, not a spot-check:
   generated text is probabilistic, and a wrong digit in a table is worse than
   an ugly slide because the audience trusts it. For dense slides (tables,
   small labels, footers) crop and enlarge the region before judging — at full
   frame a garbled CJK glyph or a swapped digit is easy to miss. Regenerate
   offenders (Step 3) and re-proofread. For authored HTML slides, also inspect
   glyph rendering and clipping; exact source text alone does not prove a
   correct capture.
1. Open `deck.html` in a browser to confirm navigation and the presenter
   window work; use the available browser workflow, including `browser-cdp`
   when installed. Without browser access, report this check as pending.
1. Report: deck path, slide count, renderer(s) used, and the controls (→ next,
   P presenter, R reset, browser Print → Save as PDF for a clean
   one-page-per-slide export).

## Notes

1. Slides use `object-fit: cover`, so a slightly off-16:9 render still fills the
   frame — exact dimensions aren't critical, but ask for 16:9 to minimize crop.
1. Cost/time depends on the selected renderer and account. Check its current
   terms when a budget matters; do not infer billing from the host agent.
1. `generated-slides/` holds large binaries — suggest `.gitignore` unless the
   user wants them committed.
1. Keep the aesthetic sentence identical across all slide prompts (AI) or the
   design-philosophy doc shared across compositions (/genimage-canvas); vary only
   the per-slide visual concept — this is the single biggest lever for a
   cohesive deck.
