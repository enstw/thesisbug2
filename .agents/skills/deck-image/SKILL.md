---
name: deck-image
description: >
  Builds an image-based presentation deck where every slide is one full-bleed
  PNG. Use when asked for an image slide deck, "generate slides as images",
  "deck-image", or to turn AI-generated or hand-drawn slide images into a
  presentation. Plans slides, renders each via a pluggable renderer
  (/genimage-img2, /genimage-nb, or /genimage-canvas for exact text; mixable),
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

The per-slide primitives are *global* skills at `~/.claude/skills/` (not
siblings under `.agents/skills/`) — that is the one path this skill reaches
outside its own folder. Pick per deck, or per slide (a mixed deck is fine:
drawn title/divider slides + generated body slides, one manifest).

| Renderer | How | Best for | Pre-condition |
| :--- | :--- | :--- | :--- |
| **/genimage-img2** | gpt-image-2 via `codex exec` (`genimage-img2/gen-image.sh`) | photorealistic / illustrative slides; dense multilingual text renders well but can garble | `codex` installed + `codex login` |
| **/genimage-nb** | nano banana via `agy -p` (`genimage-nb/gen-image.sh`) | AI-generated slides billed to the Gemini side; alternative look to gpt-image-2 | `agy` installed + logged in |
| **/genimage-canvas** | agent-drawn: author each slide as a 1920×1080 HTML composition per the canvas-design method, rasterized by `genimage-canvas/gen-image.sh` (browser-cdp `shot.sh`) | designed, typography-heavy slides; **exact on-slide text by construction** (use house-style ENSFont for CJK); no external CLI, no cost | canvas-design + browser-cdp skills (gen-image.sh fails if browser-cdp missing) |

All three renderers honor the **same output contract** — `IMAGE_OK
<abs_path>` (exit 0) / `IMAGE_FAIL <reason>` (exit non-zero) — so Step 3's
loop works unchanged; only the input differs (a prompt for the AI pair, an
authored HTML source for /genimage-canvas):

```
genimage-img2/gen-image.sh    "<prompt>"    "<out.png>" "<size hint>"
genimage-nb/gen-image.sh      "<prompt>"    "<out.png>" "<size hint>"
genimage-canvas/gen-image.sh  "<src.html>"  "<out.png>" "WxH"
```

**Boundary vs deck-svg:** if the slides should stay *live* HTML — selectable
text, entrance animations, re-editable components — this is deck-svg's job.
Use deck-image when slides are genuinely images: AI-generated art, or
/genimage-canvas compositions you want frozen poster-grade.

## Pre-flight (per renderer actually used)

/genimage-img2 gate:

```bash
command -v codex >/dev/null || echo "CODEX_MISSING"
[ -f "${CODEX_HOME:-$HOME/.codex}/auth.json" ] || [ -n "$OPENAI_API_KEY" ] || [ -n "$CODEX_API_KEY" ] || echo "AUTH_MISSING"
[ -x "$HOME/.claude/skills/genimage-img2/gen-image.sh" ] || echo "IMG2_MISSING"
```

/genimage-nb gate:

```bash
command -v agy >/dev/null || echo "AGY_MISSING"
[ -x "$HOME/.claude/skills/genimage-nb/gen-image.sh" ] || echo "IMGNB_MISSING"
```

/genimage-canvas gate:

```bash
[ -x "$HOME/.claude/skills/genimage-canvas/gen-image.sh" ] || echo "IMGCANVAS_MISSING"
```

(gen-image.sh re-checks its own dependencies — hard `IMAGE_FAIL` without
browser-cdp. Fed an authored `.html` it runs rasterize-only, so
canvas-design isn't needed at render time.)

Stop with the matching install/login message if a flag fires.

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

### AI renderers (/genimage-img2, /genimage-nb — same loop, different script)

Sequential:

```bash
cd "<deck>"
GEN="$HOME/.claude/skills/genimage-img2/gen-image.sh"      # or …/genimage-nb/gen-image.sh
SIZE="landscape 16:9 aspect ratio, high detail, sharp text"
"$GEN" "$(cat prompt-01.txt)" "generated-slides/01-title.png" "$SIZE"
# ... one call per slide; each prints  IMAGE_OK <path>  or  IMAGE_FAIL <reason>
```

Faster — a few in parallel (agentic CLI runs are heavy; cap at ~3 concurrent).
Write each slide's prompt to its own file first to avoid quoting pain:

```bash
cd "<deck>"
GEN="$HOME/.claude/skills/genimage-img2/gen-image.sh"      # or …/genimage-nb/gen-image.sh
SIZE="landscape 16:9 aspect ratio, high detail, sharp text"
pids=()
for p in prompts/*.txt; do
  slug=$(basename "$p" .txt)
  "$GEN" "$(cat "$p")" "generated-slides/${slug}.png" "$SIZE" &
  pids+=($!)
  # throttle to 3 in flight
  if [ "${#pids[@]}" -ge 3 ]; then wait "${pids[0]}"; pids=("${pids[@]:1}"); fi
done
wait
```

Use `timeout: 600000` on each Bash call. Collect every `IMAGE_OK`/`IMAGE_FAIL`
line; re-run only the failures (one targeted retry each).

### Drawn renderer (/genimage-canvas)

Per slide: author a self-contained 1920×1080 HTML composition following the
canvas-design skill's philosophy (fixed-size stage, no scroll — /genimage-canvas's
SKILL.md § Author has the full constraints), using house-style's ENSFont for
CJK text: copy `$SKILL_DIR/../house-style/assets/fonts/ENSFont.woff2` and
`ENSFont-Bold.woff2` beside the HTML and declare the same two `@font-face`
blocks as house-style `tokens.css` (family `'ENS Font'`, Regular weight
`100 500` + Bold weight `600 900`; snippet in /genimage-canvas § Author).
Then rasterize:

```bash
~/.claude/skills/genimage-canvas/gen-image.sh "slide-src/01-title.html" "generated-slides/01-title.png" "1920x1080"
```

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
   offenders (Step 3) and re-proofread. /genimage-canvas slides skip this:
   their text is exact by construction.
1. Open `deck.html` in a browser to confirm navigation and the presenter
   window work; for a headless check use the global `browser-cdp` skill.
1. Report: deck path, slide count, renderer(s) used, and the controls (→ next,
   P presenter, R reset, browser Print → Save as PDF for a clean
   one-page-per-slide export).

## Notes

1. Slides use `object-fit: cover`, so a slightly off-16:9 render still fills the
   frame — exact dimensions aren't critical, but ask for 16:9 to minimize crop.
1. Cost/time: budget ~1–3 min per AI-rendered slide; /genimage-img2 bills the codex
   ChatGPT subscription, /genimage-nb the agy/Gemini side — not per-image.
   /genimage-canvas slides cost only the authoring time.
1. `generated-slides/` holds large binaries — suggest `.gitignore` unless the
   user wants them committed.
1. Keep the aesthetic sentence identical across all slide prompts (AI) or the
   design-philosophy doc shared across compositions (/genimage-canvas); vary only
   the per-slide visual concept — this is the single biggest lever for a
   cohesive deck.
