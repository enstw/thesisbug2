---
name: deck-plan
description: >
  Plans a talk from the Model declared in talk.json before any slide exists:
  points.md picks the 8–12 points this audience takes away, each tied to a
  Model section, and
  storyboard.md sets the premises and one row per slide (point, content shape,
  layout, on-slide content, spoken points, backup terms and questions, AI
  disclosure). Use when starting,
  reordering or re-angling a presentation or 簡報分鏡; deck-svg, deck-image and
  the Beamer fallback render the signed-off storyboard.
---

# deck-plan — the talk's Controller (angle and flow)

A talk is organized as Model–View–Controller; the presentation protocol
(`assets/templates/presentation/presentation-protocol.md` § Source Files)
holds the rules. This skill is the **Controller**: it decides which parts of
the declared Model this audience sees, in what order, from what angle. The
**Model** is the task-focused file or files named by `talk.json`; the **Views** are the slides, which
deck-svg, deck-image or the Beamer fallback render from the storyboard
written here.

The Controller is a skill of its own, not a step inside one engine, because
every engine renders the same plan: a deck that switches from live HTML to
images keeps its storyboard, and an engine that planned slides by itself
would skip the review this plan exists for.

## Before planning: the declared Model

Read `<talk>/talk.json`; each `model` path is relative to `<unit>`. A reading
guide normally declares `guide.qmd`, while a paper or thesis talk declares the
actual staged deliverable or manuscript. Stable per-source summaries are
upstream lookup aids, not an alternative Model: use them to locate a passage,
then verify and cite the original in the Model.

Plan only from the declared Model as it renders, including its local Quarto
includes, because neither points nor storyboard may add a claim. A point the
talk needs but the Model lacks goes into the Model first. Run
`./fw check-citations <unit>` before planning, so every point starts from
sentences whose sources resolve; the same gate checks the unit glossary/Q&A.

## The angle — `<talk>/points.md`

- About 8–12 points, one sentence each, each naming the Model file and section it
  draws on (`<model-file> § <heading>`, an included heading counts),
  because a talk is one selection from the argument and the selection should
  be reviewable on one page.
- Number them P1, P2, … and never renumber; a point added later takes the next
  free number, because storyboard rows cite the numbers and renumbering would
  silently re-point them.
- Another occasion or angle on the same Model — a shorter version, a
  co-presented week, a discussion-first order — gets a new talk directory,
  not a new Model or a suffixed Controller inside one talk. This keeps the
  delivered occasion, its deck and milestone unambiguous.

## The flow — `<talk>/storyboard.md`

The scaffold (`unit-init`) has the format. It opens with **前提** as bullets —
never a table, because `./fw build` counts every table row as a slide:

- **Title:** a main title that catches interest or uses the course's theme,
  and a subtitle that carries the specific case and scope; neither states an
  unverified allegation as fact (ask a question or name the phenomenon
  instead), because a title is quoted without the evidence that qualifies it.
- **Audience, time, room and projection** (type floor, light or dark theme),
  **wording** (term translations, name forms), because these decide type size,
  pace and terms, and changing them after the slides exist means redoing the
  deck.
- Time never drives cuts or cramming: the density limit holds and the
  presenter adjusts pace or skips slides live, because content cut in advance
  is lost even when time turns out to suffice.

Then one row per slide, ordered along the variant's spine — thesis: problem →
gap → question → method → evidence → finding → contribution; reading guide:
range → author → arguments → synthesis → concepts → critique → questions:

| # | 來源論點 | 內容形狀 | 版型 | 動態 | 講 | 畫面內容 | 口說重點 | 名詞與提問 | AI 協助 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 5 | `points.md` P4 | 4 Two-axis typology | `.matrix` 3×3 | M-STEP | 2 min | axis y = 極數, axis x = 權威密度; highlight the cell the author's case falls in | why the axes, the author's case with page, transition to the critique | 極數、權威密度、Q3 | AI drafted the cell labels; author chose the axes and checked them against the source |

- **來源論點** names the point; the point names the Model file and section. That chain
  is the traceability the author reviews: every slide points back to a cited
  Model sentence.
- **內容形狀** is a number from [`reference/content-shapes.md`](reference/content-shapes.md);
  read it while writing rows. **版型** is chosen from [`reference/layout-catalog.md`](reference/layout-catalog.md)
  (e.g. `L-3CARD-VERDICT`, `L-BENTO-FOCUS`, `L-VS-CONFRONT`), which collects the 16
  standard layouts, or legacy classes from `reference/slide-patterns.md`. The interactive
  workbench at [`docs/layout-explorer.html`](file:///Users/j/homework/thesisbug2/docs/layout-explorer.html)
  (`./fw deck-compile --explorer`) lets authors explore all layouts, depth variants and themes live
  and copy storyboard rows with one click. Naming both before
  the slide exists makes an unfitting choice visible at review instead of as
  oddly reshaped content on a finished deck.
- **動態** names how the slide reveals in the deck's lively mode (deck-svg
  § Lively mode): one code from [`reference/motion-catalog.md`](reference/motion-catalog.md)
  (`M-STEP`, `M-POP`, `M-COUNT`, …), optionally plus a transition (`M-PUSH`,
  `M-ZOOM`), or `—` for a static slide. It is chosen here, with the layout,
  because the reveal order is part of how the audience reads the slide, and
  the same deck-wide restraint (one scramble, at most two zooms, no push
  after push) is only visible with every row in view. Either the author (or
  the agent) picks from the catalogue, or `./fw deck-motion-pick <talk>`
  turns each row into a bounded choice for Jev and writes the picks back —
  a paid call the author acknowledges with `--ack`; the catalogue explains
  both routes. Both judge from the same material: the catalogue describes
  each effect (what the audience sees, what it needs, when it fails) and
  never says which page type takes which code, and the picker states each
  page's facts (position, section, title length, lead, item count, number,
  minutes, source point, neighbours) rather than hints, because a hint is
  an answer key and two of them on one page gave Jev a coin-flip. A premise
  bullet `關鍵數字：5,380` marks the deck's one key figure for `M-SCRAMBLE`.
  `./fw deck-compile` turns the codes into the slide's
  `data-beat`/`data-fx`/`data-enter` attributes; codes that need hand-drawn
  SVG or hand-placed ids stay in the row as the intent and are added by hand
  in deck-svg. A storyboard without the column compiles a static deck.
