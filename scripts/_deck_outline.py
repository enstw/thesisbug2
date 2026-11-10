"""A storyboard row as an outline: what the slide says, without how one engine lays it out.

`deck.html` is the View the gates check. The derived Views (`deck-3d`, `deck-slidev`)
show the same signed-off storyboard in another form, so they read each row through
this module instead of parsing 畫面內容 again: one reading of the slots, shared with
`deck-compile`, means a row cannot say one thing in the deck and another in a
derived View.

An outline keeps a row's text and its roles (title, lead, items, closing box,
citation) and drops what only the HTML layout uses (depth variant, column widths).
Words a renderer prints in place of an omitted head or tag (「階段 1」) are not
content and are not carried either.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    from _deck_catalog import (CATALOG, CLOSING_LABEL, DEFAULT_WORDS, ITEM_CAP, get_layout,
                               matrix_focus, matrix_note_label, note_label_text, parse_slot_payload)
except ImportError:          # imported as scripts._deck_outline (tests)
    from ._deck_catalog import (CATALOG, CLOSING_LABEL, DEFAULT_WORDS, ITEM_CAP, get_layout,
                                matrix_focus, matrix_note_label, note_label_text, parse_slot_payload)


# ---------- the storyboard table ----------

def extract_seed(storyboard_text: str, default_seed: int = 42) -> int:
    """Extract Seed from storyboard premises: - **Seed:** 42 or - Seed: 42."""
    m = re.search(r"(?im)^[-*]\s*(?:\*\*)?Seed(?:\*\*)?\s*[:：]\s*(\w+)", storyboard_text)
    if m:
        val = m.group(1).strip()
        if val.isdigit():
            return int(val)
        # If it's a string like "2026-autumn" or "r4821", hash it deterministically
        return int(hashlib.md5(val.encode("utf-8")).hexdigest()[:8], 16)
    return default_seed


def extract_storyboard_rows(storyboard_text: str) -> list[dict[str, str]]:
    """Parse rows under ## 投影片 table into list of row dicts."""
    rows: list[dict[str, str]] = []
    lines = storyboard_text.splitlines()
    in_table = False
    headers: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cols = [c.strip() for c in stripped.strip("|").split("|")]
        if not cols:
            continue
        if cols[0] == "#":
            headers = cols
            in_table = True
            continue
        if in_table and cols[0] != ":---" and not cols[0].startswith("---"):
            if cols[0].isdigit() and len(cols) >= 4:
                row_dict = {}
                for idx, h in enumerate(headers):
                    if idx < len(cols):
                        row_dict[h] = cols[idx]
                rows.append(row_dict)
    return rows


def row_title(row: dict[str, str], slots: dict[str, Any], slide_num: int) -> str:
    """The row's title: the `title` slot, else the first line of 畫面內容, else the shape name."""
    if "title" in slots:
        return slots["title"]
    first_line = row.get("畫面內容", "").split("<br>")[0].strip()
    if first_line and not first_line.startswith(("-", "*", "cards:", "items:")):
        return first_line.split(":")[-1].strip()
    return row.get("內容形狀", "") or f"投影片 {slide_num}"


def row_eyebrow(row: dict[str, str], slots: dict[str, Any]) -> str:
    """The small label over the title: an explicit slot, else the shape name without its
    number (「3 理論入門」→「理論入門」), else 「研討進度」."""
    explicit = slots.get("eyebrow") or slots.get("label") or slots.get("data_label")
    if explicit:
        return explicit
    shape = re.sub(r"^\d+\s*", "", row.get("內容形狀", "")).strip()
    return shape or "研討進度"


# ---------- the outline ----------

@dataclass
class Item:
    head: str = ""
    body: str = ""
    tag: str = ""
    focus: bool = False        # the highlighted one (the matrix's focus quadrant)

    def line(self) -> str:
        """The item as one line of text: 「tag｜head：body」 with the empty parts left out."""
        text = "：".join(p for p in (self.head, self.body) if p)
        return f"{self.tag}｜{text}" if self.tag and text else (self.tag or text)


@dataclass
class Outline:
    num: int
    layout: str
    kind: str = "content"      # cover | section | finale | content
    label: str = ""            # the row's own eyebrow; "" when the storyboard gives none
    shape: str = ""
    title: str = ""
    lead: str = ""
    big: str = ""              # the one large figure or term
    big_label: str = ""
    quote: str = ""
    items: list[Item] = field(default_factory=list)
    closing: str = ""
    closing_label: str = ""
    cite: str = ""
    meta: str = ""
    sides: bool = False        # the two items are opposing camps
    ordered: bool = False      # the items are a sequence
    steps: bool = False        # 動態 asks for a step-by-step reveal
    minutes: str = ""
    dropped: list[str] = field(default_factory=list)   # slots a text outline cannot carry


