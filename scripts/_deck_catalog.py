"""The presentation layout catalog and slot parser for thesisbug2.

Defines the 16 standard layout codes across 5 families, their slot schemas,
seeded depth variants, and deterministic HTML renderers.

Layout catalog v1.0:
  1. Declarative & Thesis:
     - L-HERO-TITLE
     - L-FINALE-SUMMARY
  2. Parallel Expansion & Synthesis:
     - L-3CARD-VERDICT
     - L-4CARD-GRID
     - L-BENTO-FOCUS
     - L-SPLIT-ANCHOR
  3. Relational, Contrast & Typology:
     - L-VS-CONFRONT
     - L-MATRIX-DEEPDIVE
     - L-SPECTRUM-POLES
  4. Temporal & Causal Progression:
     - L-FLOW-3STAGE
     - L-TIMELINE-RAIL
     - L-CASCADE-FUNNEL
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
from typing import Any, Callable


@dataclass
class SlideContext:
    slide_num: int
    total_slides: int
    accent: str
    eyebrow: str
    data_label: str
    variant: str


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
                items = [item.strip().strip("'\"") for item in v[1:-1].split(",") if item.strip()]
                result[k] = items
            else:
                result[k] = v
        if result:
            return result
    return {"raw": s}


def parse_slot_payload(raw_text: str) -> dict[str, Any]:
    """Parse the structured micro-syntax in storyboard '畫面內容' into slot dict.

    Supports:
      key: value
      cards:
      - [tag] head: body
      - head | body
      - [tag] point
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
            if tag:
                item["tag"] = tag
            if part2:
                item["head"] = part1
                item["body"] = part2
            else:
                item["head"] = part1
                item["body"] = ""
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
        self.prev_variant: str | None = None

    def resolve(
        self,
        layout: LayoutDefinition,
        slide_num: int,
        total_slides: int,
        eyebrow: str,
        title: str,
    ) -> tuple[SlideContext, str]:
        # 1. Accent cycling: choose from --c1..--c4, never repeat previous
        accents = [f"var(--c{i})" for i in range(1, 5) if f"var(--c{i})" != self.prev_accent]
        chosen_accent = self.rng.choice(accents)
        self.prev_accent = chosen_accent

        # 2. Variant selection: choose from allowed variants
        variants = layout.allowed_variants
        if len(variants) > 1 and self.prev_variant in variants:
            cands = [v for v in variants if v != self.prev_variant]
            chosen_variant = self.rng.choice(cands)
        else:
            chosen_variant = self.rng.choice(variants) if variants else "default"
        self.prev_variant = chosen_variant

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
# Renderers for the 16 Standard Layouts
# =========================================================================

def _render_topbar(ctx: SlideContext) -> str:
    return f"""      <div class="railtop"></div>
      <div class="topbar">
        <span class="eyebrow">{esc(ctx.eyebrow)}</span>
        <span class="chap"><b>{ctx.slide_num}</b> / {ctx.total_slides}</span>
      </div>"""


def _dlabel(slots: dict[str, Any], default: str) -> str:
    return esc(slots.get("label") or slots.get("data_label") or default)


NO_LABEL = {"none", "無", "-", "—"}


