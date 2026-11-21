---
name: deck-plan
description: >
  Plans a talk from the Model declared in talk.json before any slide exists:
  points.md picks the 8–12 points this audience takes away; storyboard.md
  sets the premises (audience, density, type floor) and one row per slide
  with its point, content shape and full on-slide content. It decides what
  each slide says without looking at layouts; after the author signs off,
  deck-svg, deck-image or Beamer give it a form without changing a word. Use
  when starting, reordering or re-angling a presentation or 簡報分鏡.
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
sentences whose sources resolve; the same gate checks the unit's knowledge
points (`<unit>/speaker-notes.md`).

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
- **Audience, time, room and projection** (light or dark theme), **wording**
  (term translations, name forms), because these decide pace and terms, and
  changing them after the slides exist means redoing the deck.
- **密度 (density):** `高`, `中` or `低`, with the reason, read from
  [`reference/content-shapes.md`](reference/content-shapes.md) § 密度. Start
  from `高`: it is the default, and it is what the deck is when the bullet is
  missing. You may judge that this occasion calls for another level; write it
  with its reason in this bullet, because the author must be told at sign-off
  how full the slides were written and why, and a level chosen silently reads
  as content that went missing.
- **字級下限 (type floor):** the smallest text the room allows, inside the
  room bullet as `字級下限 34px`. 34px is a classroom projector seen from the
  back row; a small room with a large screen takes 30px and a shared screen
  online 27px, and each step down fits about a quarter more on a slide. Only
  these three values exist, because each is the 34px label size at a font
  scale the deck can run at.
- Time never drives cuts or cramming: the presenter adjusts pace or skips
  slides live, because content cut in advance is lost even when time turns
  out to suffice.

Then one row per slide, ordered along the variant's spine — thesis: problem →
gap → question → method → evidence → finding → contribution; reading guide:
range → author → arguments → synthesis → concepts → critique → questions:

| # | 來源論點 | 內容形狀 | 版型 | 動態 | 講 | 畫面內容 | 講者備註 | AI 協助 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 5 | `points.md` P4 | 4 Two-axis typology | — | — | 2 min | title: …<br>axis_x: {name: "權威密度", low: "低", high: "高"}<br>axis_y: {name: "極數", low: "單極", high: "多極"}<br>cells:<br>- …<br>focus_quadrant: 3<br>deepdive_note: … | K12、K13、K14、Q3 | AI drafted the cell labels; author chose the axes and checked them against the source |

- **來源論點** names the point; the point names the Model file and section. That chain
  is the traceability the author reviews: every slide points back to a cited
  Model sentence.
- **內容形狀** is a number from [`reference/content-shapes.md`](reference/content-shapes.md);
  read it while writing rows. Content that is none of the fifteen gets a short
  name of its own there instead of being bent into the nearest one.
- **畫面內容** is everything the audience is to see on the slide, written in
  the micro-syntax of [`reference/content-syntax.md`](reference/content-syntax.md)
  (key-values, `<br>`, bullets such as `- [tag] head: body`, records). Write
  as many items and fields as the content has at the deck's density. Do not
  open the layout catalogue or recall what a layout holds while writing this
  cell: a row written to fit a remembered layout has three cards because cards
  come in threes and no source line because a card has no source field, and
  nothing downstream can put back what was never written.
- **版型** and **動態** stay `—`. They belong to the design stage, which
  starts only after the sign-off below and fills them without touching any
  other cell. A storyboard that already carries them (an older one, or one
  being revised after design) keeps them; changing content there still goes
  through this stage and a new sign-off.
- **講者備註** holds knowledge-point numbers only — `K<n>` and `Q<n>` from
  `<unit>/speaker-notes.md`, separated by `、`, or `—` — never sentences. The
  presenter does not read a script; what they need on stage is the terms,
  abbreviations, facts and likely questions behind the slide, each with its
  page, and the audience asks about exactly those details. Which ones to
  carry depends on the audience in 前提, so the choice is made here, while the
  points themselves are factual backup written once at unit level (protocol
  § Speaker notes), extracted and numbered while the Model is written. Detail
  that does not fit on the slide becomes a knowledge point, not a longer note.
  `./fw deck-compile` copies the numbers into the slide's `data-notes` (and
  講 into `data-time`), so the notes move with the slide; `./fw deck-notes`
  refuses free text, an unknown number, an uncited point, and an abbreviation
  shown on the slide without a `全名（縮寫）` point among the slide's numbers.
  It cannot see a term the slide needs but the row omits, so coverage of the
  remaining terms is checked here at sign-off.
