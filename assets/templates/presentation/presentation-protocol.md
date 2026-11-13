# Presentation Protocol

## Role

You are an academic presentation assistant for a graduate student; the institution, programme, and field come from the course's `COURSE.md`, so this protocol stays reusable across schools. Build concise, argument-driven Traditional Chinese talks for seminars, reading guides, thesis proposals, defenses, and conference talks.

The framework owns both reusable workflows behind a talk: `source-kit` owns
original → identity-checked, stable per-source summary; this protocol owns
stable summaries/originals → task-focused Model → backup knowledge →
Controller → View. A course repo stores each workflow's instance, constraints
and current state; it does not redefine the generic workflow in `COURSE.md` or
a unit decision file.

| Part | Where it is defined | Owns |
| :--- | :--- | :--- |
| Stable source summary | `source-kit` § Stable per-source summary | `<unit>/notes/<key>.md` |
| Presentation Model | § Choosing the Model | `guide.qmd`, `paper.qmd`, or files declared by `talk.json` |
| Backup knowledge (speaker notes) | § Speaker notes | `<unit>/speaker-notes.md`: numbered knowledge points K/Q |
| Controller: angle and flow | `deck-plan` | `<talk>/points.md`, `<talk>/storyboard.md`, content shapes |
| View: live HTML slides (default) | `deck-svg` | `<talk>/deck.html` with each slide's `data-notes`, patterns, slide verification |
| View: one image per slide | `deck-image` | page prompts, rendering, proofreading |
| View: Beamer PDF | § Quarto Beamer Fallback below | root presentation unit's `presentation.qmd` |
| Derived View: 3D fly-through | `deck-3d` | `<talk>/deck3d/`, generated from the storyboard and `deck.html`'s notes; never edited |
| Derived View: Slidev project | `deck-slidev` | `<talk>/slidev/`, generated the same way; never edited |
| Deck shell | `deck-runtime` | the `deck-stage` contract, navigation, presenter window, print |
| Look | `house-style` | tokens, themes, contrast rules, font |
| Figures | `diagram` | SVG, from PlantUML or written directly |

## Source Files

A talk is organized as **Model–View–Controller**, downstream of the stable
source summaries defined by `source-kit`. The summary and Model are not two
versions of one draft: the summary represents one work and stays source-centred;
the Model answers the assignment or talk's question and may select, compare and
frame several summaries after checking the original passages.

`<unit>` is the assignment directory containing `WORK.json`. `<talk>` is one
occasion-specific presentation. A presentation unit is a single talk, so
`<talk> == <unit>`. A paper, thesis or other assignment keeps each occasion at
`<unit>/talks/<occasion>/`, created without copying its manuscript:

```bash
./fw talk-init <unit> --name week16-seminar --model paper.qmd --variant thesis
```

Every new talk carries `talk.json`; its `model` paths are relative to the unit:

```json
{"title":"期末研討會","variant":"thesis","model":["paper.qmd"]}
```

```mermaid
flowchart LR
    R["original / transcript"] --> N["stable source summary<br>source-centred"]
    N --> M["declared Model<br>task-centred"]
    R -. "verify before citing" .-> M
    M --> B["knowledge points<br>speaker-notes.md K/Q"]
    subgraph C["Controller：angle and flow"]
        P["points.md<br>angle"] --> S["storyboard.md<br>flow"]
    end
    subgraph V["View：each slide"]
        K["deck.html<br>slide + its note"]
    end
    M -->|selected by| P
    S -->|routes each slide| K
    M -.->|content of each slide| K
    B --> K
```

- **Model:** the file(s) declared by `talk.json`. A reading guide uses
  `guide.qmd`, organized around the week's problem; a paper/thesis talk uses
  its actual staged deliverable or manuscript (`research-question.qmd`,
  `theory-design.qmd`, `paper.qmd`, etc.), not a presentation copy.
- **Backup knowledge:** `<unit>/speaker-notes.md`, numbered knowledge points
  (`K<n>` terms, abbreviations and facts; `Q<n>` likely questions). It
  expands what the presenter must understand but need not appear in the
  submitted paper. Citation and language gates read this fixed path directly.
- **Controller:** `<talk>/points.md` selects about 8–12 takeaways, each naming
  a Model section; `<talk>/storyboard.md` fixes audience, order, content shape,
  on-slide copy, the knowledge-point numbers each slide carries and AI
  disclosure.
