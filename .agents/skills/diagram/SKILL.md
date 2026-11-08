---
name: diagram
description: >
  Creates or updates a diagram or figure (flowchart, sequence, class, component,
  state, ER, use-case, mindmap, gantt, activity) for a paper, document, or
  slide. Use whenever a figure is needed in the corpus. Output is SVG, from
  PlantUML rendered by ./fw plantuml2svg (Kroki, no rate limits) when automatic
  layout suits the diagram, or written directly as SVG when the layout must be
  set, such as left-to-right flows for 16:9 slides; commits the text source.
---

# diagram — SVG-first figures, from PlantUML or SVG

When a diagram is needed, **the output is SVG**, and its source is one of two kinds:

- **PlantUML**, rendered to SVG with `./fw plantuml2svg` (Kroki POST, sidestepping plantuml.com's 509 rate limits), when automatic layout suits the diagram: sequence, class, component, state, ER, use-case, mindmap, gantt, and activity diagrams that may run top to bottom.
- **SVG written directly**, by hand or by a script, when the layout has to be set: a left-to-right or multi-row flow for a 16:9 slide, a figure that must fit a given aspect, or deck art that follows the theme colours. PlantUML's current activity syntax only runs top to bottom, and its colours and type sizes are fixed, so a slide would shrink its text below the deck's 34px floor.

Either way, run — and extend — `./fw plantuml2svg` rather than curling plantuml.com / Kroki by hand or running a raw `plantuml.jar`, and do not drop a Mermaid block into a manuscript or deck: neither the deck nor this policy renders Mermaid at view time. (The framework's own Markdown documentation uses Mermaid; see `.framework/AGENTS.md`.)

## Why SVG, and why a text source

- **SVG-first**: vector, resolution-independent. Quarto PDF builds convert SVG via `rsvg-convert`; deck-stage HTML decks embed SVG inline (the required art form for decks — never emoji). Use **PNG only** when the SVG toolchain is unavailable, and then pass `--format png` explicitly.
- **A text source in git**: diffable, re-renderable, and reviewable. A `.plantuml` file is that source for its SVG; a directly written SVG is its own source, which is why it must stay plain text (no embedded base64 raster) and why a script that generates one is committed with it.

## Workflow: PlantUML

1. Author/maintain the source as `<unit>/<name>.plantuml`.
2. Render to SVG:
   ```bash
   ./fw plantuml2svg <unit>/<name>.plantuml <unit>/<name>.svg
   # PNG fallback only:
   ./fw plantuml2svg <unit>/<name>.plantuml <unit>/<name>.png --format png
   ```
3. Reference it in the qmd:
   ```markdown
   ![Caption text](<name>.svg){#fig-label}
   ```
4. Commit **both** the `.plantuml` source and the rendered `.svg` (or `.png`).
5. To update a diagram: edit the `.plantuml`, then re-run the render.

## Workflow: SVG written directly

1. Write `<unit>/<name>.svg` (a figure in the manuscript) or `<talk>/<name>.svg` (a slide). If a script draws it, commit the script beside it (`<name>.py`) and regenerate instead of editing the output, because a hand edit to generated output is lost at the next run and leaves the script and the figure saying different things.
2. **For a slide**, put it in an `L-CANVAS` row as `svg: <name>.svg`. Set `viewBox` to width `1728` (the slide's content width) and give the root `class="art dg"`, so 34px text stays 34px; draw with `currentColor` and `var(--chapter)` in `style` attributes, so the art follows the theme. `./fw deck-compile` adds `width` from the viewBox when the root lacks one, because the canvas would otherwise collapse it.
3. **For a manuscript figure**, reference it with `![Caption](<name>.svg){#fig-label}` and use literal colours and font sizes: `rsvg-convert` has no deck stylesheet, so `var(--chapter)` would not resolve in the PDF.
4. Note the source tool in an adjacent `<name>.README.md` when the SVG was exported from another program, so the next editor knows where to change it.

## Raster imagery

For AI-generated **raster** imagery (painterly art, not diagrams), use Codex's native image tool or the discovered `genimage-img2` Codex wrapper: generation is the provider exception because Codex is the maintainer's currently stable backend. If unavailable, report the asset as pending instead of switching providers. SVG-first still governs diagrams and icons.
