#!/usr/bin/env python3
"""Print what the audience can read on each slide, for the comprehension test.

    ./fw deck-text [<talk>]                 print to stdout
    ./fw deck-text [<talk>] --out <file>    write a Markdown file instead

The comprehension test (deck-svg § Run & verify, 複述測驗) gives an isolated
reader only the words on the slides and asks it to restate, slide by slide,
who did what to whom. The reader must not see speaker notes, data-label, the
storyboard or the manuscript, because any of them fills in exactly the subject,
object or definition the slide dropped, and the gap would go unnoticed. So this
prints visible text only: SVG labels included, presenter chrome (.hero__hint),
aria-hidden decoration, <style>, <script> and <defs> left out. Every beat of a
lively deck is included, because the test reads the finished slide.
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import rel, resolve_talk  # noqa: E402

SKIP_TAGS = {"style", "script", "defs", "template", "title"}
# Elements that start a new line in the extracted text. Table cells get a
# visible separator instead, so a row stays one line the reader can follow.
BREAK_TAGS = {"p", "h1", "h2", "h3", "h4", "li", "tr", "text", "blockquote", "cite",
              "div", "br", "time", "figcaption", "caption", "dt", "dd"}
CELL_TAGS = {"td", "th"}
# Inline elements that deck.css lays out as separate labels (the topbar's
# section and chapter names, a card's tag); without a break they would read
# as one run-together phrase the audience never sees.
BREAK_CLASSES = {"eyebrow", "chap", "tag"}
VOID_TAGS = {"br", "img", "hr", "input", "meta", "link", "source", "wbr", "path",
             "rect", "circle", "line", "ellipse", "polygon", "polyline", "use", "stop"}
SECTION = re.compile(r'<section\b[^>]*\bclass="slide\b[^"]*"[^>]*>(.*?)</section>', re.S)
HEADER = """# 投影片畫面文字

<!-- 由 ./fw deck-text 從 {deck} 抽出：只含台下看得到的字，不含講者備註與 data-label。
     複述測驗只給審查者這個檔案（deck-svg § Run & verify）；換行只表示版面分隔，｜ 是表格欄位。 -->
"""


def hidden(tag: str, attrs: list[tuple[str, str | None]]) -> bool:
    a = dict(attrs)
    classes = (a.get("class") or "").split()
    return tag in SKIP_TAGS or a.get("aria-hidden") == "true" or "hero__hint" in classes


class VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip: list[str] = []  # open tags that hide their subtree

    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            if tag == "br" and not self.skip:
                self.out.append("\n")
            return
        if self.skip or hidden(tag, attrs):
            self.skip.append(tag)
            return
        classes = set((dict(attrs).get("class") or "").split())
        if tag in BREAK_TAGS or classes & BREAK_CLASSES:
            self.out.append("\n")
        elif tag in CELL_TAGS:
            self.out.append(" ｜ ")

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and not self.skip:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if self.skip:
            if tag == self.skip[-1]:
                self.skip.pop()
            return
        if tag in BREAK_TAGS:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            # ASCII whitespace only: an ideographic space (U+3000) is layout the
            # author typed on purpose, so it stays.
            self.out.append(re.sub(r"[ \t\r\n]+", " ", data))

    def text(self) -> str:
        lines = (ln.strip(" ") for ln in "".join(self.out).split("\n"))
        return "\n".join(ln for ln in lines if ln)


def slide_texts(html: str) -> list[str]:
    stage = re.search(r"<deck-stage\b.*?</deck-stage>", html, re.S)
    texts = []
    for body in SECTION.findall(stage.group(0) if stage else html):
        p = VisibleText()
        p.feed(body)
        p.close()
        texts.append(p.text())
    return texts


def render(deck_name: str, texts: list[str]) -> str:
    parts = [HEADER.format(deck=deck_name)]
    for i, t in enumerate(texts):
        parts.append(f"## 第 {i} 張\n\n{t or '（沒有文字）'}\n")
    return "\n".join(parts)


def main() -> None:
    args = sys.argv[1:]
    out = None
    if "--out" in args:
        i = args.index("--out")
        if i + 1 >= len(args):
            sys.exit("--out needs a file path")
        out = Path(args[i + 1])
        del args[i:i + 2]
    _unit, talk = resolve_talk(args[0] if args else None)
    deck = talk / "deck.html"
    if not deck.is_file():
        sys.exit(f"no deck.html in {rel(talk)}")
    texts = slide_texts(deck.read_text(encoding="utf-8"))
    md = render(rel(deck), texts)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"{len(texts)} slides -> {out}")
    else:
        sys.stdout.write(md)


if __name__ == "__main__":
    main()
