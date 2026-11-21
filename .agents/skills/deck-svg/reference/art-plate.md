# Art plate — a generated picture under a slide's content

A plate is a picture that sets the scene of a slide: vehicles in mist under a
slide about military aid, a container port under one about supply chains. It
is a design-stage choice (`art:` in 畫面內容), so it changes no word and does
not touch the author's sign-off.

## What a plate may show

A plate carries **atmosphere and nothing the argument rests on**. Do not put a
map, a border, a chart, a flag, an arrow, a number or any lettering in it:
a generated map draws borders and routes that are wrong, nothing in the Model
backs them, and the audience reads a picture on a slide as a claim. A figure
that carries a fact is content, so it is written in the storyboard and drawn
as SVG (`L-CANVAS`, the **diagram** skill). Keep recognisable people out as
well.

## Where it goes

`./fw deck-compile` lays the plate out **below the content, in the height the
row leaves free**, and fades its top edge into the slide. No text sits on it,
so the contrast check keeps reading the plain slide colour. Measured on a
404-character slide (2026-11-21): a picture behind the text had to stay under
20% strength for the weakest text colour to keep 4.5:1, and at that strength a
photograph could not be seen.

So a plate needs room. `deck.html#debug` reports `art = thin` and the slide
(`artBad`) when the band is under 240px; take the picture off that row, since
shrinking the row to make room would change what the author signed. Rows at
密度 高 are often full; put plates on the cover, the section breaks and the
rows that carry one point.

## Slots

| Slot | Value |
| :--- | :--- |
| `art` | A file in the talk, or up to three (`art: art/a.jpg, art/b.jpg` or a list) shown side by side, one under each column of a three-part row. |
| `art_ground` | `dark` (default): a light subject on black. `light`: a dark subject on white. It names how the file was made, not the theme. |

The file is grayscale. The slide draws it as **one colour, the slide's chapter
colour, with the picture's brightness as its opacity** (an SVG filter the
compiler writes into the slide), so the same file follows the chapter colour
and every theme of the `c` key. A CSS mask would be simpler and does not work:
a browser refuses a mask image read from `file://`, which is how a deck is
opened (Chromium 149, 2026-11-21).

A photograph keeps its natural look only on the ground it was made for, and
turns into a soft negative in themes of the other polarity; line art looks the
same in both. Make the plate for the deck's default theme.

## Making one

Use either of the framework's image backends (framework `AGENTS.md`, image
generation): Codex (gpt-image-2) or agy (Gemini's nano banana). A plate has no
lettering, so either will do. Make one call per plate and look at each result
before using it. These prompts kept the subject low and the rest empty on both
backends (2026-11-21, five images, each on the first try); change only the
subject line.

Dark ground, photograph:

```text
Atmospheric background plate for a presentation slide. Monochrome grayscale
photograph, low contrast, soft haze, matte, no bright highlights. The subject
sits only in the bottom third of the frame. The upper two thirds are empty
smooth dark fog without any detail, fading to pure black at the top edge and
at the left and right edges. Subject: <what is in the scene>. No text, no
letters, no numbers, no captions, no logos, no flags, no maps, no borders or
country outlines, no charts, no user interface, no watermark, no close-up
faces.
```

Light ground, photograph: the same with `high-key … pale mist … no deep
blacks … empty smooth pale fog … fading to pure white`, and `art_ground: light`.

Line art (either theme):

```text
Background plate for a presentation slide. Fine white line engraving on a pure
black ground, like a technical etching: thin even lines, no grey fills, no
shading blocks. The subject sits only in the bottom third of the frame. The
upper two thirds are empty pure black. Subject: <what is in the scene>.
<the same list of exclusions>
```

Then:

1. Save it under the talk (`<talk>/art/`), as a JPEG about 1600px wide. The
   generators return a PNG of 1–1.5 MB and the JPEG is 60–180 KB; the compiler
   warns above 600 KB because the file is committed to the course repository.
1. Name it in the row: `art: art/port.jpg`.
1. Say where the pictures come from, once, in 前提:
   `- 情境圖：AI 生成（<tool>），僅作氣氛，不代表實際場景`. The compiler prints
   that line on the last slide and warns while it is missing, because the
   audience cannot tell a generated scene from a photograph of the event.
   This bullet is the design stage's to write; it is outside the sign-off.
1. Compile and open `deck.html#debug`: check `art`, and look at the slide in
   the default theme and one theme of the other polarity.
