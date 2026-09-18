---
name: diagram
description: >
  Creates or updates a diagram or figure (flowchart, sequence, class, component,
  state, ER, use-case, mindmap, gantt, activity) for a paper, document, or
  slide. Use whenever a figure is needed in the corpus. Authors PlantUML source
  and renders SVG via ./fw plantuml2svg (Kroki, no rate limits) per the
  repo's SVG-first policy, which embeds cleanly in Quarto PDF and deck HTML;
  commits both the .plantuml source and the .svg.
---

# diagram — PlantUML-first, SVG-first figures

When a diagram is needed, **prefer PlantUML source rendered to SVG.** The framework ships `./fw plantuml2svg` (renders via Kroki POST, sidestepping plantuml.com's 509 rate limits). This skill is the entry point; the full policy lives in `.framework/AGENTS.md` § Diagrams. **Run — and extend — `./fw plantuml2svg` rather than curling plantuml.com / Kroki by hand, running a raw `plantuml.jar`, or dropping in a Mermaid block.**

## Why SVG, why PlantUML

- **SVG-first**: vector, resolution-independent. Quarto PDF builds convert SVG via `rsvg-convert`; deck-stage HTML decks embed SVG inline (the required art form for decks — never emoji). Use **PNG only** when the SVG toolchain is unavailable, and then pass `--format png` explicitly.
- **PlantUML-first**: text source is diffable, re-renderable, and commit-friendly. Reach for it for any diagram it can express — flowchart/activity, sequence, class, component, state, ER, use-case, mindmap, gantt.

## Workflow

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

## When PlantUML can't express it

Same SVG-first priority for hand-drawn or tool-exported diagrams — commit the final SVG and note the source tool in an adjacent `<name>.README.md` if non-obvious. For AI-generated **raster** imagery (painterly art, not diagrams), use the `genimage-img2` skill instead; SVG-first still governs diagrams and icons.