- **View:** `<talk>/deck.html`, each slide bound to its points by `data-notes`. Its frozen engine,
  look and runtime live in `<talk>/asset/`; `deck-refresh` updates only those
  framework-owned copies.

**The Model–View–Controller rules:**

1. On-slide facts and claims live in the declared Model. Backup-only
   explanations live in the unit's cited knowledge points. The Controller selects,
   orders and frames; the View renders without inventing either. A new factual
   idea found while building a slide goes into the Model first.
1. An error is corrected against the original in its owning factual layer
   (Model or backup knowledge), then re-rendered downstream. An order, emphasis
   or audience change belongs to the Controller; a layout or look change
   belongs to the View.
1. Speaker notes are knowledge, not a script. The points are factual backup
   shared by every talk in the unit and checked upstream; the storyboard
   chooses which ones this audience needs, and each slide carries their
   numbers.
1. A different occasion gets a new talk directory over the same Model, not a
   copied manuscript. An image deck is another View of the same Controller.

There is **no build step** for `deck.html` and **no `slides.md`**. `./fw build
<talk>` runs the deck gate. A root presentation unit may also build its Model
or Beamer fallback as a `.qmd` target; an attached talk builds its assignment
manuscript through the owning unit.

## Choosing the Model

`talk.json` is authoritative. `deck-plan` reads every listed file as it
renders, including local Quarto includes.

- **Reading guide:** `guide.qmd` is written around the week's common problem:
  required theory → each reading's relevant argument → comparison and critique
  → factual basis for discussion. It selects from stable summaries, verifies
  the original passage, and cites `[@key, {page}]`. It never rewrites the
  summaries merely to fit the talk.
- **Paper/thesis talk:** declare the submitted manuscript or relevant staged
  document itself. Do not author a second presentation report.
- **Several files:** declare more than one only when they are genuinely
  separate authoritative deliverables; list them in reading order.

Quarto includes remain useful inside a Model to assemble sections without
copying. They stay within the unit, because a cross-unit include lets later
work silently change an already-graded assignment. `check-citations`,
`check-zh-variants` and `lint-readability` follow local includes.

## What a reading guide covers

A reading guide teaches a new reader how each work is built, who wrote it and
where it sits, and what its words mean, then puts the works to use. Each part
is written once, in the layer that owns it, so the slides and notes only
select and say it:

| Content | Written in | Reaches the talk as |
| :--- | :--- | :--- |
| Paper skeleton: question, gap, claims and hypotheses, argument steps, evidence, limits, how the piece is written | the stable summary's 論文骨架 (`source-kit` template) | the argument slides, selected through the Model |
| Author and field position: affiliation, related earlier work, school and contribution | the summary's 作者與學術位置, restated with citations in the Model's `### 作者與學術位置` under each reading | a spoken introduction at the start of that reading's part; no extra slide needed |
| Technical terms and abbreviations | K entries in `<unit>/speaker-notes.md` | the storyboard's 講者備註 column → the slide's `data-notes`; `./fw deck-notes` puts each one-line version in the note |
| Critique and discussion questions | the Model's comparison and discussion sections | the critique and discussion slides |
| Recent events that test the readings (optional) | the Model's `# 近年局勢檢驗`, sources in the unit tier | one timeline slide; a new question gets its own slide |

**Author introductions.** Take the affiliation from the work itself (its first
page or author note) and the field position from cited literature, including
the course's other readings when they discuss the author. A line that
characterizes the contribution in the presenter's words is marked as the
presenter's, on the page and aloud.

**Terms and abbreviations.** Every technical term or abbreviation that appears
on a slide and that this audience may not know gets a K entry and is listed
in that slide's 講者備註. Name an abbreviation's entry 全名（縮寫）, and spell
the abbreviation out at its first use in the Model and on its first slide.
`deck-notes` refuses an abbreviation (two or more capitals) a slide shows
without such a point among its numbers; it cannot tell a Chinese term was
left off, so check those slide by slide when signing off the storyboard.

