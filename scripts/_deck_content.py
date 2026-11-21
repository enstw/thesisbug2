"""What a storyboard says, kept apart from how the deck shows it.

A talk is planned in two stages. The storyboard stage decides what each slide says,
judged by the audience and the occasion and never by which layouts exist. The design
stage then chooses or adds a layout for each row; it may not change, shorten or drop
what the row says. This module is what makes the second half checkable:

- `lost_content` compares one row's text with the slide compiled from it and reports
  every piece that is not on the slide. Layouts used to drop a fourth card, an unknown
  slot or a tag without a word, so an agent learnt to write less.
- `content_digest` is a fingerprint of everything the storyboard stage owns. The
  author's sign-off records it (`./fw storyboard-sign`), and `deck-compile` refuses a
  storyboard whose content no longer matches, so a design pass cannot quietly edit it.
- `density` and `type_floor` read the two premises the content is sized by.
"""

from __future__ import annotations

import hashlib
import html as html_lib
import re
from html.parser import HTMLParser
from typing import Any, Iterator

try:
    from _deck_catalog import parse_slot_payload
    from _deck_outline import COMMON, SPECS, extract_storyboard_rows
    from _deck_steps import premise_value, section
except ImportError:          # imported as scripts._deck_content (tests)
    from ._deck_catalog import parse_slot_payload
    from ._deck_outline import COMMON, SPECS, extract_storyboard_rows
    from ._deck_steps import premise_value, section

# Slots and columns the design stage owns: they steer the form and carry no content.
DESIGN_SLOTS = {"variant", "html", "matrix_width", "label_width", "points_align", "title_lines", "sub_lines",
                "art", "art_ground"}
DESIGN_COLUMNS = {"版型", "動態"}
# Slots whose value is shown as a label or names a file, so it is not text to find on the slide.
UNCHECKED_SLOTS = DESIGN_SLOTS | {"verdict_label", "label", "data_label", "eyebrow"}
# Keys inside an item that repeat another key (`text`, `point`) or are not words (`pct`).
NON_TEXT_KEYS = {"text", "point", "pct", "position_pct", "focus_quadrant"}
# A layout that accepts any slot, because its body is written by hand for this row.
FREE_FORM = {"L-CUSTOM"}

DENSITIES = ("高", "中", "低")
DEFAULT_DENSITY = "高"
DEFAULT_FLOOR = 34
# The floors the deck can run at: each is the 34px label size at a font scale the +/− keys reach.
FLOORS = {34: 100, 30: 90, 27: 80}

SIGN_KEY = "內容簽核"
ART_KEY = "情境圖"
SIGN_LINE = re.compile(rf"(?m)^[-*]\s*(?:\*\*)?{SIGN_KEY}(?:\*\*)?\s*[:：]\s*(.*)$")
DIGEST = re.compile(r"\b[0-9a-f]{12}\b")


# ---------- what the slide shows ----------

