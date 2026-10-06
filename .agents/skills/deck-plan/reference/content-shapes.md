# Content shapes — 內容形狀

A slide's **content shape** is a property of the material, so it is decided in
the storyboard, before any slide exists and whichever engine renders it. Each
View then maps the shape to its own layout: deck-svg through
`reference/slide-patterns.md` § Shape → pattern, an image deck through the
layout line of the slide's prompt, the Beamer fallback through its frame.

**The rule:** the shape of the content chooses the layout. If the View has no
layout for a shape, add one to the View (in deck-svg, a component in
`deck.css`) — never reshape the content to fit the layout that is easiest to
produce. An agent working from a list of layouts alone reaches for bullets,
cards and comparison tables for everything, and the deck ends up with a 3×3
typology squeezed into a table and the examples cut to make room; the author
then cannot recognise the source in the slides. Naming the shape first, in a
table the author reviews, is what stops that.

## Catalogue

Fourteen shapes cover nearly every slide in a seminar, thesis or reading-guide
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

## Anti-patterns

Each of these has appeared in a real deck; each loses information the source had.

1. **Typology as bullets or as a comparison table.** A classification with two
   axes has cells; a list or an attribute table has no cells, so the reader
   cannot see which combination a case belongs to. Plan shape 4.
1. **Dropping the example to fit.** A definition without its example is not
   shorter, it is unverifiable. If the slide is full, split it into two rows;
   do not trim the evidence.
1. **Same shape on more than three consecutive slides.** Usually a sign the
   content was poured into whatever came first. Re-read the shapes.
1. **Everything is a "文獻 × 屬性" table.** One such table orients the
   audience; six in a row are a spreadsheet read aloud. Keep shape 7 to
   roughly a third of content slides.
1. **More than six bullets.** Past six the slide is a document. Move the
   detail to 口說重點 or split the row.
1. **A discussion question that tests reading.** "What does the author say on
   p. 36?" produces silence. Give a contested claim and two positions, then
   ask which side they take (shape 13).
