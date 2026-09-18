---
name: deck-runtime
description: >
  The shared HTML deck shell for deck-svg and deck-image: the <deck-stage>
  element (slide navigation, P-key presenter console, print-to-PDF at one
  1920×1080 slide per page). A ship-as-is runtime that the deck engines copy in
  when scaffolding; not authored against directly. Consult when a deck's
  navigation, presenter window, or print layout misbehaves or needs changing.
user-invocable: false
allowed-tools:
  - Read
  - Bash(pwd)
  - Bash(ls *)
  - Bash(cp *)
  - Bash(node --check *)
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
| `presenter-stage.js` | Dual-screen presenter console (P key): current/next preview, speaker notes, drives a popped-out projector window over `postMessage`, print-to-slides. | **No.** |

This is the only home for these two files. deck-svg and deck-image copy them in;
they are not duplicated per engine.

## The contract an engine must honor

A deck the engines produce must satisfy what `deck-stage.js` expects:

- A single `<deck-stage width="1920" height="1080">` wrapping the slides.
- Each slide is a `<section class="slide" data-label="…">`. `data-label` shows in
  the presenter console.
- The active slide gets `data-deck-active` set by the runtime — entrance
  animations key off `.slide[data-deck-active] .rise`.
- Speaker notes: a `<script type="application/json" id="speaker-notes">` array,
  one string per slide, in slide order. The presenter console reads it.
- Load order at end of `<body>`: `asset/deck-stage.js` then
  `asset/presenter-stage.js`.
- The runtime emits `slidechange` with `e.detail.slide` (used e.g. by the
  number-counter helper).

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