def _note_label(slots: dict[str, Any], default: str) -> str:
    """Bold prefix of a layout's closing box (verdict, takeaway, puzzle...).

    Each layout keeps a default word for what that box usually holds, but the
    same box can carry a mechanism, a case observation or a discussion
    procedure, and a fixed word like 定論 then mislabels the content. So a
    slide may set `verdict_label: <word>` to rename the prefix, or
    `verdict_label: none` to drop it.
    """
    raw = slots.get("verdict_label")
    if raw is None:
        return f"<em>{default}：</em>"
    if isinstance(raw, list):          # `verdict_label:` with no value
        return ""
    text = str(raw).strip()
    if not text or text.lower() in NO_LABEL:
        return ""
    return f"<em>{esc(text)}：</em>"


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
        li_items = "".join(f"<li>{esc(p.get('head', p) if isinstance(p, dict) else p)}</li>" for p in pts)
        # Long points wrap; centred wrapped lines are hard to follow, so a slide
        # may set `points_align: left` while the heading stays centred.
        align = ' style="text-align:left"' if str(slots.get("points_align") or "").strip().lower() == "left" else ""
        pts_html = f'<ul class="clean lead-size rise d2 mt"{align}>{li_items}</ul>'

    return f"""  <section class="slide finale" data-label="{dlabel}">
    <div class="railtop"></div>
    <div class="content">
      <h2 class="rise">{heading}</h2>
      <p class="onesentence rise d1">{onesentence}</p>
      {pts_html}
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
    for i, c in enumerate(cards[:3]):
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

    note_label = _note_label(slots, "結論")
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
    card_class = f"card card--{variant}"

    cards_html = []
    for i, c in enumerate(cards[:4]):
        tag = esc(c.get("tag") or (f"0{i+1}" if variant == "numbered-1-4" else ""))
        head = esc(c.get("head") or "")
        body = esc(c.get("body") or "")
        tag_html = f'<span class="tag">{tag}</span>' if tag else ""
        delay = f"d{i+1}"
        cards_html.append(f"""        <div class="{card_class} rise {delay}">
          {tag_html}
          <h3>{head}</h3>
          <p>{body}</p>
        </div>""")

    note_label = _note_label(slots, "定論")
    verdict_html = f'<div class="verdict box rise d4">{note_label}{verdict}</div>' if verdict else ""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      {lead_html}
      <div class="grid two mt">
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
    subs = slots.get("sub_cards") or (slots.get("cards") or [{}, {}, {}])[1:3]
    verdict = esc(slots.get("verdict") or "")

    lead_html = f'<p class="lead rise">{lead}</p>' if lead else ""
    hero_tag = esc(hero.get("tag") or "核心焦點")
    hero_head = esc(hero.get("head") or "")
    hero_body = esc(hero.get("body") or "")

    sub_cards_html = []
    for i, s in enumerate(subs[:2]):
        stag = esc(s.get("tag") or "")
        shead = esc(s.get("head") or "")
        sbody = esc(s.get("body") or "")
        tag_span = f'<span class="tag">{stag}</span>' if stag else ""
        sub_cards_html.append(f"""          <div class="card rise d{i+2}">
            {tag_span}
            <h3>{shead}</h3>
            <p>{sbody}</p>
          </div>""")

    note_label = _note_label(slots, "定論")
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

    items_html = []
    for i, item in enumerate(items[:3]):
        head = esc(item.get("head") or "")
        body = esc(item.get("body") or "")
        tag = esc(item.get("tag") or "")
        tag_span = f'<span class="tag">{tag}</span>' if tag else ""
        items_html.append(f"""          <div class="card rise d{i+2}">
            {tag_span}
            <h3>{head}</h3>
            <p>{body}</p>
          </div>""")

    cite_html = f'<div class="muted mt" style="font-size:32px">出處：{cite}</div>' if cite else ""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      <div class="split-anchor mt">
        <div class="split-anchor__hero rise d1">
          <blockquote class="pull">
            {anchor}
          </blockquote>
          {cite_html}
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
    note_label = _note_label(slots, "裁決／提問")
    verdict_html = f'<div class="verdict box rise d3">{note_label}{verdict}</div>' if verdict else ""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      {issue_html}
      <div class="confront mt">
        <div class="card confront__side rise d1">
          <span class="tag">{camp_a}</span>
          <ul class="clean lead-size mt">
            {pts_a_html}
          </ul>
        </div>
        <div class="confront__vs rise d2">
          <div class="confront__badge">VS</div>
        </div>
        <div class="card confront__side rise d1">
          <span class="tag" style="color:var(--text)">{camp_b}</span>
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
    # `focus_quadrant: none` (or 0) highlights no cell: a typology offered as a
    # question should not visually pre-assign a case to a quadrant.
    fq = str(slots.get("focus_quadrant") if slots.get("focus_quadrant") is not None else 1).strip().lower()
    focus = int(fq) if fq.isdigit() and 1 <= int(fq) <= 4 else 0
    note = esc(slots.get("deepdive_note") or "")
    note_tag = esc(slots.get("note_label") or (f"焦點象限特寫 (Q{focus})" if focus else "解讀"))
    # `matrix_width: wide` gives the matrix most of the row: cell text wraps
    # every few characters at the default split, burying the typology.
    wide = " matrix-deepdive--wide" if str(slots.get("matrix_width") or "").strip().lower() == "wide" else ""

    # Format 2x2 cells
    cell_map = {1: ("低", "低"), 2: ("低", "高"), 3: ("高", "低"), 4: ("高", "高")}
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

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      <div class="matrix-deepdive{wide} mt">
        {matrix_table}
        <div class="card card--tint-elevated matrix-deepdive__note rise d2">
          <span class="tag">{note_tag}</span>
          <p class="lead-size mt">{note}</p>
        </div>
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

    marks_html = []
    for m in markers:
        pct = m.get("position_pct") or m.get("pct") or 50
        lbl = esc(m.get("label") or m.get("head") or "")
        desc = esc(m.get("desc") or m.get("body") or "")
        marks_html.append(f"""        <div class="mark" style="left:{pct}%">
          <b>{lbl}</b>
          <span>{desc}</span>
        </div>""")

    note_label = _note_label(slots, "定論")
    verdict_html = f'<div class="verdict box rise d3 mt">{note_label}{verdict}</div>' if verdict else ""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      <div class="spectrum mt">
        <div class="marks rise d1">
{''.join(marks_html)}
        </div>
        <div class="bar"></div>
        <div class="ends">
          <span>{pole_l}</span>
          <span>{pole_r}</span>
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
    for i, s in enumerate(stages[:3]):
        head = esc(s.get("head") or f"階段 {i+1}")
        body = esc(s.get("body") or "")
        flow_nodes.append(f"""        <div class="flownode rise d{i+1}">
          <h3>{head}</h3>
          <p>{body}</p>
        </div>""")
        if i < 2 and i < len(stages) - 1:
            flow_nodes.append('        <div class="flowarrow">→</div>')

    note_label = _note_label(slots, "最終均衡")
    verdict_html = f'<div class="verdict box rise d4 mt">{note_label}{verdict}</div>' if verdict else ""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      {lead_html}
      <div class="flowdiag mt">
{''.join(flow_nodes)}
      </div>
      {verdict_html}
    </div>
  </section>"""


