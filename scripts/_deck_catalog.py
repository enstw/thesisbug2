"""The presentation layout catalog and slot parser for thesisbug2.

Defines the 20 standard layout codes across 5 families, their slot schemas,
seeded depth variants, and deterministic HTML renderers.

A depth variant changes the form of a slide's containers (panel, open column, bubble,
pill, disc, chevron), never only its colour: colour already varies per slide through the
chapter accent and per deck through the theme keys. Every name in a layout's
`allowed_variants` must render differently; a test compiles each catalog example in every
variant and compares.

Layout catalog v1.1:
  1. Declarative & Thesis:
     - L-HERO-TITLE
     - L-FINALE-SUMMARY
  2. Parallel Expansion & Synthesis:
     - L-3CARD-VERDICT
     - L-4CARD-GRID
     - L-6CARD-GRID
     - L-BENTO-FOCUS
     - L-BANNER-6GRID
     - L-SPLIT-ANCHOR
  3. Relational, Contrast & Typology:
     - L-VS-CONFRONT
     - L-MATRIX-DEEPDIVE
     - L-SPECTRUM-POLES
  4. Temporal & Causal Progression:
     - L-FLOW-3STAGE
     - L-TIMELINE-RAIL
     - L-CASCADE-FUNNEL
     - L-CANVAS (standard frame around one free drawing area)
     - L-CUSTOM (standard frame around a body written by hand, kept in the talk)
  5. Scholarly Critique & Evidence:
     - L-QUOTE-CRITIQUE
     - L-HYPOTHESIS-TEST
     - L-STAT-HERO
     - L-DEFN-EXAMPLE
"""

from __future__ import annotations

import html
import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    from _deck_flow import flow_svg, parse_lane
except ImportError:          # imported as scripts._deck_catalog (tests)
    from ._deck_flow import flow_svg, parse_lane


@dataclass
class SlideContext:
    slide_num: int
    total_slides: int
    accent: str
    eyebrow: str
    data_label: str
    variant: str
    base: Path | None = None    # the talk directory, for slots that name a file (L-CANVAS `svg:`)
    pmap: str = ""              # the pipeline step strip for this row (_deck_steps), "" = none


@dataclass
class LayoutDefinition:
    id: str
    family: str
    name: str
    required_slots: list[str]
    allowed_variants: list[str]
    render_func: Callable[[dict[str, Any], str, SlideContext], str]
    optional_slots: list[str] = field(default_factory=list)


def esc(s: Any) -> str:
    """Escape text for safe HTML embedding, leaving markup tags alone if raw."""
    if s is None:
        return ""
    text = str(s).strip()
    return html.escape(text, quote=True)


def parse_inline_dict(s: str) -> dict[str, Any]:
    """Parse a simple inline dict like {camp: '...', points: ['a', 'b']}."""
    s = s.strip()
    if s.startswith("{") and s.endswith("}"):
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
        # Lenient key-value parser: key: "value" or key: 'value'
        inner = s[1:-1].strip()
        result: dict[str, Any] = {}
        # Try simple regex matching key: value
        matches = re.findall(r'(\w+)\s*[:=]\s*("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\[.*?\]|[^,]+)', inner)
        for k, v in matches:
            v = v.strip()
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                result[k] = v[1:-1]
            elif v.startswith("[") and v.endswith("]"):
                # Split on commas outside quotes: a quoted item may hold one
                # ("約 1,234 件"), and splitting it there breaks the item in two.
                items = []
                for dq, sq, bare in re.findall(r'\s*(?:"((?:\\.|[^"\\])*)"|\'((?:\\.|[^\'\\])*)\'|([^,]+))\s*(?:,|$)', v[1:-1]):
                    item = (dq or sq or bare).strip()
                    if item:
                        items.append(item)
                result[k] = items
            else:
                result[k] = v
        if result:
            return result
    return {"raw": s}


# A record key is a slot name, lower-case like every slot in the catalog, so a tag such as
# `[H1: 假說]` stays a tag.
_RECORD_KEY = r"[a-z_][a-z0-9_]*"
_RECORD_NEXT = re.compile(rf",\s*(?={_RECORD_KEY}\s*[:：])")
_RECORD_PAIR = re.compile(rf"({_RECORD_KEY})\s*[:：]\s*(.+)$")


def parse_bullet_record(inner: str) -> dict[str, str]:
    """`label: 早期矽谷, pct: 20, desc: …` (a bullet that is only a bracket) as a record.

    Splits at a comma only where the next key starts, so a value keeps its own commas.
    Returns {} when any part is not `key: value`, which leaves the bracket a tag.
    """
    record: dict[str, str] = {}
    for part in _RECORD_NEXT.split(inner):
        m = _RECORD_PAIR.match(part.strip())
        if not m:
            return {}
        record[m.group(1)] = m.group(2).strip().strip("\"'")
    return record


def parse_slot_payload(raw_text: str) -> dict[str, Any]:
    """Parse the structured micro-syntax in storyboard '畫面內容' into slot dict.

    Supports:
      key: value
      cards:
      - [tag] head: body
      - head | body
      - [tag] point
      - [key: value, key: value]
    """
    text = raw_text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    slots: dict[str, Any] = {}
    current_list_key: str | None = None

    re_bullet = re.compile(r"^[*-]\s*(?:\[(.*?)\]\s*)?(.*?)(?:[:：|｜]\s*(.*))?$")
    re_key_val = re.compile(r"^([a-zA-Z0-9_]+)\s*[:：]\s*(.*)$")

    for line in lines:
        if line.startswith(("-", "*")):
            # It's a bullet item
            m = re_bullet.match(line)
            tag = (m.group(1) or "").strip() if m else ""
            part1 = (m.group(2) or "").strip() if m else line[1:].strip()
            part2 = (m.group(3) or "").strip() if m else ""

            # `text` keeps the bullet whole, separators included, for slots that
            # take literal lines (`title_lines`, `sub_lines`): a title line such
            # as 「霸權之後：」 would otherwise lose its colon to the head/body split.
            item: dict[str, Any] = {"text": line[1:].strip()}
            record = parse_bullet_record(tag) if tag and not part1 and not part2 else {}
            if record:
                # The spectrum's markers are written this way; read as a tag, the whole
                # record became one label and every marker lost its position.
                item.update({"head": "", "body": "", **record})
            else:
                if tag:
                    item["tag"] = tag
                item["head"] = part1
                item["body"] = part2
                if not part2:
                    item["point"] = part1

            target_key = current_list_key or "items"
            if target_key not in slots or not isinstance(slots[target_key], list):
                slots[target_key] = []
            slots[target_key].append(item)
            continue

        km = re_key_val.match(line)
        if km:
            key = km.group(1).lower().strip()
            val = km.group(2).strip()
            if not val:
                current_list_key = key
                if key not in slots:
                    slots[key] = []
            else:
                current_list_key = None
                if val.startswith("{") and val.endswith("}"):
                    slots[key] = parse_inline_dict(val)
                else:
                    slots[key] = val
        else:
            if current_list_key:
                if not isinstance(slots.get(current_list_key), list):
                    slots[current_list_key] = []
                slots[current_list_key].append({"head": line, "body": "", "point": line})
            else:
                if "body" in slots:
                    slots["body"] += " " + line
                else:
                    slots["body"] = line

    return slots


class VisualRhythmResolver:
    """Deterministic PRNG with rhythm constraints (accents, variants)."""

    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.prev_accent: str | None = None
        # layout id → its variants in this deck's order, and how many slides have used it
        self.orders: dict[str, list[str]] = {}
        self.used: dict[str, int] = {}

    def resolve(
        self,
        layout: LayoutDefinition,
        slide_num: int,
        total_slides: int,
        eyebrow: str,
        title: str,
        pinned: str = "",
    ) -> tuple[SlideContext, str]:
        # 1. Accent cycling: choose from --c1..--c4, never repeat previous
        accents = [f"var(--c{i})" for i in range(1, 5) if f"var(--c{i})" != self.prev_accent]
        chosen_accent = self.rng.choice(accents)
        self.prev_accent = chosen_accent

        # 2. Variant: each layout walks its variants in an order the seed shuffles, so a
        # layout used three times shows three forms before any repeats. Independent draws
        # gave the same form twice in a row about as often as not. A pinned slide still
        # takes its turn, so pinning one slide leaves every other slide as it was.
        variants = layout.allowed_variants or ["default"]
        if layout.id not in self.orders:
            self.orders[layout.id] = self.rng.sample(variants, len(variants))
            self.used[layout.id] = 0
        chosen_variant = self.orders[layout.id][self.used[layout.id] % len(variants)]
        self.used[layout.id] += 1
        if pinned in variants:
            chosen_variant = pinned

        ctx = SlideContext(
            slide_num=slide_num,
            total_slides=total_slides,
            accent=chosen_accent,
            eyebrow=eyebrow,
            data_label=title,
            variant=chosen_variant,
        )
        return ctx, chosen_variant


