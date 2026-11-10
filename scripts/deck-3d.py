#!/usr/bin/env python3
"""Render a signed-off storyboard as a 3D fly-through (a derived View).

    ./fw deck-3d [<talk>]     write <talk>/deck3d/ from <talk>/storyboard.md

The 3D engine is a View like any other: it reads the same storyboard.md that
`./fw deck-compile` reads and the speaker notes `./fw deck-notes` assembled in
deck.html, and writes <talk>/deck3d/index.html (the world), presenter.html and
the two engine scripts. Nothing in deck3d/ is edited by hand; change the
storyboard and run this again. deck.html stays the gated deck.

A section row (a second L-HERO-TITLE) opens an island; every other row becomes
one scene, or several when its items each carry a heading and a body, because
the flight between scenes is what this View is for and a dense panel is not.
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _deck import SKILLS  # noqa: E402
from _deck_outline import Item, Outline, deck_notes, outline_storyboard  # noqa: E402
from _deck_steps import premise_value  # noqa: E402
from _paths import course_root, rel, resolve_talk  # noqa: E402

TEMPLATE = SKILLS / "deck-3d" / "template"
OUT_DIR = "deck3d"
COPIED = ("engine.js", "world.js", "presenter.html")
FONT = "asset/ENSFont.woff2"


def _scene(o: Outline, note: str, kicker: str, *, label: str = "", title: str = "", big: str = "",
           body: list[dict] | None = None, cite: str = "") -> dict:
    return {"label": label or f"{o.num}・{o.title}", "note": note, "kicker": kicker,
            "title": title or o.title, "big": big, "body": body or [], "cite": cite}


def _item_line(o: Outline, i: int, item: Item, text: str) -> str:
    """An item as one line; a sequence without its own tags is numbered so the order survives."""
    if item.tag:
        return f"{item.tag}｜{text}" if text else item.tag
    return f"{i}. {text}" if o.ordered else text


def _unfolds(o: Outline) -> bool:
    return sum(1 for it in o.items if it.head and it.body) >= 2


def row_scenes(o: Outline, note: str, kicker: str) -> list[dict]:
    """The scenes one storyboard row becomes. Every scene carries the row's note:
    they are stops within one row of the talk."""
    if o.sides and len(o.items) == 2:
        left, right = o.items
        return [{"label": f"{o.num}・{o.title}", "note": note, "duo": True, "kicker": kicker,
                 "title": o.title, "lead": o.lead, "left": {"h": left.head, "t": left.body},
                 "right": {"h": right.head, "t": right.body}, "foot": o.closing, "cite": o.cite}]

    lead_blocks = [{"t": t} for t in (o.big_label,) if t]
    if o.quote:
        lead_blocks.append({"t": o.quote, "lg": True})
    if o.lead:
        lead_blocks.append({"t": o.lead})

    if _unfolds(o):
        # Overview first (the headings only), then one scene per item, then the closing.
        overview = lead_blocks + [
            {"t": _item_line(o, i, it, it.head or it.body), **({"em": True} if it.focus else {})}
            for i, it in enumerate(o.items, start=1)]
        scenes = [_scene(o, note, kicker, big=o.big, body=overview, cite=o.cite)]
        for i, it in enumerate(o.items, start=1):
            head = it.head or it.body
            body = [{"t": it.body, **({"em": True} if it.focus else {})}] if it.head and it.body else []
            scenes.append(_scene(o, note, kicker, label=f"{o.num}-{i}・{head}", title=head,
                                 big=it.tag or (str(i) if o.ordered else ""), body=body))
        if o.closing:
            name = o.closing_label or o.title
            scenes.append(_scene(o, note, kicker, label=f"{o.num}-{len(o.items) + 1}・{name}",
                                 title=name, body=[{"t": o.closing, "lg": True}]))
        return scenes

    body = lead_blocks + [
        {"t": _item_line(o, i, it, "：".join(p for p in (it.head, it.body) if p)),
         **({"em": True} if it.focus else {})}
        for i, it in enumerate(o.items, start=1)]
    if o.closing:
        body.append({"t": f"{o.closing_label}｜{o.closing}" if o.closing_label else o.closing, "em": True})
    if o.meta:
        body.append({"t": o.meta})
    return [_scene(o, note, kicker, big=o.big, body=body, cite=o.cite)]


def build_deck(outlines: list[Outline], notes: list[str], fallback_title: str) -> dict:
    """The DECK object world.js lays out: a cover and islands of scenes.

    Rows before the first section row form an island without a name, which gets
    no cover stop; a storyboard without section rows is one such island.
    """
    cover = {"title": fallback_title, "sub": "", "meta": "", "note": ""}
    islands: list[dict] = []
    for o, note in zip(outlines, notes):
        if o.kind == "cover":
            cover = {"title": o.title or fallback_title, "sub": o.lead, "meta": o.meta, "note": note}
            continue
        if o.kind == "section":
            islands.append({"name": o.title, "sub": o.lead, "note": note,
                            "label": f"{o.num}・{o.title}", "scenes": []})
            continue
        if not islands:
            islands.append({"name": "", "sub": "", "note": "", "label": "", "scenes": []})
        islands[-1]["scenes"].extend(row_scenes(o, note, o.label or islands[-1]["name"]))
    return {"title": cover["title"], "cover": cover, "islands": islands}


def deck_json(deck: dict) -> str:
    """DECK as a JavaScript literal that is safe inside a <script> element: `<` cannot
    close the element, and U+2028/2029 would end a JavaScript line inside a string."""
    text = json.dumps(deck, ensure_ascii=False, indent=1)
    return text.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def render_index(deck: dict) -> str:
    host = (TEMPLATE / "host.html").read_text(encoding="utf-8")
    return host.replace("{{TITLE}}", html.escape(deck["title"])).replace("{{DECK}}", deck_json(deck))


def write_view(talk: Path, deck: dict) -> Path:
    out = talk / OUT_DIR
    out.mkdir(exist_ok=True)
    (out / "index.html").write_text(render_index(deck), encoding="utf-8")
    for name in COPIED:
        shutil.copyfile(TEMPLATE / name, out / name)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("talk", nargs="?", help="the talk to render (defaults to current)")
    args = parser.parse_args()

    root = course_root()
    _unit, talk = resolve_talk(args.talk)
    storyboard = talk / "storyboard.md"
    if not storyboard.is_file():
        sys.exit(f"{rel(talk, root)} has no storyboard.md: the 3D View renders a signed-off storyboard "
                 "(deck-plan skill), it does not plan a talk")
    text = storyboard.read_text(encoding="utf-8")
    outlines, warnings = outline_storyboard(text)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    if not outlines:
        sys.exit(f"{rel(storyboard, root)} has no row with a Layout Catalog code; the 3D View renders "
                 "catalog rows only (deck-plan § 版型)")

    notes, problem = deck_notes(talk, len(outlines))
    if problem:
        print(f"warning: no speaker notes in the 3D View: {problem}. Run ./fw deck-compile "
              f"{rel(talk, root)} and ./fw deck-notes {rel(talk, root)} first, then this again.",
              file=sys.stderr)
    if not (talk / FONT).is_file():
        print(f"warning: {rel(talk / FONT, root)} is missing, so the scenes fall back to a system font; "
              f"run ./fw deck-refresh {rel(talk, root)}", file=sys.stderr)

    title = premise_value(text, "標題") or talk.name
    deck = build_deck(outlines, notes, title)
    out = write_view(talk, deck)
    scenes = sum(len(isl["scenes"]) for isl in deck["islands"])
    print(f"{len(outlines)} storyboard rows → {len(deck['islands'])} islands, {scenes} scenes "
          f"(a long scene is split further when the page lays it out)")
    print(f"wrote {rel(out / 'index.html', root)}; presenter view: {rel(out / 'presenter.html', root)}")
    print(f"self-check: open {rel(out / 'index.html', root)}#debug and read body[data-minfont] "
          "and body[data-overflow]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
