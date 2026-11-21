# Content shapes — 內容形狀

A slide's **content shape** is a property of the material, so it is decided in
the storyboard, before any slide exists and whichever engine renders it. Each
View then maps the shape to its own layout: deck-svg through
`reference/slide-patterns.md` § Shape → pattern, an image deck through the
layout line of the slide's prompt, the Beamer fallback through its frame.

**The rule:** the shape of the content chooses the layout, in two stages that
do not look at each other's work. The storyboard stage writes what the slide
says and names its shape without consulting any list of layouts; the design
stage then picks a layout that holds the row whole, or adds one, and may not
change a word. An agent that sees the layouts while deciding the content
reaches for bullets, cards and comparison tables for everything and writes
only as much as they hold: a 3×3 typology becomes a list, the examples are
cut to make room, and the author cannot recognise the source in the slides.
Keeping the layouts out of sight here, and checking afterwards that every
piece of the row is on its slide, is what stops that.

## 密度 — how much a slide carries

Density is a property of the occasion, so it is one premise for the whole deck
(`密度：高｜中｜低` in 前提) and not a constant of the framework.

| 密度 | The occasion | What one slide carries |
| :--- | :--- | :--- |
| **高** (default) | The audience also reads the slides: a thesis proposal or defence where the committee holds a copy and turns back to a page, slides that circulate afterwards, a technical review. | A whole unit of the argument with its support: a framework with all its parts, a full comparison, a claim with its evidence and source. The limit is that it fits at the room's type floor. |
| **中** | A seminar talk to peers who listen first and read second. | One point with its evidence. Parallel items beyond six only when they are grouped. |
| **低** | A lecture or public talk where the slide only supports the voice. | One idea, graspable in about ten seconds; at most six short items. |

- **Start from 高.** A slide that says too little cannot be repaired on stage,
  while a full one can be revealed step by step and talked through; and the
  common failure of an agent-written deck is thinness, not clutter.
- **You may choose another level, and the author must see that you did.** Judge
  from who is in the room and what they do with the slides, and write the
  level with its reason in 前提 (`密度：中（課堂導讀，同學邊聽邊看，沒有講義）`).
  `./fw storyboard-review` shows it at the top of the page with the characters
  each slide carries, and `./fw storyboard-sign` prints it, because a density
  nobody was told about reads to the author as content that went missing.
- **Density never overrides the relation between parts.** When how the parts
  relate is the content (a framework, a typology, a comparison), they stay on
  one slide at every level; a deck at 低 has fewer such slides, not broken ones.
- **Whether it fits is not decided here.** Write what the slide must say. If
  the design stage finds a row cannot fit at the type floor it reports the row
  back, and the choice between splitting it, moving detail to the knowledge
  points and lowering the floor is made with the author.

## Catalogue

Fifteen shapes cover nearly every slide in a seminar, thesis or reading-guide
deck. The **Use when** column is the test; the **Not this** column is the
substitution that loses information.

| # | Content shape | Use when the material is… | Not this |
| :--- | :--- | :--- | :--- |
| 1 | **One claim** | a single sentence the audience must take away (a thesis, a puzzle, a verdict) | three bullets that dilute it |
| 2 | **Definition** | a term with its author's definition and one concrete example | the term buried in a bullet list without the example |
| 3 | **Theory primer** | background theory the audience has not met, explained in plain words, with where it appears in this week's readings | skipping it because "they should know" |
| 4 | **Two-axis typology** | a classification with two dimensions, each with 2–3 values, and a case or label in each cell (2×2, 3×3, payoff matrix) | a comparison table with the axes flattened into row labels, or a bullet per cell |
| 5 | **Spectrum** | a continuum between two poles with positions marked along it (benevolent ↔ coercive, unipolar ↔ multipolar) | a two-column "A vs B" that hides the middle positions |
| 6 | **Two-sided contrast** | exactly two positions, authors or cases set against each other on the same points, including a reading's claims against its weaknesses | a two-row attribute table when the point is the contrast, not the attributes |
| 7 | **Multi-item comparison** | three or more items compared on the same two or more attributes | this is the one place a comparison table belongs; do not use one for shapes 4–6 |
| 8 | **Process / causal chain** | steps or causes in a fixed order, each leading to the next, or a redrawn source figure | a numbered list, which loses the arrows |
| 9 | **Timeline** | events on a date axis, where the intervals matter | a table with a year column |
| 10 | **Levels / hierarchy** | nested or stacked layers (levels of analysis, tiers of a system) | cards side by side, which reads as peers, not levels |
| 11 | **Numbers** | a few figures that carry the argument, or a worked numerical example | numbers inside prose |
| 12 | **Quotation** | the author's own words are the evidence | a paraphrase in a bullet |
| 13 | **Discussion question** | a contested claim, two defensible positions, and a prompt to take a side | a comprehension question with a page reference |
| 14 | **Section break** | a change of chapter, the title or the close | none — do not skip breaks in a deck over ~12 slides |
| 15 | **Framework overview** | one organising idea with the four or more parts that hang from it, each named, glossed and sourced (a theoretical framework, a research design, the map of a literature) | splitting it across slides, which shows the parts and loses that they belong to one frame |

## Anti-patterns

Each of these has appeared in a real deck; each loses information the source had.

1. **Typology as bullets or as a comparison table.** A classification with two
   axes has cells; a list or an attribute table has no cells, so the reader
   cannot see which combination a case belongs to. Plan shape 4.
1. **Dropping the example to fit.** A definition without its example is not
   shorter, it is unverifiable. Write the row whole; whether it fits is the
   design stage's finding, not a reason to trim the evidence here.
1. **Splitting what is one thing.** Six theories under one main theory, the
   cells of a typology, the rows of a comparison: the relation is the content,
   and two slides of three show neither the whole nor the relation. Plan shape
   15, 4 or 7 as one row.
1. **Same shape on more than three consecutive slides.** Usually a sign the
   content was poured into whatever came first. Re-read the shapes.
1. **Everything is a "文獻 × 屬性" table.** One such table orients the
   audience; six in a row are a spreadsheet read aloud. Keep shape 7 to
   roughly a third of content slides.
1. **More than six unstructured bullets.** A flat list past six gives the
   audience no way in, at any density. Give the items their structure (groups,
   a category per item, a table) rather than cutting them; at 密度 低, where the
   slide must be taken in while listening, move the detail into knowledge
   points the row's 講者備註 names.
1. **Writing to the layouts you remember.** Three cards because cards come in
   threes, no source line because cards have no source field: that is the
   design stage's constraint leaking into the content. Write the items and
   fields the content has ([`content-syntax.md`](content-syntax.md)).
1. **A discussion question that tests reading.** "What does the author say on
   p. 36?" produces silence. Give a contested claim and two positions, then
   ask which side they take (shape 13).
