"""Left-to-right flow diagrams for the L-CANVAS layout: one start, one end, parallel lanes between.

The shape is the activity-on-node chart science talks keep needing (a batch goes in,
two mechanisms run side by side, a prediction comes out). Its layout is fixed — start
on the left, end on the right, one row per lane — so coordinates are computed here
rather than handed to an auto-layout tool: PlantUML's current activity syntax only runs
top to bottom, and Graphviz-based output (PlantUML's legacy syntax, dot) carries
hard-coded colours and its own font size, which the deck would have to post-process
and would still scale below the 34px floor.

The SVG uses deck-svg's diagram primitives (`svg.art.dg`: `.box`, `.box.hi`, `.box.fill`,
`.edge`, `.ah`, `text.acc`, `text.sub`), so it follows the theme and the type floor.
Its viewBox is the slide's content width in pixels, which keeps the text at 34px
instead of letting the browser scale it. Groups carry `.rise d1–d4` (start, lanes, end)
so the entrance and the lively mode's beats reveal the chart in reading order.

Standard library only.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

WIDTH = 1728          # slide content width: 1920 − 2 × 96px side padding (deck.css .slide)
FONT = 34             # deck type floor; svg.dg text is 34px
NODE_H = 92
PAD_X = 28            # text padding inside a node
GAP_MIN = 72          # room for an arrow between two nodes
LANE_LABEL = 52       # height of a lane's label line above its nodes
LANE_GAP = 44
ARROW = 16
TIP_GAP = 8           # arrow tip stops this far short of the next node's border, so it never sits on it


@dataclass
class Node:
    text: str
    hi: bool = False


@dataclass
class Lane:
    label: str
    nodes: list[Node]


def em(text: str) -> float:
    """Rendered width in em: CJK and full-width about 1em, Latin, digits and ASCII about half."""
    return sum(1.0 if ord(c) > 0x2E7F else 0.56 for c in text)


def parse_node(raw: str) -> Node:
    """`*對齊原始分數*` marks a node the slide is about (outlined in the chapter colour)."""
    t = raw.strip()
    m = re.fullmatch(r"\*(.+)\*", t)
    return Node(m.group(1).strip(), True) if m else Node(t)


def parse_lane(raw: str) -> Lane:
    """`[分類器] 交叉熵 → *對齊原始分數* → 長度對齊` → a labelled lane; `->` also separates."""
    t = raw.strip()
    label = ""
    m = re.match(r"^\[(.*?)\]\s*(.*)$", t)
    if m:
        label, t = m.group(1).strip(), m.group(2)
    nodes = [parse_node(p) for p in re.split(r"\s*(?:→|->)\s*", t) if p.strip()]
    return Lane(label, nodes)


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _arrow(x: float, y: float) -> str:
    """Arrowhead pointing right with its tip at (x, y)."""
    return f'<polygon class="ah" points="{x:.1f},{y:.1f} {x - ARROW * 1.4:.1f},{y - ARROW:.1f} {x - ARROW * 1.4:.1f},{y + ARROW:.1f}"/>'


def _node(x: float, y: float, w: float, node: Node, cls: str = "box", rx: float = 14) -> str:
    box = f'{cls} hi' if node.hi else cls
    txt = ' class="acc"' if node.hi else ""
    return (f'<rect class="{box}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{NODE_H}" rx="{rx:.1f}"/>'
            f'<text x="{x + w / 2:.1f}" y="{y + NODE_H / 2 + FONT * 0.36:.1f}" text-anchor="middle"{txt}>{_esc(node.text)}</text>')


def flow_svg(start: str, lanes: list[Lane], end: str, label: str = "") -> tuple[str, list[str]]:
    """The chart as one `<svg class="art dg">` string, and warnings for anything that does not fit."""
    warnings: list[str] = []
    lanes = [ln for ln in lanes if ln.nodes]
    if not lanes:
        return "", ["flow 沒有任何路線（lanes: 底下每列一條，節點以 → 分隔）"]
    if len(lanes) > 4:
        warnings.append(f"flow 有 {len(lanes)} 條路線，超過 4 條會擠到 34px 以下；只畫前 4 條")
        lanes = lanes[:4]

    term_w = max(em(start), em(end)) * FONT + 2 * PAD_X
    node_w = max(em(n.text) for ln in lanes for n in ln.nodes) * FONT + 2 * PAD_X
    x0 = term_w + GAP_MIN                       # first lane node may start here
    x1 = WIDTH - term_w - GAP_MIN               # last lane node must end here
    span = x1 - x0
    widest = max(len(ln.nodes) for ln in lanes)
    if widest * node_w + (widest - 1) * GAP_MIN > span:
        warnings.append(f"flow 最長的路線（{widest} 個節點）放不下：縮短節點文字或拆頁，字不會縮小")

    lane_h = LANE_LABEL + NODE_H
    height = len(lanes) * lane_h + (len(lanes) - 1) * LANE_GAP
    cy = height / 2
    beats = ["d2", "d3", "d2", "d3"]             # lanes alternate so the end (d4) stays last

    parts = [f'<g class="rise d1">{_node(0, cy - NODE_H / 2, term_w, Node(start), "box fill", NODE_H / 2)}</g>']
    for i, ln in enumerate(lanes):
        top = i * (lane_h + LANE_GAP)
        y = top + LANE_LABEL
        my = y + NODE_H / 2
        n = len(ln.nodes)
        gap = (span - n * node_w) / (n - 1) if n > 1 else 0
        xs = [x0 + k * (node_w + gap) for k in range(n)] if n > 1 else [x0 + (span - node_w) / 2]
        g = []
        if ln.label:
            g.append(f'<text class="sub" x="{xs[0]:.1f}" y="{top + FONT:.1f}">{_esc(ln.label)}</text>')
        # start → first node. Every lane splits off at the same x, just right of the start
        # and left of every first node, so a branch never runs through another lane's
        # nodes (with an odd lane count the middle lane sits on the centre line).
        xf = term_w + GAP_MIN / 2
        g.append(f'<path class="edge" d="M{term_w:.1f},{cy:.1f} H{xf:.1f} V{my:.1f} H{xs[0] - TIP_GAP:.1f}"/>{_arrow(xs[0] - TIP_GAP, my)}')
        for k, node in enumerate(ln.nodes):
            g.append(_node(xs[k], y, node_w, node))
            if k + 1 < n:
                g.append(f'<path class="edge" d="M{xs[k] + node_w:.1f},{my:.1f} H{xs[k + 1] - TIP_GAP:.1f}"/>{_arrow(xs[k + 1] - TIP_GAP, my)}')
        # last node → end, merging at one x right of every last node, for the same reason
        xe = WIDTH - term_w
        xj = x1 + GAP_MIN / 2
        g.append(f'<path class="edge" d="M{xs[-1] + node_w:.1f},{my:.1f} H{xj:.1f} V{cy:.1f} H{xe - TIP_GAP:.1f}"/>{_arrow(xe - TIP_GAP, cy)}')
        parts.append(f'<g class="rise {beats[i]}">{"".join(g)}</g>')
    parts.append(f'<g class="rise d4">{_node(WIDTH - term_w, cy - NODE_H / 2, term_w, Node(end), "box fill", NODE_H / 2)}</g>')

    aria = _esc(label or f"{start} 經 {len(lanes)} 條路線到 {end}")
    svg = (f'<svg class="art dg flowchart" viewBox="0 0 {WIDTH} {height:.0f}" width="{WIDTH}" role="img" aria-label="{aria}">'
           + "".join(parts) + "</svg>")
    return svg, warnings