- **畫面內容** carries the structured semantic slots for the chosen layout
  using micro-syntax (key-values, `<br>`, bullet cards `- [tag] head: body`, verdict),
  as detailed in [`reference/layout-catalog.md`](reference/layout-catalog.md).
  This allows `./fw deck-compile <talk>` to render the slides automatically.
  Keep it graspable in about ten seconds, because the audience reads while listening.
  A row that needs more becomes two rows.
- **口說重點** is what the talk says — explanation, citations with locators,
  transitions. With sparse slides the notes carry the talk, so the author
  reviews them here; the View writes them out in full as the note's 講法.
- **名詞與提問** lists the terms the presenter must be able to explain on this
  slide (spelled as the headings of `<unit>/notes/glossary.md`) and the questions
  this audience is likely to ask (`Q<n>` from `<unit>/notes/qa.md`), separated by
  `、`. The presenter may not know every detail behind a slide, and the
  audience asks about exactly those; which ones to prepare depends on the
  audience in 前提, so the choice is made here, while the explanations and
  answers are factual backup written once at unit level (protocol § Speaker
  notes). `./fw deck-notes` refuses a row that names an entry the unit lacks.
  List every term and abbreviation on the slide or in its 口說重點 that this
  audience may not know: the command checks that listed entries exist, not
  that the list is complete, so coverage is checked here at sign-off.
- **AI 協助** records what AI drafted or verified and what the author wrote or
  changed, because courses increasingly ask for per-slide AI disclosure, and
  noting it while planning is more reliable than reconstructing it later.

## Review — `./fw storyboard-review`

Give the author the storyboard as a page, not as the table: run
`./fw storyboard-review <talk-or-unit> --open` after writing or changing it.
The page gathers what the sign-off needs from the files that own it — 前提,
one card per row with every column, a preview of the layout (the compiled
slide for a catalog code), the cited points' text, the palette — because a
ten-column table wraps into walls of text and the author would otherwise
open four files. It is a build product under `_output/`; edits go to the
storyboard and the page is rebuilt.

Three optional parts, used when the audience needs them:

- **Where a change sits.** For a talk about changes to a pipeline (a lab, a
  method), declare the steps in 前提 as `流程步驟：S1 讀取資料、S2 …（圖：@fig-label）`
  and add a **環節** column (`改：S3、S5；講：S6`, or `—`). The page shows a
  step strip per card and a slide × step table, with changed steps coloured
  apart from explained ones, because an audience comparing versions loses track
  of which stage each slide changed. `./fw deck-compile` puts the same strip in
  each compiled slide's top bar, between the eyebrow and the page number, with
  the two-character step names (讀取資料 → 讀取; `小地圖：讀取、攤平、…` overrides
  them) instead of S numbers, because a listener who hears "S4" cannot recall
  which stage it was; a `—` row gets no strip. `流程對照：<course path> § <heading>｜<column prefix>`
  adds a course-level table, filtered to this occasion's columns.
- **Formulas.** A **公式** column (`$…$`, KaTeX) lists the formula behind a
  slide for an audience that reads formulas faster than prose; each formula
  must match the Model's text, like every other cell.
- **Choices.** Decisions left to the author go in a `## 待選` section: a bullet
  per question, indented `- A …` options, and `建議 X：理由` in the question.
  The page renders radios and a copy button; the author pastes the line back,
  and the agent writes the result into the rows or premises and deletes the
  question, because a choice that stays in 待選 is not yet a plan.

The author signs off `points.md` and the storyboard; only then does a View
get built.

## Changing a planned talk

Only changes of order, emphasis, audience or angle are made here, and they
leave the Model untouched. A wrong fact goes back to its owning factual layer
(Model or unit backup knowledge) and is then re-rendered in every row and slide
that uses it; a layout change stays in the View (protocol § Source Files, rule
2).

## The gate

`./fw build <talk>` refuses a deck with no `storyboard.md`, a
row count far from the slide count, or a deck leaning on one pattern
(comparison tables on most content slides, more than six bullets on a slide),
and notes a `points.md` that is missing or still the template. It cannot judge
whether a shape fits — that is the author's review.

## Hand-off to a View

| View | Skill | Choose it when |
| :--- | :--- | :--- |
| Live HTML slides (default) | `deck-svg` (or `./fw deck-compile`) | the deck is still being edited, or compiles deterministically from catalog layouts |
| One image per slide | `deck-image` | the copy is locked and the talk is a showcase, because each later edit costs a page regeneration |
| Beamer PDF | root presentation unit's `presentation.qmd` (protocol § Quarto Beamer Fallback) | the venue needs Pandoc-rendered references or LaTeX |

When the storyboard uses layout catalog codes, run `./fw deck-compile <talk>`
to compile `storyboard.md` directly into `deck.html`. Each View writes a slide
and its speaker note from one row and the Model passage the row's point names,
never the note from the slide.
