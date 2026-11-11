---
name: reader
description: >
  Renders a source transcript (refs/<key>.md) as an offline HTML page made for
  reading with ./fw reader: page chips at every printed-page break, paragraphs cut by a
  break rejoined, footnotes previewed in place, a table of contents, adjustable
  type size, Ming/Hei faces and dark mode. Use when the author wants to read,
  project or present an assigned reading or source as a page, or asks to
  「把原文用 HTML 呈現」. The transcript stays the source; the page is regenerated.
---

# reader — a source transcript as a reading page

`./fw reader` turns a transcript in the `source-kit` format into one HTML page whose only job is to be easy to read: on a laptop while preparing, on a phone, or projected in class while the author walks through the text. **Run it rather than hand-writing a page**: a hand-built page is a second copy of the transcript that keeps the old text after the next correction to `refs/<key>.md`, and it is where page numbers quietly go wrong.

```bash
./fw reader <key>                      # finds the key's refs/<key>.md in a unit or library/
./fw reader <unit>/refs/<key>.md       # or name the transcript
./fw reader <key> --out <file.html>    # default: _output/<key>.html
```

The command prints the output path and a count of pages, rejoined paragraphs, notes and headings. It warns when a note has no reference in the text, which usually means an OCR'd `<sup>` mark went missing; fix that in the transcript, not in the page.

## What the page does for the reader, and why

- **Page chips at the printed page.** Every `[Page N start]` marker becomes a `p. N` chip, shifted by the transcript's `marker_offset`, so it shows the number a citation uses. The top bar shows the page currently being read. Readers who are checking a locator, or the class following along in the printed book, need the page number at the point of reading, not at the bottom of a scan.
- **A paragraph cut by a page break is put back together.** When a paragraph ends without closing punctuation and the next page starts with a paragraph, the two are joined, with the chip at the exact character where the page turned. A hyphenated Latin word is rejoined without its hyphen. A page break in mid-sentence breaks the reader's train of thought and has nothing to do with the argument.
- **Footnotes leave the flow but stay one gesture away.** Page-bottom notes (`> <sup>N</sup> …` blocks, or Markdown `[^N]`) go to a numbered list at the end, each tagged with its page. A note number previews on hover, or on tap on a phone, and links to the list. Notes printed between the halves of a split paragraph would otherwise interrupt it. Numbering that restarts on each page is matched to the note on the same page.
- **Line length and spacing for CJK reading.** The text column is about 40 characters wide, with line-height 1.95 and left-aligned text. Justified text spreads the letters of any line that runs into a long English name or URL, which is common in these sources.
- **Reader controls.** `A−`/`A＋` (or `-`/`+`) change the type size from 14 to 34 px, `明`/`黑` (`f`) switches between Ming and Hei faces, and `◐` (`d`) toggles dark mode. The browser remembers the choices. A projector at the back of a room and a phone in hand need different settings, and only the reader knows which applies.
- **Structure you can navigate.** A table of contents from the headings sits on the left on wide screens and highlights the current section. A thin bar shows progress through the document. A print stylesheet drops the controls.
- **Provenance stays visible.** The transcript's leading `<!-- … -->` notes (how it was made, which misprints were kept on purpose) open under 「關於這份文本」, and the citation line comes from the `references.bib` entry. A reader who meets an odd character should be able to tell whether the original printed it that way or the transcription got it wrong.

## Rules

1. **The transcript is the only source.** Correct text in `refs/<key>.md` (through `safe-edit` for multi-spot edits), then rerun the command. Never edit the HTML; its `generator` meta tag says so.
1. **Output goes to `_output/`, which is gitignored.** The page holds the full text of a copyrighted work, and the house font is 13 MB. The command copies the font once into `_output/fonts/`; a page written into a presentation unit with `--out` uses that unit's `asset/ENSFont*.woff2` instead. If the font is missing, the page falls back to system fonts and still reads well. Commit a page only when the author asks, and only to the private course repo.
1. **Do not publish the page or send it outside the course without the author's say.** Course reading material is usually for enrolled students' private study only (check `COURSE.md`). A transcript's full text in a public URL is redistribution, whatever the page looks like.
1. **Raw HTML in a transcript is escaped**, apart from the `<sup>` footnote marks. A transcript is OCR of someone else's document and must not run code in the reader's browser.
1. **Check the page by looking at it** when a browser capability is available. Take screenshots at desktop and phone width and in both themes, then compare the first split paragraph and one footnote preview against the transcript. If no browser is available, report the check as not done.

## Transcript format it reads

The `source-kit`/`pdf-to-markdown` conventions: `**[Page N start]**`, `**[Page N end, Page M start]**` and `**[Page N end]**` markers, bold or plain; an optional flat frontmatter with `marker_offset`; headings `#`–`######` (the first `#` becomes the page title); blockquotes, lists, pipe tables, fenced code, `**bold**`, `*italic*` and links. A continuation note written as `（註 N 續）` at the top of the next page's footnote block is appended to note N. Anything else renders as plain paragraphs. Nothing in the transcript is dropped.
