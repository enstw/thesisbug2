#!/usr/bin/env python3
"""Render a signed-off storyboard as a Slidev project (a derived View).

    ./fw deck-slidev [<talk>]     write <talk>/slidev/ from <talk>/storyboard.md

Slidev is a View like any other: it reads the same storyboard.md that
`./fw deck-compile` reads and the speaker notes `./fw deck-notes` assembled in
deck.html, and writes <talk>/slidev/slides.md with the project files Slidev
needs. slides.md is never edited by hand; change the storyboard and run this
again. deck.html stays the gated deck.

Slidev needs Node and its own packages, which this command does not install:

    cd <talk>/slidev && pnpm install
    pnpm dev                                  # present in the browser
    pnpm exec slidev export slides.md --format png --executable-path <chromium>
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _deck_outline import Item, Outline, deck_notes, outline_storyboard  # noqa: E402
from _deck_steps import premise_value  # noqa: E402
from _paths import course_root, rel, resolve_talk  # noqa: E402

OUT_DIR = "slidev"
FONT = "asset/ENSFont.woff2"
# The `fact` layout prints its heading several times the body size: right for a figure or
# a short term, three lines of it for a long one, which pushes the rest off the slide.
FACT_MAX = 8

# Pinned to the major versions this View was checked against; `pnpm install` resolves
# within them. playwright-chromium is what `slidev export` drives.
PACKAGE = {
    "name": "deck-slidev",
    "private": True,
    "type": "module",
    "scripts": {"dev": "slidev slides.md --open", "build": "slidev build slides.md",
                "export": "slidev export slides.md"},
    "devDependencies": {"@slidev/cli": "^51.8.2", "@slidev/theme-default": "^0.25.0",
                        "playwright-chromium": "^1.65.0"},
}

# The house font is copied into public/ so Slidev serves it at the site root; the copy
# and the installed packages are regenerated, so they stay out of git.
GITIGNORE = "node_modules/\ndist/\npublic/ENSFont.woff2\n*-export/\n*.pdf\n"

# pnpm refuses an install whose packages want to run build scripts nobody decided on.
# esbuild needs its script; playwright-chromium's downloads a browser, which is left to
# the presenter: pass `--executable-path` to `slidev export`, or run
# `pnpm exec playwright install chromium` once.
WORKSPACE = "allowBuilds:\n  esbuild: true\n  playwright-chromium: false\n"

STYLE = """/* 由 ./fw deck-slidev 產生；不要手改。 */
@font-face {
  font-family: 'ENSFont';
  src: url('/ENSFont.woff2') format('woff2');
  unicode-range: U+3000-303F, U+3040-309F, U+30A0-30FF, U+3400-4DBF, U+4E00-9FFF, U+F900-FAFF, U+FF00-FFEF;
}
/* ENSFont 只有一個字重：瀏覽器合成的粗體在楷體上會糊，所以強調改用顏色。 */
.slidev-layout { font-family: 'ENSFont', 'Helvetica Neue', system-ui, sans-serif; font-synthesis-weight: none; }
.slidev-layout strong { font-weight: inherit; color: #0e7490; }
.slidev-layout h1 { line-height: 1.25; }
.slidev-layout .eyebrow { font-size: 0.85rem; opacity: 0.65; letter-spacing: 0.04em; }
.slidev-layout .cite { font-size: 0.8rem; opacity: 0.6; margin-top: 1rem; }
.slidev-layout blockquote { margin-top: 1.2rem; }
/* fact 版面整頁置中：清單自成一塊、塊內靠左，項目符號才貼著字。 */
.slidev-layout.fact ul, .slidev-layout.fact ol { display: inline-block; text-align: left; margin-top: 1rem; }
"""

# A slot is plain text; Slidev reads slides.md as Markdown and then as a Vue template,
# so both syntaxes are escaped: a stray `*` must not start emphasis, `<` a tag, `{{` an
# expression, `$` a formula. An entity does not stop `{{`: Markdown decodes it back
# to a brace before Vue compiles the slide, so the pair goes inside a `v-pre` element.
_ENTITIES = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}
_MUSTACHE = "<span v-pre>{{</span>"
_MD_SPECIAL = re.compile(r"([\\`*_\[\]#|~$])")
# Slidev turns on Markdown's typographer, which would print `--` as a dash, `...` as an
# ellipsis, `(c)` as ©, `+-` as ±.
_TYPOGRAPHER = re.compile(r"(?<=[-+])-|(?<=\.)\.|\((?=(?:c|r|tm|p)\))", re.I)
_LINE_START = re.compile(r"^(\d+)([.)])|^([-+=:])")


def md(text: str) -> str:
    """Slot text as inline Markdown that prints exactly the characters it was given."""
    text = " ".join(text.split())
    text = _MD_SPECIAL.sub(r"\\\1", text)
    text = _TYPOGRAPHER.sub(lambda m: "\\" + m.group(0), text)
    text = "".join(_ENTITIES.get(ch, ch) for ch in text).replace("{{", _MUSTACHE)
    # A paragraph that opens with `1.` or `-` would become a list, `---` a slide break.
    return _LINE_START.sub(lambda m: f"{m.group(1)}\\{m.group(2)}" if m.group(1) else f"\\{m.group(3)}", text)


def _item(item: Item) -> str:
    head = "｜".join(md(p) for p in (item.tag, item.head) if p)
    if head and item.body:
        return f"**{head}**：{md(item.body)}"
    return f"**{head}**" if head and item.focus else head or md(item.body)


def _list(o: Outline) -> list[str]:
    if not o.items:
        return []
    mark = "1." if o.ordered else "-"
    lines = [f"{mark} {_item(it)}" for it in o.items]
    # 動態 asks for a step-by-step reveal: Slidev's own click steps
    return ["<v-clicks>", "", *lines, "", "</v-clicks>"] if o.steps else lines


def _closing(o: Outline) -> list[str]:
    if not o.closing:
        return []
    return [f"> **{md(o.closing_label)}**　{md(o.closing)}" if o.closing_label else f"> {md(o.closing)}"]


def _tail(o: Outline) -> list[list[str]]:
    blocks = [_closing(o)]
    if o.meta:
        blocks.append([md(o.meta)])
    if o.cite:
        blocks.append([f'<div class="cite">{md(o.cite)}</div>'])
    return blocks


def slide_body(o: Outline) -> tuple[str, list[list[str]]]:
    """A row as (Slidev layout, blocks of Markdown lines). The layout names are the
    default theme's; a row no special layout fits is a titled list."""
    title = [f"# {md(o.title)}"]
    eyebrow = [f'<div class="eyebrow">{md(o.label)}</div>'] if o.label else []
    lead = [md(o.lead)] if o.lead else []

    if o.kind in ("cover", "section"):
        return o.kind, [title, lead, [md(o.meta)] if o.meta else []]
    if o.kind == "finale" and not o.items:
        return "center", [title, lead, *_tail(o)]
    if o.sides and len(o.items) == 2:
        left, right = o.items
        cols = ['<div class="grid grid-cols-2 gap-8">', "<div>", "", f"### {md(left.head)}", "", md(left.body),
                "", "</div>", "<div>", "", f"### {md(right.head)}", "", md(right.body), "", "</div>", "</div>"]
        return "default", [eyebrow, title, lead, cols, *_tail(o)]
    if o.quote:
        return "quote", [eyebrow, [f"# {md(o.quote)}"], [md(o.title)], lead, _list(o), *_tail(o)]
    if o.big:
        return "fact" if len(o.big) <= FACT_MAX else "default", [
            eyebrow, [f"# {md(o.big)}"], [md(o.big_label)] if o.big_label else [],
            [f"**{md(o.title)}**"], lead, _list(o), *_tail(o)]
    big_label = [md(o.big_label)] if o.big_label else []
    return "default", [eyebrow, title, big_label, lead, _list(o), *_tail(o)]


def note_comment(note: str) -> list[str]:
    """The slide's trailing HTML comment is its presenter note in Slidev. Each line is
    its own paragraph, because Markdown would run the note's lines together."""
    lines = [ln.strip() for ln in note.replace("-->", "--＞").splitlines() if ln.strip()]
    return ["<!--", "\n\n".join(lines), "-->"] if lines else []


def render_slides(outlines: list[Outline], notes: list[str], title: str) -> str:
    head = ["theme: default", f"title: {json.dumps(title, ensure_ascii=False)}", "aspectRatio: 16/9",
            "canvasWidth: 980", "colorSchema: light", "fonts:", "  sans: ENSFont", "  local: ENSFont", "  provider: none"]
    slides: list[str] = []
    for i, (o, note) in enumerate(zip(outlines, notes)):
        layout, blocks = slide_body(o)
        front = [*(head if i == 0 else []), f"layout: {layout}"]
        body = "\n\n".join("\n".join(b) for b in [*blocks, note_comment(note)] if b)
        slides.append("---\n" + "\n".join(front) + "\n---\n\n" + body + "\n")
    return "\n".join(slides)


def write_view(talk: Path, slides: str) -> Path:
    out = talk / OUT_DIR
    (out / "styles").mkdir(parents=True, exist_ok=True)
    (out / "public").mkdir(exist_ok=True)
    (out / "slides.md").write_text(slides, encoding="utf-8")
    (out / "package.json").write_text(json.dumps(PACKAGE, indent=2) + "\n", encoding="utf-8")
    (out / "styles" / "index.css").write_text(STYLE, encoding="utf-8")
    (out / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (out / "pnpm-workspace.yaml").write_text(WORKSPACE, encoding="utf-8")
    if (talk / FONT).is_file():
        shutil.copyfile(talk / FONT, out / "public" / "ENSFont.woff2")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("talk", nargs="?", help="the talk to render (defaults to current)")
    args = parser.parse_args()

    root = course_root()
    _unit, talk = resolve_talk(args.talk)
    storyboard = talk / "storyboard.md"
    if not storyboard.is_file():
        sys.exit(f"{rel(talk, root)} has no storyboard.md: the Slidev View renders a signed-off storyboard "
                 "(deck-plan skill), it does not plan a talk")
    text = storyboard.read_text(encoding="utf-8")
    outlines, warnings = outline_storyboard(text)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    if not outlines:
        sys.exit(f"{rel(storyboard, root)} has no row with a Layout Catalog code; the Slidev View renders "
                 "catalog rows only (deck-plan § 版型)")

    notes, problem = deck_notes(talk, len(outlines))
    if problem:
        print(f"warning: no speaker notes in the Slidev View: {problem}. Run ./fw deck-compile "
              f"{rel(talk, root)} and ./fw deck-notes {rel(talk, root)} first, then this again.",
              file=sys.stderr)
    if not (talk / FONT).is_file():
        print(f"warning: {rel(talk / FONT, root)} is missing, so the slides fall back to a system font; "
              f"run ./fw deck-refresh {rel(talk, root)}", file=sys.stderr)

    title = next((o.title for o in outlines if o.kind == "cover" and o.title), "")
    out = write_view(talk, render_slides(outlines, notes, title or premise_value(text, "標題") or talk.name))
    print(f"{len(outlines)} storyboard rows → {len(outlines)} slides")
    print(f"wrote {rel(out / 'slides.md', root)}")
    print(f"next: cd {rel(out, root)} && pnpm install && pnpm dev")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