def _text(value: Any) -> str:
    return "" if value is None or isinstance(value, (list, dict)) else str(value).strip()


def _first(slots: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if slots.get(name):
            return slots[name]
    return None


def _item(raw: Any) -> Item:
    if not isinstance(raw, dict):
        return Item(head=_text(raw))
    return Item(head=_text(raw.get("head") or raw.get("label") or raw.get("point") or raw.get("raw")),
                body=_text(raw.get("body") or raw.get("desc")),
                tag=_text(raw.get("tag") or raw.get("time") or raw.get("level_name")))


def _items(raw: Any) -> list[Item]:
    return [it for it in (_item(r) for r in raw) if it.head or it.body or it.tag] if isinstance(raw, list) else []


def _lines(raw: Any) -> str:
    """A `*_lines:` list as one title: lines join directly between CJK characters, with a space otherwise."""
    if not isinstance(raw, list):
        return ""
    out = ""
    for part in (_text(r.get("text") or r.get("head")) if isinstance(r, dict) else _text(r) for r in raw):
        if out and part and not (ord(out[-1]) > 0x2E7F and ord(part[0]) > 0x2E7F):
            out += " "
        out += part
    return out


def _hero(o: Outline, slots: dict[str, Any]) -> None:
    o.title = _lines(slots.get("title_lines")) or o.title
    o.lead = _lines(slots.get("sub_lines")) or o.lead


def _bento(o: Outline, slots: dict[str, Any]) -> None:
    hero = slots.get("hero_card") or (slots.get("cards") or [{}])[0]
    subs = slots.get("sub_cards") or (slots.get("cards") or [])[1:]
    o.items = _items([hero] + list(subs if isinstance(subs, list) else []))
    if o.items:
        o.items[0].focus = True


def _vs(o: Outline, slots: dict[str, Any]) -> None:
    for name in ("side_a", "side_b"):
        side = slots.get(name) if isinstance(slots.get(name), dict) else {}
        points = side.get("points") or []
        o.items.append(Item(head=_text(side.get("camp") or side.get("camp_name")),
                            body="；".join(_text(p) for p in points) if isinstance(points, list) else _text(points)))


def _matrix(o: Outline, slots: dict[str, Any]) -> None:
    x = slots.get("axis_x") if isinstance(slots.get("axis_x"), dict) else {}
    y = slots.get("axis_y") if isinstance(slots.get("axis_y"), dict) else {}
    if x.get("name") and y.get("name"):
        o.lead = f"{_text(y['name'])} × {_text(x['name'])}"
    focus = matrix_focus(slots)
    # Quadrant numbering as the renderer places them: 1 low/low, 2 x low · y high, 3 x high · y low, 4 high/high.
    where = {1: ("low", "low"), 2: ("low", "high"), 3: ("high", "low"), 4: ("high", "high")}
    cells = slots.get("cells") if isinstance(slots.get("cells"), list) else []
    for i, cell in enumerate(cells[:4], start=1):
        item = _item(cell)
        xs, ys = (_text(x.get(where[i][0])), _text(y.get(where[i][1])))
        item.tag = " × ".join(p for p in (ys, xs) if p)
        item.focus = i == focus
        o.items.append(item)
    o.closing = _text(slots.get("deepdive_note"))
    o.closing_label = matrix_note_label(slots, focus) if o.closing else ""


def _spectrum(o: Outline, slots: dict[str, Any]) -> None:
    left, right = _text(slots.get("pole_left")), _text(slots.get("pole_right"))
    if left and right:
        o.lead = f"{left} ↔ {right}"

    def position(raw: Any) -> float:
        try:
            return float(str(raw.get("position_pct") or raw.get("pct") or 50).rstrip("%"))
        except (AttributeError, ValueError):
            return 50.0
    markers = _first(slots, ("markers", "items"))
    o.items = _items(sorted(markers, key=position)) if isinstance(markers, list) else []


def _hypothesis(o: Outline, slots: dict[str, Any]) -> None:
    hypo = slots.get("hypothesis") if isinstance(slots.get("hypothesis"), dict) else {}
    finding = slots.get("finding") if isinstance(slots.get("finding"), dict) else {}
    o.items = [
        Item(tag=_text(hypo.get("label")) or DEFAULT_WORDS["hypothesis"],
             head=_text(hypo.get("theory_expectation") or hypo.get("head")),
             body=_text(hypo.get("logic") or hypo.get("body"))),
        Item(tag=(_text(finding.get("label")) or DEFAULT_WORDS["finding"]) + "："
                 + (_text(finding.get("status")) or DEFAULT_WORDS["finding_status"]),
             head=_text(finding.get("empirical_evidence") or finding.get("head")), focus=True),
    ]


def _defn(o: Outline, slots: dict[str, Any]) -> None:
    o.big_label = _text(_first(slots, ("etymology", "context")))
    o.lead = _text(_first(slots, ("formal_definition", "defn", "body")))
    for word, names in (("positive", ("positive_example", "pos_example")),
                        ("negative", ("negative_boundary", "neg_example"))):
        text = _text(_first(slots, names))
        if text:
            o.items.append(Item(tag=DEFAULT_WORDS[word], head=text))


@dataclass(frozen=True)
class Spec:
    """Which slots of a layout fill which part of the outline, first non-empty name winning
    (the same fallback order as the layout's renderer)."""
    title: tuple[str, ...] = ("title",)
    lead: tuple[str, ...] = ()
    items: tuple[str, ...] = ()
    closing: tuple[str, ...] = ()
    cite: tuple[str, ...] = ()
    big: tuple[str, ...] = ()
    big_label: tuple[str, ...] = ()
    quote: tuple[str, ...] = ()
    meta: tuple[str, ...] = ()
    shaped: tuple[str, ...] = ()       # slots the `shape` function reads
    styling: tuple[str, ...] = ()      # slots that only steer the HTML layout
    dropped: tuple[str, ...] = ()      # content a text outline cannot carry (a drawing)
    ordered: bool = False
    sides: bool = False
    shape: Callable[[Outline, dict[str, Any]], None] | None = None

    def slots(self) -> set[str]:
        return {n for group in (self.title, self.lead, self.items, self.closing, self.cite, self.big,
                                self.big_label, self.quote, self.meta, self.shaped, self.styling,
                                self.dropped) for n in group}


COMMON = ("title", "label", "data_label", "eyebrow", "verdict_label")

SPECS: dict[str, Spec] = {
    "L-HERO-TITLE": Spec(lead=("sub", "subtitle"), meta=("meta", "author"),
                         shaped=("title_lines", "sub_lines"), shape=_hero),
    "L-FINALE-SUMMARY": Spec(title=("heading", "title"), lead=("onesentence", "verdict", "body"),
                             items=("points", "items"), styling=("points_align",)),
    "L-3CARD-VERDICT": Spec(lead=("lead",), items=("cards", "items"), closing=("verdict",)),
    "L-4CARD-GRID": Spec(lead=("lead",), items=("cards", "items"), closing=("verdict",)),
    "L-BENTO-FOCUS": Spec(lead=("lead",), closing=("verdict",),
                          shaped=("hero_card", "sub_cards", "cards"), shape=_bento),
    "L-SPLIT-ANCHOR": Spec(lead=("anchor_statement", "anchor"), items=("items", "cards"),
                           cite=("footer_cite", "cite")),
    "L-VS-CONFRONT": Spec(lead=("issue", "claim"), closing=("ask_or_verdict", "ask", "verdict"),
                          shaped=("side_a", "side_b"), shape=_vs, sides=True),
    "L-MATRIX-DEEPDIVE": Spec(shaped=("axis_x", "axis_y", "cells", "focus_quadrant", "deepdive_note",
                                      "note_label"), styling=("matrix_width",), shape=_matrix),
    "L-SPECTRUM-POLES": Spec(closing=("verdict",), shaped=("pole_left", "pole_right", "markers", "items"),
                             shape=_spectrum),
    "L-FLOW-3STAGE": Spec(lead=("lead",), items=("stages", "items"), closing=("verdict",), ordered=True),
    "L-TIMELINE-RAIL": Spec(items=("events", "items"), closing=("takeaway", "verdict"), ordered=True),
    "L-CASCADE-FUNNEL": Spec(items=("levels", "items"), closing=("core_focus", "verdict"),
                             styling=("label_width",), ordered=True),
    "L-CANVAS": Spec(lead=("lead",), closing=("verdict",),
                     dropped=("start", "lanes", "end", "svg", "caption")),
    "L-QUOTE-CRITIQUE": Spec(quote=("quote", "body"), cite=("citation", "cite"),
                             items=("critiques", "items")),
    "L-HYPOTHESIS-TEST": Spec(closing=("theoretical_puzzle", "puzzle"),
                              shaped=("hypothesis", "finding"), shape=_hypothesis),
    "L-STAT-HERO": Spec(big=("stat_number", "number"), big_label=("stat_label", "label"),
                        lead=("context",), items=("implications", "items")),
    "L-DEFN-EXAMPLE": Spec(big=("term",),
                           shaped=("formal_definition", "defn", "body", "etymology", "context",
                                   "positive_example", "pos_example", "negative_boundary", "neg_example"),
                           shape=_defn),
}


def outline_row(row: dict[str, str], idx: int) -> Outline:
    """One catalog row as an outline; raises ValueError for a layout the catalog does not have."""
    layout = get_layout(row.get("版型", "")).id
    spec = SPECS[layout]
    slots = parse_slot_payload(row.get("畫面內容", ""))
    num = int(row.get("#", idx))
    minutes = re.match(r"\s*(\d+(?:\.\d+)?)", row.get("講", ""))
    o = Outline(num=num, layout=layout, shape=row.get("內容形狀", ""),
                label=_text(slots.get("eyebrow") or slots.get("label") or slots.get("data_label")),
                ordered=spec.ordered, sides=spec.sides,
                steps="M-STEP" in row.get("動態", ""), minutes=minutes.group(1) if minutes else "")
    o.title = _text(_first(slots, spec.title)) or _text(row_title(row, slots, num))
    for part in ("lead", "closing", "cite", "big", "big_label", "quote", "meta"):
        setattr(o, part, _text(_first(slots, getattr(spec, part))))
    o.items = _items(_first(slots, spec.items))
    if layout in CLOSING_LABEL and o.closing:
        o.closing_label = note_label_text(slots, CLOSING_LABEL[layout])
    if spec.shape:
        spec.shape(o, slots)
    o.items = o.items[:ITEM_CAP.get(layout, len(o.items))]
    # L-STAT-HERO prints `label` under its number when there is no `stat_label`; it is then
    # the figure's caption, not the row's eyebrow, and must not show twice.
    if o.big_label and o.big_label == o.label and not slots.get("stat_label"):
        o.label = _text(slots.get("eyebrow") or slots.get("data_label"))
    o.dropped = [name for name in spec.dropped if slots.get(name)]
    return o


def outline_storyboard(text: str) -> tuple[list[Outline], list[str]]:
    """(outlines, warnings) for a storyboard's catalog rows, in order.

    A row whose 版型 is not a catalog code is skipped with the warning `deck-compile`
    gives, so every View covers the same rows. The first row is the cover when it is
    an L-HERO-TITLE; a later L-HERO-TITLE opens a section, except as the last row,
    where it closes the talk like an L-FINALE-SUMMARY.
    """
    outlines: list[Outline] = []
    warnings: list[str] = []
    for idx, row in enumerate(extract_storyboard_rows(text)):
        try:
            o = outline_row(row, idx)
        except ValueError as e:
            warnings.append(f"投影片 #{row.get('#', idx)}: {e}")
            continue
        if o.dropped:
            warnings.append(f"投影片 #{o.num}: {o.layout} 的 {'、'.join(o.dropped)} 是圖，"
                            "這個 View 只帶得走文字；圖留在 deck.html")
        outlines.append(o)
    for i, o in enumerate(outlines):
        if o.layout == "L-FINALE-SUMMARY":
            o.kind = "finale"
        elif o.layout == "L-HERO-TITLE":
            o.kind = "cover" if i == 0 else "finale" if i == len(outlines) - 1 else "section"
    return outlines, warnings


# ---------- speaker notes ----------

NOTES_BLOCK = re.compile(r'<script type="application/json" id="speaker-notes">(.*?)</script>', re.S)


def deck_notes(talk: Path, count: int) -> tuple[list[str], str]:
    """(one note per outlined row, problem) read from the notes `./fw deck-notes` wrote into deck.html.

    A derived View takes the assembled notes instead of expanding the knowledge points
    again, because `deck-notes` is where a broken K/Q number is refused. When the deck is
    missing or does not have one slide per outlined row (it was not compiled from this
    storyboard), the notes cannot be matched to rows: they come back empty, with the reason.
    """
    empty = [""] * count
    deck = talk / "deck.html"
    if not deck.is_file():
        return empty, "deck.html is missing"
    m = NOTES_BLOCK.search(deck.read_text(encoding="utf-8"))
    try:
        notes = json.loads(m.group(1)) if m else None
    except json.JSONDecodeError:
        notes = None
    if not isinstance(notes, list) or len(notes) != count:
        found = len(notes) if isinstance(notes, list) else 0
        return empty, f"deck.html carries {found} speaker notes for {count} storyboard rows"
    return [str(n) for n in notes], ""