class _Visible(HTMLParser):
    """The text an audience can read: no <style>/<script>, no aria-hidden decoration, no attributes."""

    VOID = {"br", "img", "hr", "input", "meta", "link", "path", "rect", "circle", "line", "ellipse",
            "polygon", "polyline", "use", "stop"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            return
        if self.skip or tag in ("style", "script", "defs") or dict(attrs).get("aria-hidden") == "true":
            self.skip.append(tag)
            return
        self.out.append("\n")

    def handle_endtag(self, tag):
        if self.skip:
            if tag == self.skip[-1]:
                self.skip.pop()
            return
        self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def visible_text(rendered: str) -> str:
    parser = _Visible()
    parser.feed(rendered)
    parser.close()
    return "".join(parser.out)


def _squash(text: str) -> str:
    """Text with every space removed, so a line wrap or an element boundary inside a phrase does not hide it."""
    return re.sub(r"\s+", "", text)


def leaves(value: Any) -> Iterator[str]:
    """Every piece of text in a slot's value, in order."""
    if isinstance(value, str):
        if value.strip():
            yield value.strip()
    elif isinstance(value, dict):
        for key, inner in value.items():
            if key not in NON_TEXT_KEYS:
                yield from leaves(inner)
    elif isinstance(value, list):
        for item in value:
            yield from leaves(item)


def _short(text: str, n: int = 18) -> str:
    return text if len(text) <= n else text[:n] + "…"


def lost_content(layout_id: str, slots: dict[str, Any], rendered: str) -> list[str]:
    """What the row says that its compiled slide does not show, one message per piece.

    Three ways content used to vanish without a word, all reported here: a slot the
    layout does not have, an item past the number the layout has room for, and a field
    the layout does not draw (a tag on a stage, the text after a colon in a closing point).
    """
    spec = SPECS[layout_id]
    known = spec.slots() | set(COMMON)
    shown = _squash(visible_text(rendered))
    free = layout_id in FREE_FORM
    problems: list[str] = []

    def missing(value: Any) -> list[str]:
        return [t for t in leaves(value) if _squash(t) not in shown]

    for key, value in slots.items():
        if key in UNCHECKED_SLOTS or (not free and (key in spec.styling or key in spec.dropped)):
            continue
        if key == "title" and slots.get("title_lines") or key == "sub" and slots.get("sub_lines"):
            continue
        if not free and key not in known:
            # A row's loose first line can still reach the slide as its title; only text that did not is lost.
            gone = missing(value)
            if gone:
                problems.append(f"槽位 {key} 不是 {layout_id} 的槽位，它的內容（「{_short(gone[0])}」）沒有上畫面")
            continue
        if isinstance(value, list):
            whole = [(i, item) for i, item in enumerate(value, 1)
                     if list(leaves(item)) and len(missing(item)) == len(list(leaves(item)))]
            if whole:
                first = next(leaves(whole[0][1]))
                numbers = "、".join(str(i) for i, _ in whole)
                why = "手寫版面的檔案裡沒有這些文字" if free else f"{layout_id} 放不下這麼多項"
                problems.append(f"{key} 的第 {numbers} 項（「{_short(first)}」…）整項沒有上畫面：{why}")
            gone = {i for i, _ in whole}
            for i, item in enumerate(value, 1):
                if i not in gone:
                    why = "手寫版面的檔案裡沒有這段文字" if free else f"{layout_id} 不畫這個欄位"
                    problems += [f"{key} 第 {i} 項的「{_short(t)}」沒有上畫面：{why}" for t in missing(item)]
        else:
            problems += [f"{key} 的「{_short(t)}」沒有上畫面" for t in missing(value)]
    return problems


def missing_required(layout: Any, slots: dict[str, Any]) -> list[str]:
    """Required slots the row leaves out; a slot counts as given when another name its layout reads in the same place is."""
    spec = SPECS[layout.id]
    groups = [g for g in (spec.title, spec.lead, spec.items, spec.closing, spec.cite, spec.big,
                          spec.big_label, spec.quote, spec.meta) if g]
    out = []
    for name in layout.required_slots:
        names = next((g for g in groups if name in g), (name,))
        if not any(slots.get(n) for n in names):
            out.append(name)
    return out


# ---------- the premises content is sized by ----------

def density(storyboard_text: str) -> tuple[str, bool]:
    """(高|中|低, stated): the deck's information density from 前提, 高 when it is not stated."""
    value = premise_value(storyboard_text, "密度") or ""
    for level in DENSITIES:
        if value.startswith(level):
            return level, True
    return DEFAULT_DENSITY, False


def type_floor(storyboard_text: str) -> int:
    """The smallest text size the room allows, from 前提 (`字級下限 30px` anywhere in it), 34 by default."""
    m = re.search(r"字級下限\D{0,12}?(\d{2})\s*px", section(storyboard_text, "前提"))
    return int(m.group(1)) if m else DEFAULT_FLOOR


# ---------- the sign-off ----------

def content_digest(storyboard_text: str) -> str:
    """A fingerprint of what the storyboard stage owns.

    It covers every premise bullet except the seed, the sign-off itself and the pictures'
    source (the design stage's to write), and every
    row's cells except the design columns; inside 畫面內容 it reads the text, not the slot
    names, so the design stage may move a row's content into another layout's slots but
    may not reword it.
    """
    h = hashlib.sha256()
    for line in section(storyboard_text, "前提").splitlines():
        if re.match(r"[-*]\s", line) and not re.match(rf"[-*]\s*(?:\*\*)?(?:Seed|{SIGN_KEY}|{ART_KEY})\b", line):
            h.update(_squash(line).encode("utf-8") + b"\x1e")
    for row in extract_storyboard_rows(storyboard_text):
        for column, cell in row.items():
            if column in DESIGN_COLUMNS:
                continue
            if column == "畫面內容":
                slots = parse_slot_payload(cell)
                cell = "\x1f".join(t for key, value in slots.items() if key not in DESIGN_SLOTS for t in leaves(value))
            h.update(column.encode("utf-8") + b"\x1f" + _squash(cell).encode("utf-8") + b"\x1e")
        h.update(b"\x1d")
    return h.hexdigest()[:12]


def art_credit(storyboard_text: str) -> str:
    """The 前提 bullet that says where the deck's pictures come from ("情境圖：…"), "" when there is none."""
    m = re.search(rf"(?m)^[-*]\s*(?:\*\*)?({ART_KEY})(?:\*\*)?\s*[:：]\s*(.+)$", section(storyboard_text, "前提"))
    return f"{m.group(1)}：{m.group(2).strip()}" if m else ""


def signed_digest(storyboard_text: str) -> str | None:
    """The digest the sign-off bullet records, None when the storyboard has no sign-off."""
    m = SIGN_LINE.search(section(storyboard_text, "前提"))
    if not m:
        return None
    found = DIGEST.search(m.group(1))
    return found.group(0) if found else ""


def sign_problem(storyboard_text: str) -> str:
    """"" when the content matches its sign-off or was never signed; otherwise what to do."""
    signed = signed_digest(storyboard_text)
    if signed is None or signed == content_digest(storyboard_text):
        return ""
    return ("分鏡稿的內容（前提、來源論點、內容形狀、畫面內容的文字、講者備註）在簽核之後改過。"
            "設計階段只能改「版型」「動態」與版面槽位（variant 等）；內容要改就回分鏡階段，"
            "由作者同意後執行 ./fw storyboard-sign 重新簽核")


def char_count(cell: str) -> int:
    """How many characters a row puts on its slide: every piece of text in 畫面內容, spaces left out."""
    slots = parse_slot_payload(cell)
    return sum(len(_squash(html_lib.unescape(t))) for key, value in slots.items()
               if key not in DESIGN_SLOTS for t in leaves(value))