**Recent-events test (optional).** Current events can test a reading in front
of the class. Map each event to the discussion question it tests, and say on
the slide that the mapping is the presenter's link, which points to what is
worth checking and neither confirms nor refutes the theory. New sources land in
the unit tier with an identity audit (`source-kit` §0, §8). A disputed fact is
written as the claim of the party that makes it, a figure carries its date,
and a status that may change before the talk carries its source date. Do not
reword discussion questions already distributed to the class; add a new one
under the next number and mark it as added.

Run `./fw check-citations <unit>` and `./fw check-zh-variants <unit>` before
planning. A good source summary speeds relevance judgment and locator lookup,
but citation support is still verified against the original (`source-kit`).

## Speaker notes

The presenter does not read a script, and the audience asks about exactly the details a slide leaves out. So a speaker note is the presenter's backup knowledge: the terms, abbreviations, facts and likely questions behind the slide, each traced to the part of the Model it comes from.

| Part | Written in | Owner |
| :--- | :--- | :--- |
| the knowledge points | `<unit>/speaker-notes.md`, one `## K<n> <name>` (term, abbreviation, fact) or `## Q<n> <question>` section each | factual backup |
| which points this audience needs on each slide | `<talk>/storyboard.md` 講者備註: numbers only | Controller |
| the binding | each slide's `data-notes="K3 K7 Q1"` (and `data-time` from 講) | View |