- **AI 協助** records what AI drafted or verified and what the author wrote or
  changed, because courses increasingly ask for per-slide AI disclosure, and
  noting it while planning is more reliable than reconstructing it later.

## Review — `./fw storyboard-review`

Give the author the storyboard as a page, not as the table: run
`./fw storyboard-review <talk-or-unit> --open` after writing or changing it.
The page gathers what the sign-off needs from the files that own it — 前提,
the deck's density with its reason and the characters each slide carries,
one card per row with every column, a preview (a structural sketch before
design, the compiled slide after), the cited points' text, the palette — because a
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
  must match the Model's text, like every other cell. `./fw deck-compile` puts it on
  the slide as one formula line under the body (`p.fx`; `｜` separates several,
  `—` means none), typeset offline by the KaTeX the deck carries.
- **Choices.** Decisions left to the author go in a `## 待選` section: a bullet
  per question, indented `- A …` options, and `建議 X：理由` in the question.
  The page renders radios and a copy button; the author pastes the line back,
  and the agent writes the result into the rows or premises and deletes the
  question, because a choice that stays in 待選 is not yet a plan.

## Sign-off — `./fw storyboard-sign`

The author signs off `points.md` and the storyboard; only then does a View
get built. When the author has read the review page and agreed, run
`./fw storyboard-sign <talk>`. It writes a `內容簽核` bullet into 前提 holding
the date and a fingerprint of the content: the premises and every column of
every row except 版型 and 動態, read as text, so slot names may change later
and words may not. It also prints the deck's density and type floor; pass
those on to the author with the sign-off, since that is the moment they are
told.

From then on `./fw deck-compile` refuses a storyboard whose content no longer
matches the fingerprint. That is what lets the design stage work on the same
file without being able to trim a row to fit a layout. Never run the command
to make a refusal go away: a mismatch means content changed, so take the
change to the author and sign again only on their agreement.

## Changing a planned talk

Only changes of order, emphasis, audience, density or angle are made here,
and they leave the Model untouched. A wrong fact goes back to its owning
factual layer (Model or unit backup knowledge) and is then re-rendered in
every row and slide that uses it; a layout change stays in the View (protocol
§ Source Files, rule 2). Each change to the content here needs the author's
agreement and a new sign-off.

The design stage hands a row back when no layout can hold it at the type
floor. That row returns here with the measured overflow, and the choice is
the author's: split it where its parts are separable, move detail into the
knowledge points, lower the type floor if the room allows, or lower the
deck's density. Do not pick one alone, because each of them changes what the
audience is shown.

## The gate

`./fw build <talk>` refuses a deck with no `storyboard.md`, a row count far
from the slide count, a compiled deck out of step with its storyboard
(a slide that does not show everything its row says, or content changed after
the sign-off), or a deck leaning on one pattern (comparison tables on most
content slides; at 密度 中 or 低, more than six bullets on a slide), and notes
a `points.md` that is missing or still the template. It cannot judge whether
a shape fits — that is the author's review.

## Hand-off to a View

| View | Skill | Choose it when |
| :--- | :--- | :--- |
| Live HTML slides (default) | `deck-svg` (or `./fw deck-compile`) | the deck is still being edited, or compiles deterministically from catalog layouts |
| One image per slide | `deck-image` | the copy is locked and the talk is a showcase, because each later edit costs a page regeneration |
| Beamer PDF | root presentation unit's `presentation.qmd` (protocol § Quarto Beamer Fallback) | the venue needs Pandoc-rendered references or LaTeX |
| 3D fly-through (derived) | `deck-3d` (`./fw deck-3d`) | the talk wants a showpiece whose transitions carry the structure; generated beside `deck.html`, never instead of it |
| Slidev project (derived) | `deck-slidev` (`./fw deck-slidev`) | the venue or presenter works in Slidev (presenter mode, click steps, its exports); generated beside `deck.html`, needs Node |

Each View gives a signed-off row its form and shows every piece of it. For
the live HTML deck that is deck-svg's design stage: it fills 版型 and 動態,
and `./fw deck-compile <talk>` compiles `storyboard.md` into `deck.html` and
checks the slides against the rows. A View writes a slide from one row and
the Model passage the row's point names, and carries the row's 講者備註 numbers
as its `data-notes`; the note is assembled from the knowledge points, never
written from the slide.