# =========================================================================
# Renderers for the standard layouts
# =========================================================================

def _render_topbar(ctx: SlideContext) -> str:
    return f"""      <div class="railtop"></div>
      <div class="topbar">
        <span class="eyebrow">{esc(ctx.eyebrow)}</span>{ctx.pmap}
        <span class="chap"><b>{ctx.slide_num}</b> / {ctx.total_slides}</span>
      </div>"""


def _dlabel(slots: dict[str, Any], default: str) -> str:
    return esc(slots.get("label") or slots.get("data_label") or default)


NO_LABEL = {"none", "無", "-", "—"}

# The default word in front of each layout's closing box, and the fixed words a
# layout prints when a slot leaves them out. They are data, not literals inside
# the renderers, because the derived Views read the same rows through
# `_deck_outline` and a second copy of a word would drift from the slide.
CLOSING_LABEL = {
    "L-3CARD-VERDICT": "結論",
    "L-4CARD-GRID": "定論",
    "L-6CARD-GRID": "定論",
    "L-BENTO-FOCUS": "定論",
    "L-VS-CONFRONT": "裁決／提問",
    "L-SPECTRUM-POLES": "定論",
    "L-FLOW-3STAGE": "最終均衡",
    "L-TIMELINE-RAIL": "歷史啟示",
    "L-CASCADE-FUNNEL": "核心焦點",
    "L-HYPOTHESIS-TEST": "理論謎題／意涵",
    "L-CANVAS": "重點",
    "L-CUSTOM": "重點",
}
# How many list items each layout has room for; a row that lists more shows the
# first ones. Here for the same reason as the words above: a derived View that
# kept the fourth card of a three-card row would show what the deck does not.
ITEM_CAP = {
    "L-3CARD-VERDICT": 3,
    "L-4CARD-GRID": 4,
    "L-BENTO-FOCUS": 3,          # the focus card plus two side cards
    "L-BANNER-6GRID": 6,         # cards under the banner
    "L-6CARD-GRID": 6,
    "L-SPLIT-ANCHOR": 3,
    "L-FLOW-3STAGE": 3,
    "L-TIMELINE-RAIL": 5,
    "L-CASCADE-FUNNEL": 3,
    "L-QUOTE-CRITIQUE": 3,
    "L-STAT-HERO": 2,
}
DEFAULT_WORDS = {
    "hypothesis": "理論預期 (H1)",
    "finding": "實證發現",
    "finding_status": "實證落差",
    "positive": "典型例證",
    "negative": "邊界／反例",
    "matrix_focus": "焦點象限特寫 (Q{n})",
    "matrix_note": "解讀",
}


def note_label_text(slots: dict[str, Any], default: str) -> str:
    """The word in front of a layout's closing box (verdict, takeaway, puzzle...), "" for none.

    Each layout keeps a default word for what that box usually holds, but the
    same box can carry a mechanism, a case observation or a discussion
    procedure, and a fixed word like 定論 then mislabels the content. So a
    slide may set `verdict_label: <word>` to rename the prefix, or
    `verdict_label: none` to drop it.
    """
    raw = slots.get("verdict_label")
    if raw is None:
        return default
    if isinstance(raw, list):          # `verdict_label:` with no value
        return ""
    text = str(raw).strip()
    if not text or text.lower() in NO_LABEL:
        return ""
    return text


def matrix_focus(slots: dict[str, Any]) -> int:
    """The highlighted quadrant of L-MATRIX-DEEPDIVE (1–4), 0 for none.

    `focus_quadrant: none` (or 0) highlights no cell: a typology offered as a
    question should not visually pre-assign a case to a quadrant.
    """
    fq = str(slots.get("focus_quadrant") if slots.get("focus_quadrant") is not None else 1).strip().lower()
    return int(fq) if fq.isdigit() and 1 <= int(fq) <= 4 else 0


def matrix_note_label(slots: dict[str, Any], focus: int) -> str:
    return str(slots.get("note_label")
               or (DEFAULT_WORDS["matrix_focus"].format(n=focus) if focus else DEFAULT_WORDS["matrix_note"]))


def _note_label(slots: dict[str, Any], default: str) -> str:
    """`note_label_text` as the bold prefix the slide prints."""
    text = note_label_text(slots, default)
    return f"<em>{esc(text)}：</em>" if text else ""


def _slot_lines(raw: Any) -> list[str]:
    """Text of each item in a `*_lines:` list slot, or [] when it is not a list."""
    if not isinstance(raw, list):
        return []
    return [str((ln.get("text") or ln.get("head", "")) if isinstance(ln, dict) else ln).strip() for ln in raw]


def _est_em(text: str) -> float:
    """Rough rendered width in em: a CJK or full-width character is about 1em,
    Latin letters, digits and ASCII punctuation about half that."""
    return sum(1.0 if ord(c) > 0x2E7F else 0.55 for c in text)