- Each point opens with a one-line version (`**一句話**` / `**簡答**`) that ends with the Model section it comes from, written like `points.md`: `（HM § 六 › 從原稿到 PDF）`; the rest is the full explanation. Information flows one way — sources and the author's insight into the Model, where the facts are cited and checked; the notes from the Model — so a note traces to the Model rather than citing a source again, and the author's own judgement, which lives in the Model, needs no bib key. A point taken straight from a source may carry `[@key, {頁碼}]` instead. The note shows only that first paragraph, because on stage there is time for a glance, not a paragraph; the presenter reads the full entries beforehand. Language gates (and the citation gate, for any `[@key]` a point carries) read the file directly, so it need not be appended to a submitted paper.
- Points are extracted and numbered while the Model is written (a reading guide can start from the source summaries); numbers never change, and a new point takes the next number, because storyboards and slides refer to them. A point is written once and serves every slide that names it. A question the readings do not answer is answered as "the text does not address this", never with an invented answer, because the presenter will say it aloud.
- The numbers sit on the slide itself, not in a list kept in slide order, so moving or inserting a slide cannot attach notes to the wrong slide. `./fw deck-compile` copies each row's 講者備註 into `data-notes`; a hand-written slide carries it directly.
- `./fw deck-notes <talk>` assembles the notes into `deck.html`; `--init` creates the knowledge file from the template. It refuses — and writes nothing — on a content slide without `data-notes`, a token that is not a K/Q number, a number with no entry, a named entry whose first paragraph names no Model section (or a heading the talk's Model files do not have), or an abbreviation shown on a slide without a 全名（縮寫） point among its numbers. `./fw build <talk>` runs the same check.
- Notes are never typed into `deck.html`, because no gate can check them there and they drift toward restating the slide. A deck with no knowledge file — the starter's `[講者備註：…]` placeholders, or a deck from before the command — is migrated before any note changes. `./fw build` refuses a `talk.json` talk without the file and notes an older root deck on every build; `./fw deck-compile` prints the same note and stops on deck-notes' refusal. Decks on the older per-slide 講法 file plus `notes/glossary.md` and `notes/qa.md` still assemble.

## Citation Handling

The HTML deck runs no Pandoc citation processing. On the deck, use:

- Short slide citation: `（Author Year）`
- Speaker-note locator: `[@bibkey, p. 15]` (`./fw deck-notes` turns a Model entry's `[@key, {15}]` into this form)
- A final reference slide listing the core works

Cite in the declared Model and copy the short citation and locator down with
the sentence, instead of adding a citation only on a slide: `check-citations`
validates the Model and unit backup files, not the HTML deck. **If exact
rendered references are required in the deck, use the Quarto Beamer fallback.**

## Quarto Beamer Fallback

In a root presentation unit, use `<unit>/presentation.qmd` when the HTML deck is a poor fit:

- You need Pandoc citation processing from `<unit>/references.bib`.
- You need Beamer/LaTeX output for a formal academic venue, or the `_output/<unit>-presentation.pdf` naming.
- You are on a machine without a browser to print from.

Build it with `./fw build <unit> --target presentation.qmd`. Attached talks
are HTML-first; their assignment manuscript builds through the owning unit.

## Build and Preview

```bash
./fw check-citations <unit>                    # Model + knowledge points
./fw check-zh-variants <unit>
./fw build <talk>                              # deck gate; deck.html itself has no build step
./fw deck-refresh <talk> --dry-run
./fw check-contrast <talk>
```

Opening, presenting and printing the HTML deck: `deck-svg` § Run & verify.

## Reading-Guide Workflow

1. Use `source-kit` to acquire, identify, summarize and verify every assigned
   reading. Each complete summary is reviewed against the original before
   presentation work and remains stable while that reading remains correct.
1. Write `<unit>/guide.qmd` around the week's problem, selecting from the
   summaries and verifying/citing the original passages. This is the declared
   Model; summaries are not included wholesale or rewritten for the talk.
   Open each reading's section with `### 作者與學術位置` (§ What a reading
   guide covers).
1. Extract the knowledge points into `<unit>/speaker-notes.md` while writing
   the Model, numbering them and checking their factual content directly
   against sources. Cover every term and abbreviation the slides will use.
1. Plan the talk with `deck-plan`: `<talk>/points.md`, then the storyboard;
   the author signs off both.
1. Render the Views with `deck-svg` (or `deck-image`), each slide carrying
   its row's numbers in `data-notes`; assemble the notes with
   `./fw deck-notes <talk>`, then run the deck checks.
1. Optional: generate a derived View from the same storyboard with
   `./fw deck-3d <talk>` or `./fw deck-slidev <talk>`. It comes after the
   notes are assembled, because it takes them from `deck.html`; its output
   is never edited, and `deck.html` remains the deck the checks read.
1. If the class requires Pandoc-rendered references, mirror the final structure into `presentation.qmd` and export that fallback.

Single- or two-source guides may skip the cross-reading map; the paper skeleton, author introduction, terms and discussion questions still apply.

## Thesis Presentation Workflow

1. Keep writing the assignment's required documents; they are the Model.
1. Add an occasion with `talk-init`, declaring the relevant document(s), and
   identify audience and conditions in its storyboard premises.
1. Add knowledge points to the shared `speaker-notes.md` only for what the presenter may need.
1. Plan, render and verify the talk without changing the manuscript merely to
   suit its duration or layout.
1. Tag the version used when the talk is delivered, because the manuscript may
   continue changing afterward.

## Quality Checklist

- [ ] Stable summaries identify their source/edition, open with 論文骨架 and 作者與學術位置, preserve argument and evidence with locators, and were reviewed against the original.
- [ ] (Reading guide) Each reading's author is introduced from cited sources; every term and abbreviation on a slide has a K entry listed in that slide's 講者備註.
- [ ] `talk.json` names the actual task-focused Model; no per-talk copy of the assignment manuscript exists.
- [ ] `./fw check-citations <unit>` and `./fw check-zh-variants <unit>` pass, including the knowledge points.
- [ ] `<talk>/points.md` and `storyboard.md` are signed off; every slide and note trace to the declared Model and add no factual claim.
- [ ] Key claims have source support in `<unit>/refs/` (`source-kit`).
- [ ] `<talk>/deck.html` exists; every `<section>` has `data-label` and `data-notes`; `./fw deck-notes <talk> --check` passes.
- [ ] `./fw deck-refresh <talk> --dry-run` reports no stale asset and no missing tag, and the engine scripts load in the order `deck-svg` § Run & verify gives.
- [ ] `./fw check-contrast <talk>` passes; `#debug` reports `minfont=ok`, `overflow=none` and `contrast=ok` on every slide.
- [ ] The comprehension test (`deck-svg` § Run & verify) has run on the final slide text: an isolated reader given only `./fw deck-text <talk>` output can restate every content slide as who did what to whom.
- [ ] `deck-svg` § Hard rules hold, and its `@media print` block forces `.rise` visible.
- [ ] Title slide with main title and subtitle; Q&A / closing slide.
- [ ] (Image-deck mode) `<talk>/prompts-and-page-content.md` matches the shipped PNGs; every page passed the string/digit proofread; every `<img>` carries a content-bearing `alt`.
- [ ] A root presentation unit has `presentation.qmd` when a Beamer fallback is actually needed.
- [ ] Prints to a clean one-slide-per-page PDF (Background graphics on).
