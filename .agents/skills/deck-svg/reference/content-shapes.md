# deck-svg content shapes — 內容形狀 → 版型

`slide-patterns.md` lists what CSS classes exist. This file answers the question
that comes first: **what does the content look like, and which pattern fits that
shape?** Read it while writing the storyboard, before touching `deck.html`.

**The rule:** the shape of the content chooses the layout. If no pattern fits,
add a component to `asset/deck.css` — never reshape the content to fit the
pattern that is easiest to type. An agent working from the class list alone
reaches for bullets, cards and `table.cmp` for everything, and the deck ends up
with a 3×3 typology squeezed into a comparison table and the examples cut to
make room; the author then cannot recognise the source in the slides. Keying the
choice on content shape is what stops that.

## Catalogue

Fourteen shapes cover nearly every slide in a seminar, thesis or reading-guide
deck. The **Use when** column is the test; the **Pattern** column is what to
build; the **Not** column is the substitution that loses information.

| # | Content shape | Use when the material is… | Pattern (classes) | Not this |
| :--- | :--- | :--- | :--- | :--- |
| 1 | **One claim** | a single sentence the audience must take away (a thesis, a puzzle, a verdict) | `.claim` (+ one `.lead` line beneath) | three bullets that dilute it |
| 2 | **Definition** | a term with its author's definition and one concrete example | `.defn` (`.term` + `.example`) | the term buried in a bullet list without the example |
| 3 | **Theory primer** | background theory the audience has not met, explained in plain words, with where it appears in this week's readings | `.grid.two`/`.three` of `.card` (`.tag` = theory name, `p` = plain-language explanation, `ul.clean` = where it appears) | skipping it because "they should know" |
| 4 | **Two-axis typology** | a classification with two dimensions, each with 2–3 values, and a case or label in each cell (2×2, 3×3, payoff matrix) | `.matrix` (`.axis-y`, `table`, `.axis-x`; `td.hi` for the highlighted cell) | `table.cmp` with the axes flattened into row labels, or a bullet per cell |
| 5 | **Spectrum** | a continuum between two poles with positions marked along it (benevolent ↔ coercive, unipolar ↔ multipolar) | `.spectrum` (`.marks` > `.mark`, `.bar`, `.ends`) | a two-column "A vs B" that hides the middle positions |
| 6 | **Two-sided contrast** | exactly two positions, authors or cases set against each other on the same points | `.cols.split` of `.colblock`, or `.grid.two` of `.card`; for a reading's claims against its weaknesses, `.colblock.against` + `.verdict` | a 2×n `table.cmp` when the point is the contrast, not the attributes |
| 7 | **Multi-item comparison** | three or more items compared on the same two or more attributes | `table.cmp` (`caption`, header row, row-header `th`; `.tight` for six or more rows) | this is the one place `table.cmp` belongs; do not use it for shapes 4–6 |
| 8 | **Process / causal chain** | steps or causes in a fixed order, each leading to the next | `.flowdiag` (`.flownode` + `.flowarrow`), or inline `svg.art.dg` for branches or a redrawn source figure | a numbered list, which loses the arrows |
| 9 | **Timeline** | events on a date axis, where the intervals matter | `.timeline` of `.tl` (`time`, `b`, `p`) | a table with a year column |
| 10 | **Levels / hierarchy** | nested or stacked layers (levels of analysis, tiers of a system) | `.tiers` of `.tier` (`h3` + `p`) | cards side by side, which reads as peers, not levels |
| 11 | **Numbers** | a few figures that carry the argument | `.stats` of `.stat` (`.stats.four` for four); a worked numerical example goes in `.matrix` | numbers inside prose |
| 12 | **Quotation** | the author's own words are the evidence | `blockquote.pull` + `cite` with page | a paraphrase in a bullet |
| 13 | **Discussion question** | a contested claim, two defensible positions, and a prompt to take a side | `.debate` (`.claim`, `.sides` > `.side`, `.ask`) | a comprehension question with a page reference |
| 14 | **Section break** | a change of chapter | `.slide` with `.kicker` only, or `.finale` for the close | none — do not skip breaks in a deck over ~12 slides |

Diagrams and generated art are covered in the presentation protocol
(`assets/templates/presentation/presentation-protocol.md` § Diagrams).

## Storyboard first

Write `<unit>/storyboard.md` before `deck.html`. It opens with a short
**前提** list — audience, time limit, room and projection (type floor, light or
dark theme), wording conventions — because those decide type size, slide count
and terms, and changing them after the slides exist means redoing the deck.
Keep 前提 as bullets: `./fw build` counts every table row as a slide. Then one
row per slide:

| # | 來源段落 | 內容形狀 | 版型 | 講 | 畫面內容 | 口說重點 | AI 協助 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 5 | `notes/key.md` § 論證怎麼走 → 叁 | 4 Two-axis typology | `.matrix` 3×3 | 2 min | axis y = 極數, axis x = 權威密度; highlight the cell the author's case falls in | why the axes, the author's case with page, transition to the critique, expected question on the empty cell | AI drafted the cell labels; author chose the axes and checked them against the source |

**畫面內容** is what appears on the slide; **口說重點** is what the talk says
— explanation, citations with locators, transitions, anticipated questions.
Once on-slide text is kept sparse, all of that moves to the speaker notes, so
the notes carry the talk and must be visible at storyboard review; they are
written out in full into `#speaker-notes` while building the deck. The **AI
協助** column records what AI drafted or verified and what the author wrote or
changed, because courses increasingly require disclosing AI use per paragraph
or slide, and noting it while storyboarding is more reliable than
reconstructing it afterwards.

The row is the traceability the author asked for: every slide points back to
the paragraph it condenses, and the shape column makes the layout choice
visible **before** the slide is built, so an unfitting choice is caught at
review rather than discovered as odd content on a finished slide. The author
signs off the storyboard; only then does `deck.html` get written.

`./fw build` on a presentation unit checks that the storyboard exists and that
the deck does not lean on one pattern (see § Anti-patterns); it cannot judge
whether the shape was chosen well — that is the storyboard review.

## Anti-patterns

Each of these has appeared in a real deck; each loses information the source had.

1. **Typology as bullets or as `table.cmp`.** A classification with two axes
   has cells; a list or an attribute table has no cells, so the reader cannot
   see which combination a case belongs to. Use `.matrix`.
1. **Dropping the example to fit.** A definition without its example is not
   shorter, it is unverifiable. If the slide is full, split it; do not trim the
   evidence.
1. **Same pattern on more than three consecutive slides.** Usually a sign the
   content was poured into whatever came first. Re-read the shapes.
1. **Everything is a "文獻 × 屬性" table.** One such table orients the
   audience; six in a row are a spreadsheet read aloud. Cap `table.cmp` at
   roughly a third of content slides.
1. **More than six bullets.** Past six the slide is a document. Move the detail
   to speaker notes or split the slide.
1. **A discussion question that tests reading.** "What does the author say on
   p. 36?" produces silence. Give a contested claim and two positions, then ask
   which side they take (`.debate`).
