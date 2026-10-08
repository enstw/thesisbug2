---
name: deck-runtime
description: >
  The shared HTML deck shell for deck-svg and deck-image: the deck-stage
  element (slide navigation, P-key presenter console, print-to-PDF at one
  1920×1080 slide per page). A ship-as-is runtime that the deck engines copy in
  when scaffolding; not authored against directly. Consult when a deck's
  navigation, presenter window, or print layout misbehaves or needs changing.
---

# deck-runtime — the shared deck shell (runtime layer)

The middle layer of the deck model: the **runtime** that turns a page of
`<section class="slide">` elements into a navigable, presentable, printable deck.
It is **look-agnostic** — it styles nothing of its own, driving everything off
CSS variables — so the theme (house-style) and the slide vocabulary (the engine)
layer on top without touching it.

```
look      house-style    font · tokens · content rules
runtime   deck-runtime   ← THIS — <deck-stage> nav · presenter · print
engine    deck-svg, deck-image   author slides onto the shell
```

## What's in the box (`template/asset/`)

| File | Role | Edit it? |
|---|---|---|
| `deck-stage.js` | The `<deck-stage>` custom element: slide flight/nav, keyboard (→/Esc/digits/F), `slidechange` event, print CSS (`@page 1920×1080`, one slide per page), `#debug` self-check. | **No — frozen.** Treat as a dependency. |
| `presenter-stage.js` | Dual-screen presenter console (P key): current/next preview and speaker notes in a popup that drives the deck window over `postMessage`; **O** (or the 全部投影片 button) opens a grid of every slide, so a far slide is one click away (arrows + Enter also pick one, Esc returns to the notes). With an extended desktop it puts the deck fullscreen on the external screen and the console on the built-in one (see below). Forwards `+`/`=`/`-` as `{deckFontDirection: ±1}` so the presenter can resize the deck's text, and `c`/`g` (Shift = reverse) as `{deckThemeKey}` so the theme can change from the console; an engine without a handler ignores the message. | **No.** |

This is the only home for these two files. deck-svg and deck-image copy them in;
they are not duplicated per engine.

## The contract an engine must honor

A deck the engines produce must satisfy what `deck-stage.js` expects:

- A single `<deck-stage width="1920" height="1080">` wrapping the slides. Each
  direct child is one slide (`<section>`); `<script>`, `<style>` and
  `<template>` children are ignored.
- Slides are hidden, not unmounted: inactive ones stay in the DOM with
  `visibility:hidden; opacity:0`, and every slide is forced to
  `position:absolute; inset:0; overflow:hidden`. Author each as a full-bleed
  1920×1080 frame, because content past the edge is clipped without a
  scrollbar.
- `data-label="…"` on each slide names it in the presenter console and
  thumbnails (falling back to its first `h1`–`h3`).
- The active slide gets `data-deck-active` set by the runtime — entrance
  animations key off `.slide[data-deck-active] .rise`.
- Speaker notes: a `<script type="application/json" id="speaker-notes">` array,
  one string per slide, in slide order. The presenter console reads it; `\n`
  inside a string is a line break there.
- Load order at end of `<body>`: `asset/deck-stage.js` then
  `asset/presenter-stage.js`; an engine's own scripts go around them as its
  skill specifies.
- Keep `deck-stage:not(:defined){visibility:hidden}` in the CSS, so the first
  slide does not flash unstyled before the element upgrades.
- The runtime emits `slidechange` with `e.detail.index/previousIndex/total/slide/reason`
  (used e.g. by the number-counter helper).

What the runtime gives for free, so an engine writes none of it: ←/→,
PgUp/PgDn, Space, Home/End, **R** (reset), number keys, the hover overlay,
mobile tap zones, `@media print` at one 1920×1080 slide per page, and the
**P** presenter window. When the desktop spans two screens and the browser
is Chromium-based, **P** tries to place the windows, one per press: the first P
opens the console filling the built-in screen (an ordinary window, not
fullscreen, so the presenter can still switch apps there), the second P,
pressed on the deck, asks for fullscreen on the external screen (the
projector). If the console took focus, its P brings the deck forward and the
deck asks for P once more. The window-management permission is asked once per
page load. **This placement does not reach the projector in Brave from
`file://`** (live test 2026-10-08): the browser keeps both windows on the
laptop, so the presenter drags the deck window to the projector and presses
**F** there; docs/DESIGN.md records the findings and the planned extension.
On macOS, "Displays have separate Spaces" (System Settings → Desktop & Dock)
must be on, or a fullscreen deck's Space blanks the laptop screen too. With one screen, mirroring, Safari or Firefox, or a refused permission, P opens the
plain popup as before; a desktop without a built-in screen keeps the console
on the screen the deck was on. Thumbnails and the slide grid render over
`file://` too: each is a copy of the deck loaded at its slide. Chrome only
blocks the console from scripting those copies there, so a thumbnail that
changes slide reloads instead of switching in place. Decks are presented
from `file://`, so runtime features must work there (see docs/DESIGN.md).

Minimal skeleton (an engine's starter adds its look and checks):

```html
<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="UTF-8">
<style>deck-stage:not(:defined){visibility:hidden}</style></head><body>
<deck-stage width="1920" height="1080">
  <section class="slide" data-label="標題">…</section>
</deck-stage>
<script type="application/json" id="speaker-notes">["第一張的備註…"]</script>
<script src="asset/deck-stage.js"></script>
<script src="asset/presenter-stage.js"></script>
</body></html>
```

CSS variables the runtime/components rely on (defined by house-style tokens):
`--font`, `--ink*`, `--text/--body/--muted`, `--accent`, `--chapter`, `--ease`.

## How an engine mounts the runtime (the convention)

Skills have no native import; the engine's scaffold step copies the shell in.
Sibling skills resolve as `$SKILL_DIR/../deck-runtime/…`:

```sh
RT="$SKILL_DIR/../deck-runtime/template/asset"
cp "$RT/deck-stage.js" "$RT/presenter-stage.js"  <deck>/asset/
```

## Verify

- `node --check template/asset/deck-stage.js` and `… presenter-stage.js` pass.
- A scaffolded deck opens from `file://` and advances on click; the runtime's
  own check is `deck.html#debug` (see deck-svg § Run & verify).