def render_timeline_rail(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    events = slots.get("events") or slots.get("items") or []
    takeaway = esc(slots.get("takeaway") or slots.get("verdict") or "")

    tls = []
    for i, ev in enumerate(events[:5]):
        time_str = esc(ev.get("time") or ev.get("tag") or "")
        head = esc(ev.get("head") or "")
        body = esc(ev.get("body") or "")
        tls.append(f"""        <div class="tl rise d{i+1}">
          <time>{time_str}</time>
          <b>{head}</b>
          <p>{body}</p>
        </div>""")

    note_label = _note_label(slots, "歷史啟示")
    takeaway_html = f'<div class="verdict box rise d4 mt">{note_label}{takeaway}</div>' if takeaway else ""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      <div class="timeline mt">
{''.join(tls)}
      </div>
      {takeaway_html}
    </div>
  </section>"""


def render_cascade_funnel(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    levels = slots.get("levels") or slots.get("items") or []
    verdict = esc(slots.get("core_focus") or slots.get("verdict") or "")

    # `label_width: narrow` shrinks the 400px level-name column for short names
    # such as 條約／組織／協議, so the description gets the width.
    narrow = " tiers--narrow" if str(slots.get("label_width") or "").strip().lower() == "narrow" else ""

    tiers = []
    for i, lv in enumerate(levels[:3]):
        lvl_name = esc(lv.get("level_name") or lv.get("tag") or f"層級 {i+1}")
        head = esc(lv.get("head") or "")
        body = esc(lv.get("body") or "")
        tiers.append(f"""        <div class="tier rise d{i+1}">
          <div style="font-weight:700;color:var(--chapter);font-size:36px">{lvl_name}</div>
          <div>
            <h3 style="font-size:42px;margin:0 0 6px">{head}</h3>
            <p style="margin:0;font-size:36px;color:var(--body)">{body}</p>
          </div>
        </div>""")

    note_label = _note_label(slots, "核心焦點")
    verdict_html = f'<div class="verdict box rise d4 mt">{note_label}{verdict}</div>' if verdict else ""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      <div class="tiers{narrow} mt">
{''.join(tiers)}
      </div>
      {verdict_html}
    </div>
  </section>"""


def render_quote_critique(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    quote = esc(slots.get("quote") or slots.get("body") or "")
    cite = esc(slots.get("citation") or slots.get("cite") or "")
    critiques = slots.get("critiques") or slots.get("items") or []

    cards_html = []
    for i, c in enumerate(critiques[:3]):
        tag = esc(c.get("tag") or f"批判 {i+1}")
        head = esc(c.get("head") or c.get("point") or "")
        body = esc(c.get("body") or "")
        # `- [tag] head: body` used to drop the body silently; show both.
        text_html = (f'<h3 class="mt">{head}</h3>\n            <p>{body}</p>' if body
                     else f'<p class="lead-size mt">{head}</p>')
        cards_html.append(f"""          <div class="card rise d{i+2}">
            <span class="tag">{tag}</span>
            {text_html}
          </div>""")

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      <div class="quote-critique mt">
        <blockquote class="pull rise d1">
          {quote}
          <cite>— {cite}</cite>
        </blockquote>
        <div class="quote-critique__cards mt">
{''.join(cards_html)}
        </div>
      </div>
    </div>
  </section>"""


def render_hypothesis_test(slots: dict[str, Any], variant: str, ctx: SlideContext) -> str:
    title = esc(slots.get("title") or "")
    dlabel = _dlabel(slots, title)
    hypo = slots.get("hypothesis") or {}
    finding = slots.get("finding") or {}
    puzzle = esc(slots.get("theoretical_puzzle") or slots.get("puzzle") or "")
    puzzle_label = _note_label(slots, "理論謎題／意涵")

    h_lbl = esc(hypo.get("label") or "理論預期 (H1)")
    h_text = esc(hypo.get("theory_expectation") or hypo.get("head") or "")
    h_logic = esc(hypo.get("logic") or hypo.get("body") or "")

    f_ev = esc(finding.get("empirical_evidence") or finding.get("head") or "")
    f_stat = esc(finding.get("status") or "實證落差")
    f_lbl = esc(finding.get("label") or "實證發現")

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      <div class="hypo-test mt">
        <div class="card rise d1">
          <span class="tag">{h_lbl}</span>
          <h3>{h_text}</h3>
          <p class="mt">{h_logic}</p>
        </div>
        <div class="card card--tint-elevated rise d2">
          <span class="tag" style="color:var(--text)">{f_lbl}：{f_stat}</span>
          <h3>{f_ev}</h3>
        </div>
      </div>
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

    imp_html = []
    for i, imp in enumerate(implications[:2]):
        head = esc(imp.get("head") or "")
        body = esc(imp.get("body") or "")
        imp_html.append(f"""          <div class="card rise d{i+2}">
            <h3>{head}</h3>
            <p>{body}</p>
          </div>""")

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      <div class="stat-hero mt">
        <div class="stat-hero__stat rise d1">
          <div class="stat-hero__num">{num}</div>
          <div class="lead" style="font-weight:700;margin-top:12px">{lbl}</div>
          <p class="muted mt" style="font-size:32px">{context}</p>
        </div>
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
    pos_html = f'<div class="example"><b>典型例證</b><p>{pos}</p></div>' if pos else ""
    neg_html = f'<div class="example mt" style="border-left-color:var(--hair)"><b>邊界／反例</b><p>{neg}</p></div>' if neg else ""

    return f"""  <section class="slide" style="--chapter:{ctx.accent}" data-label="{dlabel}">
{_render_topbar(ctx)}
    <div class="content">
      <h2 class="kicker rise">{title}</h2>
      <div class="defn mt">
        <div class="term rise d1">
          <h3>{term}{etym_html}</h3>
          <p>{defn}</p>
        </div>
        <div class="rise d2">
          {pos_html}
          {neg_html}
        </div>
      </div>
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
        optional_slots=["onesentence", "points", "verdict"],
    ),

    # 2. Parallel Expansion & Synthesis
    "L-3CARD-VERDICT": LayoutDefinition(
        id="L-3CARD-VERDICT",
        family="Parallel",
        name="三子項展開＋底部定論",
        required_slots=["title", "cards", "verdict"],
        allowed_variants=["top-rail", "tint-elevated", "side-border"],
        render_func=render_3card_verdict,
        optional_slots=["lead"],
    ),
    "L-4CARD-GRID": LayoutDefinition(
        id="L-4CARD-GRID",
        family="Parallel",
        name="四象限／四支柱均等網格",
        required_slots=["title", "cards"],
        allowed_variants=["grid-2x2", "numbered-1-4"],
        render_func=render_4card_grid,
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
    "L-SPLIT-ANCHOR": LayoutDefinition(
        id="L-SPLIT-ANCHOR",
        family="Parallel",
        name="1:2 概念錨點式",
        required_slots=["title", "items"],
        allowed_variants=["quote-style", "card-list"],
        render_func=render_split_anchor,
        optional_slots=["anchor_statement", "anchor", "cite", "footer_cite"],
    ),

    # 3. Relational, Contrast & Typology
    "L-VS-CONFRONT": LayoutDefinition(
        id="L-VS-CONFRONT",
        family="Relational",
        name="兩造交鋒對峙",
        required_slots=["title", "side_a", "side_b"],
        allowed_variants=["split-rail", "card-versus"],
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
        allowed_variants=["node-arrow", "chevron-step"],
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
        allowed_variants=["stat-left", "stat-center"],
        render_func=render_stat_hero,
        optional_slots=["stat_label", "number", "label"],
    ),
    "L-DEFN-EXAMPLE": LayoutDefinition(
        id="L-DEFN-EXAMPLE",
        family="Critique",
        name="概念界定與典型例證",
        required_slots=["title", "term"],
        allowed_variants=["dict-card", "split-cards"],
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
    "l-bento": "L-BENTO-FOCUS",
    "l-vs": "L-VS-CONFRONT",
    "l-matrix": "L-MATRIX-DEEPDIVE",
    "l-spectrum": "L-SPECTRUM-POLES",
    "l-flow": "L-FLOW-3STAGE",
    "l-timeline": "L-TIMELINE-RAIL",
    "l-funnel": "L-CASCADE-FUNNEL",
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