def render_hero_title(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    title = esc(slots.get("title") or "未命名簡報")
    dlabel = _dlabel(slots, title)
    # `title_lines:` (a list) sets where the cover title breaks. Balanced
    # wrapping evens out line widths but cannot see meaning, so a title whose
    # natural break is after a comma may still split mid-phrase.
    # Each listed line is kept whole; if the longest would overflow the 1500px
    # title box at the 132px default (letter-spacing .04em), the font shrinks
    # just enough to fit, rather than letting the line wrap mid-phrase again.
    texts = [t for t in _slot_lines(slots.get("title_lines")) if t]
    title_html, h1_style = title, ""
    if texts:
        # No per-line <span>: the title's colour is a gradient clipped to the
        # h1's text, and a child element would hide that from deck-check.
        title_html = "<br>".join(esc(t) for t in texts)
        widest = max(len(t) for t in texts) or 1
        fit = int(1500 * 0.97 / (widest * 1.04))
        size = f" font-size: calc({fit}px * var(--deck-font-scale, 1));" if fit < 132 else ""
        h1_style = f' style="white-space: nowrap;{size}"'
    sub = esc(slots.get("sub") or slots.get("subtitle") or "")
    # `sub_lines:` does for the subtitle what `title_lines` does for the title:
    # a subtitle that joins a question to a source line otherwise wraps inside
    # an author-year citation. Lines stay whole; the 48px default shrinks to
    # fit the 1500px box, never below the deck's 34px text floor.
    sub_texts = [t for t in _slot_lines(slots.get("sub_lines")) if t]
    sub_style = ""
    if sub_texts:
        sub = "<br>".join(esc(t) for t in sub_texts)
        fit = int(1500 * 0.97 / (max(_est_em(t) for t in sub_texts) or 1))
        size = f" font-size: calc({max(fit, 34)}px * var(--deck-font-scale, 1));" if fit < 48 else ""
        sub_style = f' style="white-space: nowrap;{size}"'
    meta = esc(slots.get("meta") or slots.get("author") or "")
    sub_html = f'<p class="hero__sub rise d1"{sub_style}>{sub}</p>' if sub else ""
    meta_html = f'<p class="hero__meta rise d2">{meta}</p>' if meta else ""

    return f"""  <section class="slide hero" data-label="{dlabel}">
    <div class="railtop"></div>
    <div class="hero__layers" aria-hidden="true">
      <div class="grid-layer"></div>
    </div>
    <div class="hero__inner">
      <h1 class="rise"{h1_style}>{title_html}</h1>
      {sub_html}
      {meta_html}
    </div>
    <div class="hero__hint">切換 <kbd>→</kbd> <kbd>←</kbd></div>
  </section>"""


def render_finale_summary(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    heading = esc(slots.get("heading") or slots.get("title") or "結語與討論")
    dlabel = _dlabel(slots, heading)
    onesentence = esc(slots.get("onesentence") or slots.get("verdict") or slots.get("body") or "")
    pts = slots.get("points") or slots.get("items") or []

    pts_html = ""
    if pts:
        # the whole bullet: a point such as 「韌性：效率的代價」 lost everything after its colon when only the head was printed
        li_items = "".join(f"<li>{esc((p.get('text') or p.get('head', '')) if isinstance(p, dict) else p)}</li>" for p in pts)
        # Long points wrap; centred wrapped lines are hard to follow, so a slide
        # may set `points_align: left` while the heading stays centred.
        align = ' style="text-align:left"' if str(slots.get("points_align") or "").strip().lower() == "left" else ""
        pts_html = f'<ul class="clean lead-size rise d2 mt"{align}>{li_items}</ul>'

    qr_html = _qr_figure(slots, ctx, size=240, style="margin:32px auto 0", rise="rise d3")

    return f"""  <section class="slide finale" data-label="{dlabel}">
    <div class="railtop"></div>
    <div class="content">
      <h2 class="rise">{heading}</h2>
      <p class="onesentence rise d1">{onesentence}</p>
      {pts_html}
      {qr_html}
    </div>
  </section>"""


def render_3card_verdict(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    lead = esc(slots.get("lead") or "")
    cards = slots.get("cards") or slots.get("items") or []
    verdict = esc(slots.get("verdict") or "")

    lead_html = f'<p class="lead rise">{lead}</p>' if lead else ""
    card_class = f"card card--{variant}"

    cards_html = []
    for i, c in enumerate(cards[:ITEM_CAP["L-3CARD-VERDICT"]]):
        tag = esc(c.get("tag") or "")
        head = esc(c.get("head") or "")
        body = esc(c.get("body") or "")
        tag_html = f'<span class="tag">{tag}</span>' if tag else ""
        delay = f"d{i+1}"
        cards_html.append(f"""          <div class="{card_class} rise {delay}">
            {tag_html}
            <h3>{head}</h3>
            <p>{body}</p>
          </div>""")

    note_label = _note_label(slots, CLOSING_LABEL["L-3CARD-VERDICT"])
    verdict_html = f'<div class="verdict box rise d4">{note_label}{verdict}</div>' if verdict else ""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      {lead_html}
      <div class="grid three mt">
{''.join(cards_html)}
      </div>
      {verdict_html}
    </div>
  </section>"""


def render_4card_grid(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    lead = esc(slots.get("lead") or "")
    cards = slots.get("cards") or slots.get("items") or []
    verdict = esc(slots.get("verdict") or "")

    lead_html = f'<p class="lead rise">{lead}</p>' if lead else ""

    cards_html = []
    for i, c in enumerate(cards[:ITEM_CAP["L-4CARD-GRID"]]):
        tag = esc(c.get("tag") or "")
        head = esc(c.get("head") or "")
        body = esc(c.get("body") or "")
        tag_html = f'<span class="tag">{tag}</span>' if tag else ""
        delay = f"d{i+1}"
        if variant == "numbered-1-4":
            # The ordinal is the renderer's, not the author's text, so it stays out of what is read as slide text.
            cards_html.append(f"""        <div class="numrow rise {delay}">
          <div class="disc" aria-hidden="true">{i+1}</div>
          <div>
            {tag_html}
            <h3>{head}</h3>
            <p>{body}</p>
          </div>
        </div>""")
        elif variant == "pillars":
            cap = f'<div class="pillar__cap">{tag}</div>' if tag else f'<div class="pillar__cap" aria-hidden="true">0{i+1}</div>'
            cards_html.append(f"""        <div class="pillar rise {delay}">
          {cap}
          <div class="pillar__body">
            <h3>{head}</h3>
            <p>{body}</p>
          </div>
        </div>""")
        else:
            cards_html.append(f"""        <div class="card card--grid-2x2 rise {delay}">
          {tag_html}
          <h3>{head}</h3>
          <p>{body}</p>
        </div>""")

    note_label = _note_label(slots, CLOSING_LABEL["L-4CARD-GRID"])
    verdict_html = f'<div class="verdict box rise d4">{note_label}{verdict}</div>' if verdict else ""
    grid = "grid four" if variant == "pillars" else "grid two"

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      {lead_html}
      <div class="{grid} mt">
{''.join(cards_html)}
      </div>
      {verdict_html}
    </div>
  </section>"""


def render_bento_focus(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    lead = esc(slots.get("lead") or "")
    hero = slots.get("hero_card") or (slots.get("cards") or [{}])[0]
    subs = slots.get("sub_cards") or (slots.get("cards") or [{}, {}, {}])[1:ITEM_CAP["L-BENTO-FOCUS"]]
    verdict = esc(slots.get("verdict") or "")

    lead_html = f'<p class="lead rise">{lead}</p>' if lead else ""
    hero_tag = esc(hero.get("tag") or "核心焦點")
    hero_head = esc(hero.get("head") or "")
    hero_body = esc(hero.get("body") or "")

    sub_cards_html = []
    for i, s in enumerate(subs[:ITEM_CAP["L-BENTO-FOCUS"] - 1]):
        stag = esc(s.get("tag") or "")
        shead = esc(s.get("head") or "")
        sbody = esc(s.get("body") or "")
        tag_span = f'<span class="tag">{stag}</span>' if stag else ""
        sub_cards_html.append(f"""          <div class="card rise d{i+2}">
            {tag_span}
            <h3>{shead}</h3>
            <p>{sbody}</p>
          </div>""")

    note_label = _note_label(slots, CLOSING_LABEL["L-BENTO-FOCUS"])
    verdict_html = f'<div class="verdict box rise d4">{note_label}{verdict}</div>' if verdict else ""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      {lead_html}
      <div class="bento bento--{variant} mt">
        <div class="card card--tint-elevated bento__hero rise d1">
          <span class="tag">{hero_tag}</span>
          <h3>{hero_head}</h3>
          <p class="lead-size">{hero_body}</p>
        </div>
{''.join(sub_cards_html)}
      </div>
      {verdict_html}
    </div>
  </section>"""


def render_split_anchor(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    anchor = esc(slots.get("anchor_statement") or slots.get("anchor") or "")
    items = slots.get("items") or slots.get("cards") or []
    cite = esc(slots.get("footer_cite") or slots.get("cite") or "")
    quote_style = variant == "quote-style"

    item_class = "openitem" if quote_style else "card"
    items_html = []
    for i, item in enumerate(items[:ITEM_CAP["L-SPLIT-ANCHOR"]]):
        head = esc(item.get("head") or "")
        body = esc(item.get("body") or "")
        tag = esc(item.get("tag") or "")
        tag_span = f'<span class="tag">{tag}</span>' if tag else ""
        items_html.append(f"""          <div class="{item_class} rise d{i+2}">
            {tag_span}
            <h3>{head}</h3>
            <p>{body}</p>
          </div>""")

    cite_html = f'<div class="muted mt">出處：{cite}</div>' if cite else ""
    qr_html = _qr_figure(slots, ctx, size=220, style="margin:24px 0 0")
    if quote_style:
        statement = f"""<div class="bigquote" aria-hidden="true">“</div>
          <p class="anchorline">{anchor}</p>"""
    else:
        statement = f"""<blockquote class="pull">
            {anchor}
          </blockquote>"""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      <div class="split-anchor split-anchor--{variant} mt">
        <div class="split-anchor__hero rise d1">
          {statement}
          {cite_html}
          {qr_html}
        </div>
        <div class="split-anchor__list">
{''.join(items_html)}
        </div>
      </div>
    </div>
  </section>"""


def render_vs_confront(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    issue = esc(slots.get("issue") or slots.get("claim") or "")
    side_a = slots.get("side_a") or {}
    side_b = slots.get("side_b") or {}
    verdict = esc(slots.get("ask_or_verdict") or slots.get("ask") or slots.get("verdict") or "")

    camp_a = esc(side_a.get("camp") or side_a.get("camp_name") or "陣營 A")
    pts_a = side_a.get("points") or []
    pts_a_html = "".join(f"<li>{esc(p)}</li>" for p in pts_a)

    camp_b = esc(side_b.get("camp") or side_b.get("camp_name") or "陣營 B")
    pts_b = side_b.get("points") or []
    pts_b_html = "".join(f"<li>{esc(p)}</li>" for p in pts_b)

    issue_html = f'<p class="lead rise" style="color:var(--text);font-weight:700">{issue}</p>' if issue else ""
    note_label = _note_label(slots, CLOSING_LABEL["L-VS-CONFRONT"])
    verdict_html = f'<div class="verdict box rise d3">{note_label}{verdict}</div>' if verdict else ""

    # (side A's box, side B's box, A's camp name, B's camp name, the VS column) per variant
    if variant == "split-rail":
        box_a = box_b = "confront__side confront__side--open"
        name_a, name_b = f'<span class="pill">{camp_a}</span>', f'<span class="pill pill--line">{camp_b}</span>'
        vs = "confront__vs confront__vs--rail"
    elif variant == "speech-bubbles":
        box_a = "confront__side bubble bubble--tail-right"
        box_b = "confront__side bubble bubble--plain bubble--tail-left"
        name_a, name_b = f'<span class="pill">{camp_a}</span>', f'<span class="pill pill--line">{camp_b}</span>'
        vs = "confront__vs"
    else:
        box_a = box_b = "card confront__side"
        name_a = f'<span class="tag">{camp_a}</span>'
        name_b = f'<span class="tag" style="color:var(--text)">{camp_b}</span>'
        vs = "confront__vs"

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      {issue_html}
      <div class="confront confront--{variant} mt">
        <div class="{box_a} rise d1">
          {name_a}
          <ul class="clean lead-size mt">
            {pts_a_html}
          </ul>
        </div>
        <div class="{vs} rise d2">
          <div class="confront__badge" aria-hidden="true">VS</div>
        </div>
        <div class="{box_b} rise d1">
          {name_b}
          <ul class="clean lead-size mt">
            {pts_b_html}
          </ul>
        </div>
      </div>
      {verdict_html}
    </div>
  </section>"""


def render_matrix_deepdive(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    axis_x = slots.get("axis_x") or {"name": "X 軸", "low": "低", "high": "高"}
    axis_y = slots.get("axis_y") or {"name": "Y 軸", "low": "低", "high": "高"}
    cells = slots.get("cells") or []
    focus = matrix_focus(slots)
    note = esc(slots.get("deepdive_note") or "")
    note_tag = esc(matrix_note_label(slots, focus))
    callout = variant == "floating-callout"
    # `matrix_width: wide` gives the matrix most of the row: cell text wraps
    # every few characters at the default split, burying the typology. The
    # callout variant already gives the matrix the full width.
    wide = (" matrix-deepdive--wide"
            if not callout and str(slots.get("matrix_width") or "").strip().lower() == "wide" else "")

    # Format 2x2 cells
    tds = {}
    for i in range(1, 5):
        c = cells[i-1] if i <= len(cells) else {}
        clabel = esc(c.get("label") or c.get("head") or f"象限 {i}")
        cdesc = esc(c.get("desc") or c.get("body") or "")
        hi = " hi" if i == focus else ""
        tds[i] = f'<td class="{hi}"><b>{clabel}</b><span>{cdesc}</span></td>'

    matrix_table = f"""        <div class="matrix">
          <div class="axis-y">{esc(axis_y.get('name'))}</div>
          <table>
            <thead>
              <tr><th></th><th>{esc(axis_x.get('low'))}</th><th>{esc(axis_x.get('high'))}</th></tr>
            </thead>
            <tbody>
              <tr><th>{esc(axis_y.get('high'))}</th>{tds[2]}{tds[4]}</tr>
              <tr><th>{esc(axis_y.get('low'))}</th>{tds[1]}{tds[3]}</tr>
            </tbody>
          </table>
          <div class="axis-x">{esc(axis_x.get('name'))}</div>
        </div>"""

    if callout:
        note_html = f"""<div class="bubble bubble--tail-up matrix-deepdive__note rise d2">
          <span class="pill">{note_tag}</span>
          <p>{note}</p>
        </div>"""
    else:
        note_html = f"""<div class="card card--tint-elevated matrix-deepdive__note rise d2">
          <span class="tag">{note_tag}</span>
          <p class="lead-size mt">{note}</p>
        </div>"""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      <div class="matrix-deepdive matrix-deepdive--{variant}{wide} mt">
        {matrix_table}
        {note_html}
      </div>
    </div>
  </section>"""


def render_spectrum_poles(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    pole_l = esc(slots.get("pole_left") or "極端 A")
    pole_r = esc(slots.get("pole_right") or "極端 B")
    markers = slots.get("markers") or slots.get("items") or []
    verdict = esc(slots.get("verdict") or "")
    pills = variant == "step-pills"

    marks_html = []
    for m in markers:
        pct = m.get("position_pct") or m.get("pct") or 50
        lbl = esc(m.get("label") or m.get("head") or "")
        desc = esc(m.get("desc") or m.get("body") or "")
        inner = f"<b>{lbl}</b>\n          <span>{desc}</span>"
        if pills:
            inner = f'<div class="bubble bubble--tail-down">{inner}</div>'
        marks_html.append(f"""        <div class="mark" style="left:{pct}%">
          {inner}
        </div>""")

    note_label = _note_label(slots, CLOSING_LABEL["L-SPECTRUM-POLES"])
    verdict_html = f'<div class="verdict box rise d3 mt">{note_label}{verdict}</div>' if verdict else ""
    pole_class = ' class="pill pill--line"' if pills else ""
    bar_class = "bar bar--steps" if pills else "bar"

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      <div class="spectrum spectrum--{variant} mt">
        <div class="marks rise d1">
{''.join(marks_html)}
        </div>
        <div class="{bar_class}"></div>
        <div class="ends">
          <span{pole_class}>{pole_l}</span>
          <span{pole_class}>{pole_r}</span>
        </div>
      </div>
      {verdict_html}
    </div>
  </section>"""


def render_flow_3stage(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    lead = esc(slots.get("lead") or "")
    stages = slots.get("stages") or slots.get("items") or []
    verdict = esc(slots.get("verdict") or "")

    lead_html = f'<p class="lead rise">{lead}</p>' if lead else ""

    flow_nodes = []
    for i, s in enumerate(stages[:ITEM_CAP["L-FLOW-3STAGE"]]):
        head = esc(s.get("head") or f"階段 {i+1}")
        body = esc(s.get("body") or "")
        if variant == "chevron-step":
            flow_nodes.append(f"""        <div class="chev rise d{i+1}">
          <div class="chev__head"><h3>{head}</h3></div>
          <p>{body}</p>
        </div>""")
        elif variant == "disc-rail":
            flow_nodes.append(f"""        <div class="discstep rise d{i+1}">
          <div class="disc" aria-hidden="true">{i+1}</div>
          <h3>{head}</h3>
          <p>{body}</p>
        </div>""")
        else:
            flow_nodes.append(f"""        <div class="flownode rise d{i+1}">
          <h3>{head}</h3>
          <p>{body}</p>
        </div>""")
            if i < 2 and i < len(stages) - 1:
                flow_nodes.append('        <div class="flowarrow">→</div>')

    note_label = _note_label(slots, CLOSING_LABEL["L-FLOW-3STAGE"])
    verdict_html = f'<div class="verdict box rise d4 mt">{note_label}{verdict}</div>' if verdict else ""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      {lead_html}
      <div class="flowdiag flowdiag--{variant} mt">
{''.join(flow_nodes)}
      </div>
      {verdict_html}
    </div>
  </section>"""


def render_timeline_rail(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    events = (slots.get("events") or slots.get("items") or [])[:ITEM_CAP["L-TIMELINE-RAIL"]]
    takeaway = esc(slots.get("takeaway") or slots.get("verdict") or "")
    alternating = variant == "alternating"

    tls = []
    for i, ev in enumerate(events):
        time_str = esc(ev.get("time") or ev.get("tag") or "")
        head = esc(ev.get("head") or "")
        body = esc(ev.get("body") or "")
        inner = f"""<time>{time_str}</time>
          <b>{head}</b>
          <p>{body}</p>"""
        if alternating:
            # Each event spans two of the n+1 columns and alternates sides of the rail, so
            # a bubble is twice as wide as a column and its neighbours are on the other side.
            side, tail = ("up", "down") if i % 2 == 0 else ("down", "up")
            tls.append(f"""        <div class="tl tl--{side} rise d{min(i+1, 4)}" style="grid-column:{i+1} / span 2">
          <div class="bubble bubble--tail-{tail}">
          {inner}
          </div>
        </div>""")
        else:
            tls.append(f"""        <div class="tl rise d{i+1}">
          {inner}
        </div>""")

    note_label = _note_label(slots, CLOSING_LABEL["L-TIMELINE-RAIL"])
    takeaway_html = f'<div class="verdict box rise d4 mt">{note_label}{takeaway}</div>' if takeaway else ""
    columns = f' style="grid-template-columns:repeat({len(events) + 1}, 1fr)"' if alternating else ""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      <div class="timeline timeline--{variant} mt"{columns}>
{''.join(tls)}
      </div>
      {takeaway_html}
    </div>
  </section>"""


def render_cascade_funnel(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    levels = (slots.get("levels") or slots.get("items") or [])[:ITEM_CAP["L-CASCADE-FUNNEL"]]
    verdict = esc(slots.get("core_focus") or slots.get("verdict") or "")

    # `label_width: narrow` shrinks the level-name column for short names
    # such as 條約／組織／協議, so the description gets the width.
    is_narrow = str(slots.get("label_width") or "").strip().lower() == "narrow"

    def parts(i: int, lv: dict[str, Any]) -> tuple[str, str, str]:
        return (esc(lv.get("level_name") or lv.get("tag") or f"層級 {i+1}"),
                esc(lv.get("head") or ""), esc(lv.get("body") or ""))

    if variant == "concentric-cards":
        # Each level is a box inside the level above it, so the last level sits at the core.
        body_html = ""
        for i in reversed(range(len(levels))):
            name, head, body = parts(i, levels[i])
            body_html = f"""<div class="nest__box rise d{i+1}">
          <div class="nest__row">
            <div class="nest__name">{name}</div>
            <div>
              <h3>{head}</h3>
              <p>{body}</p>
            </div>
          </div>
          {body_html}
        </div>"""
        block = f"""<div class="nest{' nest--narrow' if is_narrow else ''} mt">
        {body_html}
      </div>"""
    else:
        tiers = []
        for i, lv in enumerate(levels):
            name, head, body = parts(i, lv)
            tiers.append(f"""        <div class="tier rise d{i+1}">
          <div style="font-weight:700;color:var(--chapter);font-size:36px">{name}</div>
          <div>
            <h3 style="font-size:42px;margin:0 0 6px">{head}</h3>
            <p style="margin:0;font-size:36px;color:var(--body)">{body}</p>
          </div>
        </div>""")
        block = f"""<div class="tiers{' tiers--narrow' if is_narrow else ''} mt">
{''.join(tiers)}
      </div>"""

    note_label = _note_label(slots, CLOSING_LABEL["L-CASCADE-FUNNEL"])
    verdict_html = f'<div class="verdict box rise d4 mt">{note_label}{verdict}</div>' if verdict else ""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      {block}
      {verdict_html}
    </div>
  </section>"""


def render_quote_critique(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    quote = esc(slots.get("quote") or slots.get("body") or "")
    cite = esc(slots.get("citation") or slots.get("cite") or "")
    critiques = slots.get("critiques") or slots.get("items") or []
    left = variant == "quote-left"

    cards_html = []
    for i, c in enumerate(critiques[:ITEM_CAP["L-QUOTE-CRITIQUE"]]):
        tag = esc(c.get("tag") or f"批判 {i+1}")
        head = esc(c.get("head") or c.get("point") or "")
        body = esc(c.get("body") or "")
        if left:
            text_html = f"<h3>{head}</h3>\n              <p>{body}</p>" if body else f"<p>{head}</p>"
            cards_html.append(f"""          <div class="critrow rise d{i+2}">
            <span class="pill">{tag}</span>
            <div>
              {text_html}
            </div>
          </div>""")
            continue
        # `- [tag] head: body` used to drop the body silently; show both.
        text_html = (f'<h3 class="mt">{head}</h3>\n            <p>{body}</p>' if body
                     else f'<p class="lead-size mt">{head}</p>')
        cards_html.append(f"""          <div class="card rise d{i+2}">
            <span class="tag">{tag}</span>
            {text_html}
          </div>""")

    if left:
        # The quotation is what someone said, so it sits in a speech bubble with the speaker under its tail.
        body_html = f"""<div class="quote-critique quote-critique--quote-left mt">
        <div class="quote-critique__say rise d1">
          <div class="bubble bubble--tail-down bubble--quote">{quote}</div>
          <p class="quote-critique__who">— {cite}</p>
        </div>
        <div class="quote-critique__rows">
{''.join(cards_html)}
        </div>
      </div>"""
    else:
        body_html = f"""<div class="quote-critique mt">
        <blockquote class="pull rise d1">
          {quote}
          <cite>— {cite}</cite>
        </blockquote>
        <div class="quote-critique__cards mt">
{''.join(cards_html)}
        </div>
      </div>"""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      {body_html}
    </div>
  </section>"""


def render_hypothesis_test(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    hypo = slots.get("hypothesis") or {}
    finding = slots.get("finding") or {}
    puzzle = esc(slots.get("theoretical_puzzle") or slots.get("puzzle") or "")
    puzzle_label = _note_label(slots, CLOSING_LABEL["L-HYPOTHESIS-TEST"])

    h_lbl = esc(hypo.get("label") or DEFAULT_WORDS["hypothesis"])
    h_text = esc(hypo.get("theory_expectation") or hypo.get("head") or "")
    h_logic = esc(hypo.get("logic") or hypo.get("body") or "")

    f_ev = esc(finding.get("empirical_evidence") or finding.get("head") or "")
    f_stat = esc(finding.get("status") or DEFAULT_WORDS["finding_status"])
    f_lbl = esc(finding.get("label") or DEFAULT_WORDS["finding"])

    if variant == "conflict-flow":
        # The expectation is drawn as a dashed outline (not observed), the finding as a filled
        # bubble (observed), with the mismatch between them.
        pair = f"""<div class="hypo-test hypo-test--conflict-flow mt">
        <div class="hypo-box hypo-box--expect rise d1">
          <span class="pill pill--line">{h_lbl}</span>
          <h3>{h_text}</h3>
          <p>{h_logic}</p>
        </div>
        <div class="hypo-clash rise d2" aria-hidden="true">≠</div>
        <div class="bubble hypo-box hypo-box--found rise d2">
          <span class="pill">{f_lbl}：{f_stat}</span>
          <h3>{f_ev}</h3>
        </div>
      </div>"""
    else:
        pair = f"""<div class="hypo-test mt">
        <div class="card rise d1">
          <span class="tag">{h_lbl}</span>
          <h3>{h_text}</h3>
          <p class="mt">{h_logic}</p>
        </div>
        <div class="card card--tint-elevated rise d2">
          <span class="tag" style="color:var(--text)">{f_lbl}：{f_stat}</span>
          <h3>{f_ev}</h3>
        </div>
      </div>"""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      {pair}
      <div class="verdict box rise d3 mt">{puzzle_label}{puzzle}</div>
    </div>
  </section>"""


def render_stat_hero(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    num = esc(slots.get("stat_number") or slots.get("number") or "0")
    lbl = esc(slots.get("stat_label") or slots.get("label") or "")
    context = esc(slots.get("context") or "")
    implications = slots.get("implications") or slots.get("items") or []
    band = variant == "stat-band"

    card_class = "card card--open-rule" if band else "card"
    imp_html = []
    for i, imp in enumerate(implications[:ITEM_CAP["L-STAT-HERO"]]):
        head = esc(imp.get("head") or "")
        body = esc(imp.get("body") or "")
        imp_html.append(f"""          <div class="{card_class} rise d{i+2}">
            <h3>{head}</h3>
            <p>{body}</p>
          </div>""")

    # `<div class="stat-hero__num">` is written the same in both variants: M-COUNT and
    # M-SCRAMBLE find the number by that exact tag.
    if band:
        stat = f"""<div class="stat-hero__stat rise d1">
          <div class="stat-hero__num">{num}</div>
          <div>
            <div class="lead" style="font-weight:700">{lbl}</div>
            <p class="stat-hero__ctx">{context}</p>
          </div>
        </div>"""
    else:
        stat = f"""<div class="stat-hero__stat rise d1">
          <div class="stat-hero__num">{num}</div>
          <div class="lead" style="font-weight:700;margin-top:12px">{lbl}</div>
          <p class="muted mt">{context}</p>
        </div>"""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      <div class="stat-hero stat-hero--{variant} mt">
        {stat}
        <div class="stat-hero__body">
{''.join(imp_html)}
        </div>
      </div>
    </div>
  </section>"""


def render_defn_example(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    term = esc(slots.get("term") or "")
    etym = esc(slots.get("etymology") or slots.get("context") or "")
    defn = esc(slots.get("formal_definition") or slots.get("defn") or slots.get("body") or "")
    pos = esc(slots.get("positive_example") or slots.get("pos_example") or "")
    neg = esc(slots.get("negative_boundary") or slots.get("neg_example") or "")

    etym_html = f'<small>{etym}</small>' if etym else ""
    pos_html = f'<div class="example"><b>{DEFAULT_WORDS["positive"]}</b><p>{pos}</p></div>' if pos else ""
    neg_html = f'<div class="example mt" style="border-left-color:var(--hair)"><b>{DEFAULT_WORDS["negative"]}</b><p>{neg}</p></div>' if neg else ""
    term_html = f"""<h3>{term}{etym_html}</h3>
          <p>{defn}</p>"""

    if variant == "dict-card":
        # One bordered entry, as in a dictionary: headword, definition, then the two examples under a rule.
        neg_cell = neg_html.replace('class="example mt"', 'class="example"')
        examples = f"""
          <div class="dict__ex rise d2">
            {pos_html}
            {neg_cell}
          </div>""" if pos or neg else ""
        block = f"""<div class="defn defn--dict-card mt">
        <div class="dict rise d1">
          <div class="term">
          {term_html}
          </div>{examples}
        </div>
      </div>"""
    elif variant == "split-cards":
        # The example is a filled bubble (inside the concept), the boundary case a dashed outline (outside it).
        pos_card = (f'<div class="bubble defn__pos"><span class="pill">{DEFAULT_WORDS["positive"]}</span>'
                    f'<p>{pos}</p></div>') if pos else ""
        neg_card = (f'<div class="defn__neg"><span class="pill pill--line">{DEFAULT_WORDS["negative"]}</span>'
                    f'<p>{neg}</p></div>') if neg else ""
        block = f"""<div class="defn defn--split-cards mt">
        <div class="term rise d1">
          {term_html}
        </div>
        <div class="defn__pair rise d2">
          {pos_card}
          {neg_card}
        </div>
      </div>"""
    else:
        block = f"""<div class="defn mt">
        <div class="term rise d1">
          {term_html}
        </div>
        <div class="rise d2">
          {pos_html}
          {neg_html}
        </div>
      </div>"""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      {block}
    </div>
  </section>"""


def warn(msg: str) -> str:
    """A compile warning carried inside the rendered HTML; render_row lifts it out and reports it."""
    return f"<!-- deck-compile warning: {html.escape(msg)} -->"


def _canvas_svg(rel_path: str, base: Path | None) -> tuple[str, str]:
    """Inline an SVG file named relative to the talk, so it scales with the slide and takes theme colours."""
    if base is None:
        return "", warn(f"svg: {rel_path} 無法讀取（沒有 talk 目錄）")
    path = (base / rel_path).resolve()
    if base.resolve() not in path.parents:
        return "", warn(f"svg: {rel_path} 不在 talk 目錄裡")
    if not path.is_file():
        return "", warn(f"svg: 找不到 {rel_path}")
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"<\?xml[^>]*\?>|<!DOCTYPE[^>]*>", "", text).strip()
    # The canvas sizes its drawing with `width:auto`, which collapses an SVG that has only a
    # viewBox to zero width; give such a root the viewBox width, as compiled flow charts carry.
    root = re.search(r"<svg\b[^>]*>", text)
    if root and not re.search(r"\swidth\s*=", root.group(0)):
        vb = re.search(r'viewBox\s*=\s*"[\d.\-]+[\s,]+[\d.\-]+[\s,]+([\d.]+)', root.group(0))
        if vb:
            tag = root.group(0)[:-1].rstrip("/").rstrip() + f' width="{vb.group(1)}"' + ("/>" if root.group(0).endswith("/>") else ">")
            text = text[:root.start()] + tag + text[root.end():]
    return text, ""


def _qr_figure(slots: dict[str, Any], ctx: SlideContext, size: int, style: str, rise: str = "") -> str:
    """A QR code (`qr: <SVG path relative to the talk>`) with an optional `qr_label` under it.

    Closing and link slides carry a QR code so the audience can open a URL from their seats.
    `rise` gives it its own entrance (and, through deck-motion, its own beat); leave it empty
    when the code sits inside a block that already rises, so it arrives with that block.
    A div and a p, not figure/figcaption, because deck-motion only gives beats to those tags.
    The SVG is inlined like L-CANVAS `svg:` and pinned to `size` pixels square; a root with only
    width/height gets a viewBox first, because resizing an SVG without one crops it instead of
    scaling it. Generate the SVG with its own white quiet zone, so it scans on a dark theme too.
    """
    rel = slots.get("qr")
    if not rel:
        return ""
    art, note = _canvas_svg(str(rel), ctx.base)
    if not art:
        return note
    root = re.search(r"<svg\b[^>]*>", art)
    if root:
        tag = root.group(0)
        if not re.search(r"\sviewBox\s*=", tag):
            w = re.search(r'\swidth\s*=\s*"([\d.]+)', tag)
            h = re.search(r'\sheight\s*=\s*"([\d.]+)', tag)
            if w and h:
                tag = tag[:4] + f' viewBox="0 0 {w.group(1)} {h.group(1)}"' + tag[4:]
        tag = re.sub(r'\s(width|height)\s*=\s*"[^"]*"', "", tag)
        tag = tag[:4] + f' width="{size}" height="{size}"' + tag[4:]
        art = art[:root.start()] + tag + art[root.end():]
    label = esc(slots.get("qr_label") or "")
    label_html = f'<p class="muted" style="font-size:calc(34px * var(--deck-font-scale, 1));margin:8px 0 0">{label}</p>' if label else ""
    cls = f"qr {rise}".strip()
    return (f'<div class="{cls}" style="{style};width:max-content;text-align:center">'
            f'<div style="width:{size}px;height:{size}px;margin:0 auto">{art}</div>{label_html}</div>')


def render_canvas(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    """The standard frame (top bar with page number, title, optional lead and closing box)
    around one drawing area that fills the rest of the slide.

    The area holds either a left-to-right flow chart compiled from `start`, `lanes` and
    `end`, or an SVG file named by `svg:`, because the free part of a science slide is
    usually a mechanism diagram that no fixed card layout can express.
    """
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    lead = esc(slots.get("lead") or "")
    verdict = esc(slots.get("verdict") or "")
    caption = esc(slots.get("caption") or "")

    notes: list[str] = []
    lanes_raw = slots.get("lanes")
    if isinstance(lanes_raw, list) and lanes_raw:
        lanes = [parse_lane(str(it.get("text") or it.get("head", "")) if isinstance(it, dict) else str(it)) for it in lanes_raw]
        art, flow_warnings = flow_svg(str(slots.get("start") or "開始"), lanes, str(slots.get("end") or "結束"), title)
        notes += [warn(w) for w in flow_warnings]
        if not slots.get("start") or not slots.get("end"):
            notes.append(warn("flow 少了 start 或 end，用「開始」「結束」代替"))
    elif slots.get("svg"):
        art, note = _canvas_svg(str(slots["svg"]), ctx.base)
        art = f'<div class="rise d2">{art}</div>' if art else ""
        notes.append(note)
    else:
        art = ""
        notes.append(warn("L-CANVAS 沒有畫布內容：寫 start／lanes／end（流程圖）或 svg: <檔名>"))
    if not art:
        art = '<div class="canvas-empty">畫布待放圖</div>'

    lead_html = f'<p class="lead rise d1">{lead}</p>' if lead else ""
    caption_html = f'<p class="art-cap">{caption}</p>' if caption else ""
    verdict_html = f'<div class="verdict box rise d4">{_note_label(slots, CLOSING_LABEL["L-CANVAS"])}{verdict}</div>' if verdict else ""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content canvas-frame">
      <h2 class="kicker rise">{title}</h2>
      {lead_html}
      <div class="canvas">{art}</div>
      {caption_html}
      {verdict_html}{''.join(n for n in notes if n)}
    </div>
  </section>"""


def tag_accents(tags: list[str]) -> dict[str, str]:
    """Each distinct tag's chapter colour, in order of first appearance.

    On L-BANNER-6GRID a tag names the card's category, so cards of one category must share a
    colour whatever the slide's own accent is. The order is 1, 4, 2, 3 because --c2 and --c3
    are neighbouring hues in several themes (turquoise and emerald in the default one), and
    a slide rarely has more than three categories.
    """
    order = (1, 4, 2, 3)
    colours: dict[str, str] = {}
    for tag in tags:
        if tag and tag not in colours:
            colours[tag] = f"var(--c{order[len(colours) % 4]})"
    return colours


def _card_grid(cards: list[dict[str, Any]], first_delay: int) -> str:
    """Up to six cards in two or three columns, each with a category pill, a head, an optional
    second name, a gloss and an optional citation; a row of the grid arrives together."""
    colours = tag_accents([str(c.get("tag") or "").strip() for c in cards])
    cols = 2 if len(cards) in (1, 2, 4) else 3
    cards_html = []
    for i, c in enumerate(cards):
        tag = str(c.get("tag") or "").strip()
        head = esc(c.get("head") or "")
        sub = esc(c.get("sub") or "")
        body = esc(c.get("body") or "")
        cite = esc(c.get("cite") or "")
        pill = f'<span class="pill" style="--chapter:{colours[tag]}">{esc(tag)}</span>' if tag else ""
        sub_html = f'\n            <p class="axis__sub">{sub}</p>' if sub else ""
        body_html = f"\n            <p>{body}</p>" if body else ""
        cite_html = f'\n            <p class="axis__cite">{cite}</p>' if cite else ""
        cards_html.append(f"""          <div class="axis__card rise d{min(first_delay + i // cols, 4)}">
            <div class="axis__top"><h3>{head}</h3>{pill}</div>{sub_html}{body_html}{cite_html}
          </div>""")
    return f"""        <div class="axis__grid axis__grid--{cols}">
{chr(10).join(cards_html)}
        </div>"""


def render_6card_grid(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    """Five or six parallel items with a closing box: the grid of L-BANNER-6GRID without a banner.

    At the default density a slide often carries more parallel items than the three- and
    four-card layouts hold, and a row should not need a banner it does not have, or a
    hand-written body, just to show six.
    """
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    lead = esc(slots.get("lead") or "")
    verdict = esc(slots.get("verdict") or "")
    cap = ITEM_CAP["L-6CARD-GRID"]
    cards = (slots.get("cards") or slots.get("items") or [])[:cap]

    lead_html = f'<p class="lead rise">{lead}</p>' if lead else ""
    note_label = _note_label(slots, CLOSING_LABEL["L-6CARD-GRID"])
    verdict_html = f'<div class="verdict box rise d4">{note_label}{verdict}</div>' if verdict else ""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      {lead_html}
      <div class="axis axis--{variant}">
{_card_grid(cards, first_delay=1)}
      </div>
      {verdict_html}
    </div>
  </section>"""


def render_banner_grid(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    """One banner for the idea that frames the slide, over a grid of up to six cards that hang from it.

    A card carries a category pill, a head, an optional second name (`sub`, the term in its
    original language), a one-line gloss and an optional `cite`: the shape of a theory
    framework, where one main theory organises several supporting ones.
    """
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    raw_banner = slots.get("banner")
    banner = raw_banner if isinstance(raw_banner, dict) else {"head": raw_banner or ""}
    all_cards = slots.get("cards") or slots.get("items") or []
    cap = ITEM_CAP["L-BANNER-6GRID"]
    cards = all_cards[:cap]
    notes = warn(f"L-BANNER-6GRID 最多 {cap} 張卡，第 {cap + 1} 張起不會上畫面；拆成兩頁") if len(all_cards) > cap else ""

    b_tag = esc(banner.get("tag") or "")
    b_head = esc(banner.get("head") or banner.get("raw") or "")
    b_sub = esc(banner.get("sub") or "")
    b_body = esc(banner.get("body") or "")
    b_tag_html = f'<span class="axis__tag">{b_tag}</span>' if b_tag else ""
    b_sub_html = f"<small>{b_sub}</small>" if b_sub else ""
    b_body_html = f"<p>{b_body}</p>" if b_body else ""

    grid_html = _card_grid(cards, first_delay=2)

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      <div class="axis axis--{variant}">
        <div class="axis__banner rise d1">
          {b_tag_html}
          <div>
            <h3>{b_head}{b_sub_html}</h3>
            {b_body_html}
          </div>
        </div>
{grid_html}
      </div>{notes}
    </div>
  </section>"""


def _talk_fragment(rel_path: str, base: Path | None) -> tuple[str, str]:
    """(text, warning) of an HTML fragment named relative to the talk; files outside the talk are refused."""
    if base is None:
        return "", warn(f"html: {rel_path} 無法讀取（沒有 talk 目錄）")
    path = (base / rel_path).resolve()
    if base.resolve() not in path.parents:
        return "", warn(f"html: {rel_path} 不在 talk 目錄裡")
    if not path.is_file():
        return "", warn(f"html: 找不到 {rel_path}")
    text = path.read_text(encoding="utf-8").strip()
    if re.search(r"<(section|deck-stage|script)\b", text):
        return "", warn(f"html: {rel_path} 只寫投影片內文，不含 <section>、<deck-stage> 或 <script>；外框由 L-CUSTOM 產生")
    return text, ""


def render_custom(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    """The standard frame (top bar, title, optional lead and closing box) around a body written by hand.

    For a row no catalog layout can show whole. The body is a file in the talk
    (`html: <path>`), kept across compiles, so adding a form does not need the framework,
    which a course only has as a read-only submodule. What the row says stays in the
    storyboard: `deck-compile` checks the body shows every piece of it, so the file holds
    the form and never becomes a second place to edit the words.
    """
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    lead = esc(slots.get("lead") or "")
    verdict = esc(slots.get("verdict") or "")
    rel = slots.get("html")
    if isinstance(rel, str) and rel.strip():
        body, note = _talk_fragment(rel.strip(), ctx.base)
    else:
        body, note = "", warn("L-CUSTOM 要寫 html: <相對 talk 的檔名>，檔案內容是這一頁的內文 HTML")
    if not body:
        body = '<div class="canvas-empty">手寫版面待放</div>'

    lead_html = f'<p class="lead rise d1">{lead}</p>' if lead else ""
    verdict_html = f'<div class="verdict box rise d4">{_note_label(slots, CLOSING_LABEL["L-CUSTOM"])}{verdict}</div>' if verdict else ""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      {lead_html}
      <div class="custom">
{body}
      </div>
      {verdict_html}{note}
    </div>
  </section>"""


# =========================================================================
# Layout Catalog Registry
# =========================================================================

CATALOG: dict[str, LayoutDefinition] = {
    # 1. Declarative
    "L-HERO-TITLE": LayoutDefinition(
        id="L-HERO-TITLE",
        family="Declarative",
        name="開場主封面",
        required_slots=["title"],
        allowed_variants=["default"],
        render_func=render_hero_title,
        optional_slots=["sub", "meta", "subtitle", "author"],
    ),
    "L-FINALE-SUMMARY": LayoutDefinition(
        id="L-FINALE-SUMMARY",
        family="Declarative",
        name="閉幕與核心結論",
        required_slots=["heading"],
        allowed_variants=["default"],
        render_func=render_finale_summary,
        optional_slots=["onesentence", "points", "verdict", "points_align", "qr", "qr_label"],
    ),

    # 2. Parallel Expansion & Synthesis
    "L-3CARD-VERDICT": LayoutDefinition(
        id="L-3CARD-VERDICT",
        family="Parallel",
        name="三子項展開＋底部定論",
        required_slots=["title", "cards", "verdict"],
        allowed_variants=["top-rail", "open-rule", "bubble"],
        render_func=render_3card_verdict,
        optional_slots=["lead"],
    ),
    "L-4CARD-GRID": LayoutDefinition(
        id="L-4CARD-GRID",
        family="Parallel",
        name="四象限／四支柱均等網格",
        required_slots=["title", "cards"],
        allowed_variants=["grid-2x2", "numbered-1-4", "pillars"],
        render_func=render_4card_grid,
        optional_slots=["lead", "verdict"],
    ),
    "L-6CARD-GRID": LayoutDefinition(
        id="L-6CARD-GRID",
        family="Parallel",
        name="五到六項均等網格",
        required_slots=["title", "cards"],
        allowed_variants=["soft-cards", "ruled-cells"],
        render_func=render_6card_grid,
        optional_slots=["lead", "verdict"],
    ),
    "L-BENTO-FOCUS": LayoutDefinition(
        id="L-BENTO-FOCUS",
        family="Parallel",
        name="便當盒非對稱焦點",
        required_slots=["title"],
        allowed_variants=["left-heavy", "top-heavy"],
        render_func=render_bento_focus,
        optional_slots=["lead", "hero_card", "sub_cards", "cards", "verdict"],
    ),
    "L-BANNER-6GRID": LayoutDefinition(
        id="L-BANNER-6GRID",
        family="Parallel",
        name="主軸橫幅＋六卡網格",
        required_slots=["title", "banner", "cards"],
        allowed_variants=["soft-cards", "ruled-cells"],
        render_func=render_banner_grid,
    ),
    "L-SPLIT-ANCHOR": LayoutDefinition(
        id="L-SPLIT-ANCHOR",
        family="Parallel",
        name="1:2 概念錨點式",
        required_slots=["title", "items"],
        allowed_variants=["card-list", "quote-style"],
        render_func=render_split_anchor,
        optional_slots=["anchor_statement", "anchor", "cite", "footer_cite", "qr", "qr_label"],
    ),

    # 3. Relational, Contrast & Typology
    "L-VS-CONFRONT": LayoutDefinition(
        id="L-VS-CONFRONT",
        family="Relational",
        name="兩造交鋒對峙",
        required_slots=["title", "side_a", "side_b"],
        allowed_variants=["card-versus", "split-rail", "speech-bubbles"],
        render_func=render_vs_confront,
        optional_slots=["issue", "claim", "ask_or_verdict", "ask", "verdict"],
    ),
    "L-MATRIX-DEEPDIVE": LayoutDefinition(
        id="L-MATRIX-DEEPDIVE",
        family="Relational",
        name="2×2 矩陣＋焦點象限引出",
        required_slots=["title", "axis_x", "axis_y", "deepdive_note"],
        allowed_variants=["split-note", "floating-callout"],
        render_func=render_matrix_deepdive,
        optional_slots=["cells", "focus_quadrant"],
    ),
    "L-SPECTRUM-POLES": LayoutDefinition(
        id="L-SPECTRUM-POLES",
        family="Relational",
        name="光譜軸線＋端點案例錨定",
        required_slots=["title", "pole_left", "pole_right", "markers"],
        allowed_variants=["gradient-bar", "step-pills"],
        render_func=render_spectrum_poles,
        optional_slots=["verdict"],
    ),

    # 4. Temporal & Causal Progression
    "L-FLOW-3STAGE": LayoutDefinition(
        id="L-FLOW-3STAGE",
        family="Progression",
        name="三階段機制推演鏈",
        required_slots=["title", "stages"],
        allowed_variants=["node-arrow", "chevron-step", "disc-rail"],
        render_func=render_flow_3stage,
        optional_slots=["lead", "verdict"],
    ),
    "L-TIMELINE-RAIL": LayoutDefinition(
        id="L-TIMELINE-RAIL",
        family="Progression",
        name="軌道式大事記時間軸",
        required_slots=["title", "events"],
        allowed_variants=["top-rail", "alternating"],
        render_func=render_timeline_rail,
        optional_slots=["takeaway", "verdict"],
    ),
    "L-CASCADE-FUNNEL": LayoutDefinition(
        id="L-CASCADE-FUNNEL",
        family="Progression",
        name="漏斗層層收斂",
        required_slots=["title", "levels"],
        allowed_variants=["stacked-tiers", "concentric-cards"],
        render_func=render_cascade_funnel,
        optional_slots=["core_focus", "verdict"],
    ),
    "L-CANVAS": LayoutDefinition(
        id="L-CANVAS",
        family="Progression",
        name="標準外框＋自由畫布",
        required_slots=["title"],
        allowed_variants=["default"],
        render_func=render_canvas,
        optional_slots=["lead", "start", "lanes", "end", "svg", "caption", "verdict"],
    ),
    "L-CUSTOM": LayoutDefinition(
        id="L-CUSTOM",
        family="Progression",
        name="標準外框＋手寫版面",
        required_slots=["title", "html"],
        allowed_variants=["default"],
        render_func=render_custom,
        optional_slots=["lead", "verdict"],
    ),

    # 5. Scholarly Critique & Evidence
    "L-QUOTE-CRITIQUE": LayoutDefinition(
        id="L-QUOTE-CRITIQUE",
        family="Critique",
        name="文獻原話引述＋三重解構",
        required_slots=["title", "quote", "critiques"],
        allowed_variants=["quote-top", "quote-left"],
        render_func=render_quote_critique,
        optional_slots=["citation", "cite"],
    ),
    "L-HYPOTHESIS-TEST": LayoutDefinition(
        id="L-HYPOTHESIS-TEST",
        family="Critique",
        name="理論假設 vs 實證落差",
        required_slots=["title", "hypothesis", "finding", "theoretical_puzzle"],
        allowed_variants=["contrast-pillars", "conflict-flow"],
        render_func=render_hypothesis_test,
        optional_slots=["puzzle"],
    ),
    "L-STAT-HERO": LayoutDefinition(
        id="L-STAT-HERO",
        family="Critique",
        name="單一震撼數據指標",
        required_slots=["title", "stat_number", "context", "implications"],
        allowed_variants=["stat-left", "stat-band"],
        render_func=render_stat_hero,
        optional_slots=["stat_label", "number", "label"],
    ),
    "L-DEFN-EXAMPLE": LayoutDefinition(
        id="L-DEFN-EXAMPLE",
        family="Critique",
        name="概念界定與典型例證",
        required_slots=["title", "term"],
        allowed_variants=["side-notes", "dict-card", "split-cards"],
        render_func=render_defn_example,
        optional_slots=["formal_definition", "defn", "body", "positive_example", "pos_example", "negative_boundary", "neg_example", "etymology", "context"],
    ),
}

# Alias mapping to accommodate slight variations
ALIASES = {
    ".hero": "L-HERO-TITLE",
    "hero": "L-HERO-TITLE",
    ".finale": "L-FINALE-SUMMARY",
    "finale": "L-FINALE-SUMMARY",
    "l-3card": "L-3CARD-VERDICT",
    "l-4card": "L-4CARD-GRID",
    "l-6card": "L-6CARD-GRID",
    "l-bento": "L-BENTO-FOCUS",
    "l-banner": "L-BANNER-6GRID",
    "l-vs": "L-VS-CONFRONT",
    "l-matrix": "L-MATRIX-DEEPDIVE",
    "l-spectrum": "L-SPECTRUM-POLES",
    "l-flow": "L-FLOW-3STAGE",
    "l-timeline": "L-TIMELINE-RAIL",
    "l-funnel": "L-CASCADE-FUNNEL",
    "l-canvas": "L-CANVAS",
    "l-custom": "L-CUSTOM",
    "l-quote": "L-QUOTE-CRITIQUE",
    "l-hypothesis": "L-HYPOTHESIS-TEST",
    "l-stat": "L-STAT-HERO",
    "l-defn": "L-DEFN-EXAMPLE",
}


def get_layout(layout_id: str) -> LayoutDefinition:
    lid = layout_id.strip()
    if lid in CATALOG:
        return CATALOG[lid]
    normalized = ALIASES.get(lid.lower())
    if normalized and normalized in CATALOG:
        return CATALOG[normalized]
    # Check if lid without dots or uppercase matches
    for k, v in CATALOG.items():
        if k.lower() == lid.lower() or k.replace("L-", "").lower() == lid.lower():
            return v
    raise ValueError(f"未知的版型代碼 '{layout_id}'。支援的代碼：{', '.join(sorted(CATALOG.keys()))}")
