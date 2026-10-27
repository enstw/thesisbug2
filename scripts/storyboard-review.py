#!/usr/bin/env python3
"""Render a talk's storyboard as one HTML page for the author's (and a teacher's) review.

    ./fw storyboard-review [<talk-or-unit>]          write <talk>/_output/storyboard.html
    ./fw storyboard-review [<talk-or-unit>] --open   …and open it in the default browser

A Markdown table with ten columns is hard to review: rows wrap into walls of
text and the premises, the points and the layouts live in other files. This
page puts everything the sign-off needs on one scrollable page, each part read
from the file that owns it, so nothing here is a second copy to keep in sync:

    審閱說明     the storyboard's opening comment
    待選         the 〈待選〉 section as radio choices; a button copies the picks
                 as one line the author pastes back to the agent
    流程地圖     optional: the Model's diagram named by the premise bullet
                 `流程步驟：S1 讀取資料、S2 …（圖：@fig-label）`, a slide × step table
                 from the 環節 column (`改：S3、S5；講：S6`), and a course table
                 named by `流程對照：<path> § <heading>｜<column prefix>`
    前提         the premise bullets
    簡報風格     the talk's palette (asset/tokens.css, else house-style) and the
                 content shapes the storyboard uses (deck-plan content-shapes.md)
    投影片       one card per row: a preview (the real slide for a layout-catalog
                 code, a structural sketch for a legacy class), the step strip,
                 every column, formulas (公式 column, $…$, typeset by KaTeX) and
                 the cited points' text
    論點         every point in points.md with the slides that cite it

The page is a build product under the git-ignored _output/; edit the
storyboard (or points, Model) and run this again. Standard library only; KaTeX
and Mermaid load from jsDelivr at pinned versions, so offline the formulas and
the diagram show as source.
"""

from __future__ import annotations

import argparse
import html
import importlib.util
import os
import re
import sys
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _deck import SKILLS  # noqa: E402
from _deck_catalog import VisualRhythmResolver  # noqa: E402
from _paths import (course_root, find_talk, included_files, manuscript_files, rel,  # noqa: E402
                    resolve_unit, talk_model_files)

_spec = importlib.util.spec_from_file_location("deck_compile", HERE / "deck-compile.py")
deck_compile = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(deck_compile)

KATEX = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist"
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"
HOUSE_TOKENS = SKILLS / "house-style" / "assets" / "css" / "tokens.css"
DECK_CSS = SKILLS / "deck-svg" / "template" / "asset" / "deck.css"
SHAPES = SKILLS / "deck-plan" / "reference" / "content-shapes.md"

CSS = """
:root { --bg:#fbfaf7; --card:#ffffff; --ink:#1f2328; --mute:#5f6670; --line:#e3e0d8;
  --accent:#2f6f8f; --chip:#eef3f6; --warn:#a4501b; --backup:#f4f1ea;
  --chg:#f0a43a; --chg-bg:#fdebd0; --say:#3b82c4; }
@media (prefers-color-scheme: dark) { :root { --bg:#16181b; --card:#1f2226; --ink:#e6e6e3; --mute:#9aa1a9;
  --line:#33373d; --accent:#7fb6d4; --chip:#26313a; --warn:#e3995f; --backup:#1b1d20; --chg-bg:#4a3413; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
  font:17px/1.75 "PingFang TC","Noto Sans TC","Heiti TC",system-ui,sans-serif; }
main { max-width:1040px; margin:0 auto; padding:32px 16px 80px; }
h1 { font-size:28px; margin:0 0 4px; }
.sub { color:var(--mute); margin:0 0 20px; font-size:15px; }
h2 { font-size:21px; margin:44px 0 12px; padding-bottom:6px; border-bottom:1px solid var(--line); scroll-margin-top:52px; }
h3 { font-size:17px; margin:24px 0 8px; }
p.note { color:var(--mute); font-size:15px; margin:4px 0 10px; }
ul.premise { padding-left:1.2em; } ul.premise li { margin:6px 0; }
code { font:0.88em ui-monospace,"SF Mono",Menlo,monospace; background:var(--chip); padding:1px 5px; border-radius:4px; }
nav.toc { position:sticky; top:0; z-index:5; background:var(--bg); padding:8px 0; border-bottom:1px solid var(--line);
  display:flex; flex-wrap:wrap; gap:6px; }
nav.toc a { text-decoration:none; color:var(--accent); background:var(--chip); border-radius:6px; padding:1px 9px; font-size:14px; }
nav.toc a.sec { background:none; font-weight:600; }
.scroll { overflow-x:auto; }
table { border-collapse:collapse; font-size:14.5px; line-height:1.55; }
th, td { border:1px solid var(--line); padding:6px 8px; vertical-align:top; text-align:left; }
th { background:var(--chip); font-weight:600; }
table.grid td, table.grid th { text-align:center; white-space:nowrap; padding:4px 8px; }
table.grid td:nth-child(2) { text-align:left; white-space:normal; min-width:12em; }
td.chg { background:var(--chg-bg); color:var(--warn); font-weight:700; }
td.say { box-shadow:inset 0 0 0 2px var(--say); color:var(--say); font-weight:600; }
.mermaid { background:#fff; border:1px solid var(--line); border-radius:8px; padding:12px; overflow-x:auto; }
.swatches { display:flex; flex-wrap:wrap; gap:10px; }
.sw { width:112px; font-size:12.5px; color:var(--mute); }
.sw i { display:block; height:42px; border-radius:6px; border:1px solid var(--line); margin-bottom:4px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:18px 20px; margin:18px 0;
  scroll-margin-top:52px; }
.card.backup { background:var(--backup); }
.head { display:flex; flex-wrap:wrap; align-items:center; gap:8px 12px; margin-bottom:12px; }
.num { font-size:22px; font-weight:700; color:var(--accent); min-width:2.2em; }
.chip { font-size:13px; color:var(--mute); background:var(--chip); border-radius:5px; padding:1px 8px; }
.chip.tag { color:var(--warn); }
.top { display:grid; grid-template-columns:320px 1fr; gap:16px; margin-bottom:12px; }
.preview { width:320px; height:180px; border-radius:6px; overflow:hidden; position:relative; background:#000; }
.preview iframe { width:1920px; height:1080px; border:0; transform:scale(.16667); transform-origin:0 0; pointer-events:none; }
.preview svg { width:320px; height:180px; display:block; }
.top small { color:var(--mute); font-size:12px; }
.strip { display:flex; flex-wrap:wrap; gap:4px; margin:2px 0 8px; }
.strip span { font-size:12.5px; padding:0 7px; border-radius:4px; border:1px solid var(--line); color:var(--mute); }
.strip span.chg { background:var(--chg-bg); border-color:var(--chg); color:var(--warn); font-weight:700; }
.strip span.say { border:2px solid var(--say); color:var(--say); font-weight:600; }
dl { display:grid; grid-template-columns:6.5em 1fr; gap:6px 14px; margin:0; }
dt { color:var(--mute); font-size:14px; padding-top:3px; }
dd { margin:0; }
dd.formula { background:var(--chip); border-radius:6px; padding:6px 10px; overflow-x:auto; }
details { margin-top:12px; border-top:1px dashed var(--line); padding-top:8px; }
summary { cursor:pointer; color:var(--accent); font-size:14px; }
.point { font-size:15px; margin:8px 0 0; }
.point b { color:var(--accent); }
.point .refs { color:var(--mute); font-size:13px; }
.point.unused b { color:var(--warn); }
.todo { color:var(--warn); font-weight:600; }
fieldset.q { border:1px solid var(--line); border-radius:10px; background:var(--card); margin:12px 0; padding:10px 16px 12px; }
fieldset.q legend { font-weight:600; padding:0 6px; }
label.opt { display:block; padding:5px 6px; border-radius:6px; cursor:pointer; }
label.opt:hover { background:var(--chip); }
label.opt input[type=radio] { margin-right:8px; }
label.opt b { color:var(--accent); margin-right:4px; }
input.free { font:inherit; width:min(560px,70%); padding:2px 6px; border:1px solid var(--line); border-radius:5px;
  background:var(--bg); color:var(--ink); }
button#copy { font:inherit; padding:6px 16px; border-radius:7px; border:1px solid var(--accent); background:var(--accent);
  color:#fff; cursor:pointer; }
textarea#picked { width:100%; font:14px/1.6 inherit; border:1px solid var(--line); border-radius:6px; background:var(--chip);
  color:var(--ink); padding:6px 8px; }
@media (max-width:760px) { .top { grid-template-columns:1fr; } dl { grid-template-columns:1fr; } dt { padding-top:8px; } }
"""

# The picks live only in this viewer's browser (localStorage, guarded): the
# page is a local file the agent cannot read back, so the copy button is the
# hand-off and storage only spares the author re-clicking after a rebuild.
JS = """
(function () {
  var qs = Array.prototype.slice.call(document.querySelectorAll('fieldset.q'));
  if (!qs.length) return;
  var KEY = 'storyboard-review:' + location.pathname;
  function load() { try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { return {}; } }
  function save(v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) {} }
  var st = load();
  qs.forEach(function (f, i) {
    var s = st[f.dataset.q];
    if (!s) return;
    var r = f.querySelector('input[type=radio][value="' + s.v + '"]'); if (r) r.checked = true;
    if (s.t) f.querySelector('.free').value = s.t;
  });
  function text() {
    var out = [], v = {};
    qs.forEach(function (f) {
      var r = f.querySelector('input[type=radio]:checked'), t = f.querySelector('.free').value.trim();
      v[f.dataset.q] = { v: r ? r.value : '', t: t };
      out.push(f.dataset.q + '：' + (r ? (r.value === '其他' ? '其他「' + t + '」' : r.value) : '未選'));
    });
    save(v);
    return out.join('；');
  }
  var ta = document.getElementById('picked');
  function show() { ta.value = text(); }
  document.addEventListener('change', show); document.addEventListener('input', show); show();
  document.getElementById('copy').addEventListener('click', function () {
    show(); ta.select();
    var done = function () { document.getElementById('copied').textContent = '已複製'; };
    if (navigator.clipboard) navigator.clipboard.writeText(ta.value).then(done, function () { document.execCommand('copy'); done(); });
    else { document.execCommand('copy'); done(); }
  });
})();
"""


def inline(s: str) -> str:
    """Storyboard cells use `code`, **bold** and $math$. Code is split out first,
    because `p ** 2` inside code is a power, not bold; math is left for KaTeX."""
    out = []
    for part in re.split(r"(`[^`]+`)", s):
        if len(part) > 1 and part.startswith("`") and part.endswith("`"):
            out.append(f"<code>{html.escape(part[1:-1], quote=False)}</code>")
        else:
            part = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(part, quote=False))
            out.append(re.sub(r"(待作者定)", r'<span class="todo">\1</span>', part).replace("&lt;br&gt;", "<br>"))
    return "".join(out)


def plain(s: str, n: int | None = None) -> str:
    s = "".join(p[1:-1] if len(p) > 1 and p.startswith("`") and p.endswith("`")
                else re.sub(r"\*\*(.+?)\*\*", r"\1", p).replace("<br>", " ")
                for p in re.split(r"(`[^`]+`)", s))
    return html.escape(s if n is None or len(s) <= n else s[:n] + "…", quote=False)


def section(md: str, title: str) -> str:
    m = re.search(rf"^## {re.escape(title)}\s*\n(.*?)(?=^## |\Z)", md, re.S | re.M)
    return m.group(1) if m else ""


def md_table(text: str) -> tuple[list[str], list[list[str]]]:
    rows = [ln for ln in text.splitlines() if ln.startswith("|")]
    if len(rows) < 2:
        return [], []
    split = lambda r: [c.strip() for c in r.strip().strip("|").split("|")]  # noqa: E731
    return split(rows[0]), [split(r) for r in rows[2:]]


def html_table(header: list[str], rows: list[list[str]], cls: str = "") -> str:
    th = "".join(f"<th>{inline(h)}</th>" for h in header)
    tr = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="scroll"><table class="{cls}"><tr>{th}</tr>{tr}</table></div>'


def premise_value(md: str, key: str) -> str | None:
    m = re.search(rf"^- (?:\*\*)?{key}(?:\*\*)?\s*[：:]\s*(.+)$", section(md, "前提"), re.M)
    return m.group(1).strip() if m else None


def steps_decl(md: str) -> tuple[list[str], str | None]:
    """`流程步驟：S1 讀取資料、S2 攤平、保留（圖：@fig-x）` → (['S1', 'S2', '保留'], 'fig-x').
    A step's key is its first word, which is what the 環節 column cites."""
    val = premise_value(md, "流程步驟")
    if not val:
        return [], None
    fig = re.search(r"[（(]圖[：:]\s*@?([\w-]+)[）)]", val)
    val = re.sub(r"[（(]圖[：:].*?[）)]", "", val)
    keys = [item.split()[0] for item in re.split("[、，,]", val) if item.split()]
    return keys, fig.group(1) if fig else None


def steps_of(cell: str, keys: list[str]) -> dict[str, str]:
    """「改：S3、保留；講：S6」→ {'S3': 'chg', '保留': 'chg', 'S6': 'say'}."""
    out: dict[str, str] = {}
    for part in re.split("[；;]", cell):
        m = re.match(r"\s*(改|講)\s*[：:](.*)", part)
        if m:
            for s in re.split("[、，, ＋+]", m.group(2)):
                if s.strip() in keys:
                    out[s.strip()] = "chg" if m.group(1) == "改" else "say"
    return out


def model_files(unit: Path, talk: Path) -> list[Path]:
    if (talk / "talk.json").is_file() or (talk == unit and (talk / "deck.html").is_file()):
        try:
            files = talk_model_files(unit, talk)
            return [g for f in files for g in (f, *included_files(f, unit))]
        except SystemExit:
            pass
    return manuscript_files(unit)


def model_diagram(files: list[Path], label: str) -> tuple[str, str] | None:
    """The Mermaid source and caption of the Model diagram with this label."""
    for f in files:
        for m in re.finditer(r"```\{mermaid\}\n(.*?)```", f.read_text(encoding="utf-8"), re.S):
            if re.search(rf"%%\|\s*label:\s*{re.escape(label)}\s*$", m.group(1), re.M):
                cap = re.search(r'%%\|\s*fig-cap:\s*"(.*)"', m.group(1))
                src = "\n".join(ln for ln in m.group(1).splitlines() if not ln.startswith("%%|"))
                return src, cap.group(1) if cap else ""
    return None


def crosswalk(md: str, root: Path) -> tuple[str, list[str], list[list[str]]] | None:
    """`流程對照：notes/map.md § 矩陣｜第 5 週` → the first column plus the columns
    whose header starts with the prefix, from that table in a course file."""
    val = premise_value(md, "流程對照")
    m = re.match(r"`?([^`§]+?)`?\s*§\s*(.+?)\s*[｜|]\s*(.+)$", val or "")
    if not m:
        return None
    path = (root / m.group(1).strip()).resolve()
    if not path.is_file() or not path.is_relative_to(root.resolve()):
        return None
    head, rows = md_table(section(path.read_text(encoding="utf-8"), m.group(2).strip()))
    idx = [0] + [i for i, h in enumerate(head) if i and h.startswith(m.group(3).strip())]
    if len(idx) == 1:
        return None
    return (m.group(1).strip(), [head[i] for i in idx],
            [[r[i] for i in idx] for r in rows if len(r) == len(head)])


def tokens(talk: Path) -> tuple[dict[str, str], Path]:
    f = talk / "asset" / "tokens.css"
    f = f if f.is_file() else HOUSE_TOKENS
    root = re.search(r":root\s*\{(.*?)\}", f.read_text(encoding="utf-8"), re.S)
    return (dict(re.findall(r"--([\w-]+):\s*([^;]+);", root.group(1))) if root else {}), f


def sketch(layout: str, shape: str, tok: dict[str, str]) -> str:
    """A structural sketch of a legacy-class layout (16:9, deck colours); a
    catalog code gets the real slide instead."""
    bg, fg, mu, ac = (tok.get(k, d).strip() for k, d in
                      (("ink", "#06080f"), ("text", "#f3f5fa"), ("muted", "#8b93a7"), ("accent", "#e7ad46")))

    def r(x, y, w, h, c, o=1, rx=2):
        return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{c}" opacity="{o}"/>'

    g = [r(0, 0, 192, 108, bg, 1, 0)]
    if "hero" in layout:
        return "".join(g + [r(30, 38, 132, 12, fg), r(46, 56, 100, 6, mu), r(70, 80, 52, 4, ac)])
    if "finale" in layout:
        return "".join(g + [r(24, 46, 144, 10, fg), r(60, 64, 72, 4, mu)])
    g += [r(10, 8, 24, 3, ac), r(10, 14, 110, 7, fg)]
    y0, y1 = 28, 92
    if re.search(r"claim|verdict|lead", layout):
        g.append(r(10, 96, 172, 5, ac, .9))
    if "stats" in layout:
        n = 4 if "four" in layout else 3
        w = (172 - (n - 1) * 6) / n
        for i in range(n):
            x = 10 + i * (w + 6)
            g += [r(x, y0 + 6, w, 46, fg, .08), r(x + 6, y0 + 16, w - 12, 12, ac), r(x + 6, y0 + 34, w - 16, 4, mu)]
        g.append(r(10, 84, 120, 4, mu))
    elif "walk" in layout:
        for i in range(3):
            g += [r(10, y0 + 4 + i * 16, 3, 10, ac), r(16, y0 + 5 + i * 16, 80, 8, fg, .25),
                  r(102, y0 + 7 + i * 16, 60, 4, mu)]
    elif "table" in layout or "matrix" in layout:
        m = re.search(r"(\d+)\s*列\s*[×x]\s*(\d+)\s*欄", layout)
        nr, nc = (int(m.group(1)), int(m.group(2))) if m else (4, 3)
        h = (y1 - y0 - 4) / (nr + 1)
        x0 = 30 if "matrix" in layout else 10
        w = (182 - x0) / nc
        for i in range(nr + 1):
            for j in range(nc):
                g.append(r(x0 + j * w + 1, y0 + i * h + 1, w - 2, h - 2, fg if i == 0 else mu, .35 if i == 0 else .14, 1))
        if "matrix" in layout:
            g.append(r(10, y0, 4, y1 - y0 - 4, ac, .7))
    elif "cols" in layout or "grid.two" in layout:
        for x in (10, 100):
            g += [r(x, y0 + 2, 82, 56, fg, .08), r(x + 6, y0 + 8, 50, 6, fg, .8)]
            g += ([r(x + 8, y0 + 20, 66, 30, ac, .25)] if "svg" in layout
                  else [r(x + 6, y0 + 20 + k * 9, 66, 4, mu) for k in range(4)])
    elif "svg" in layout:
        if "折線" in shape or "line" in shape.lower():
            pts = " ".join(f"{14 + i * 40},{y1 - 8 - (i * 9) % 38}" for i in range(5))
            g += [f'<polyline points="{pts}" fill="none" stroke="{ac}" stroke-width="2"/>', r(12, y1 - 6, 168, 1, mu)]
        else:
            for i in range(4):
                for k, o in ((0, 1), (1, .5)):
                    hh = 22 + i * 9 + k * 2
                    g.append(r(20 + i * 42 + k * 13, y1 - 4 - hh, 11, hh, ac, o, 1))
    else:
        g.append(r(10, y0 + 10, 172, 40, fg, .1))
    return "".join(g)


def preview(row: dict[str, str], idx: int, total: int, resolver: VisualRhythmResolver,
            css_hrefs: list[str], tok: dict[str, str], talk: Path | None = None) -> tuple[str, str]:
    """(preview html, caption): the compiled slide when 版型 is a catalog code."""
    rendered, _ = deck_compile.render_row(row, idx, total, resolver, talk)
    if rendered:
        rendered = re.sub(r'<section\b', '<section data-deck-active=""', rendered, count=1)
        doc = ("<!doctype html><html><head><meta charset='utf-8'>"
               + "".join(f"<link rel='stylesheet' href='{h}'>" for h in css_hrefs)
               + "<style>html,body{margin:0;width:1920px;height:1080px;overflow:hidden;background:var(--ink)}"
               ".slide{position:absolute;inset:0;width:1920px;height:1080px}</style></head>"
               f"<body>{rendered}</body></html>")
        return (f'<div class="preview"><iframe loading="lazy" srcdoc="{html.escape(doc)}"></iframe></div>',
                "版型預覽：deck-compile 會畫出的投影片")
    svg = sketch(row.get("版型", ""), row.get("內容形狀", ""), tok)
    return f'<div class="preview"><svg viewBox="0 0 192 108">{svg}</svg></div>', "版型示意：只畫結構，不是實際畫面"


def choices(md: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """〈待選〉: a top-level bullet is a question, indented `- A …` bullets are its options."""
    qs: list[list] = []
    for ln in section(md, "待選").splitlines():
        if ln.startswith("- "):
            qs.append([ln[2:].strip(), []])
        elif qs and (m := re.match(r"\s+- ([A-Z])\s+(.*)", ln)):
            qs[-1][1].append((m.group(1), m.group(2)))
    return [(q, o) for q, o in qs if o]


def points(talk: Path) -> dict[str, str]:
    f = talk / "points.md"
    out: dict[str, str] = {}
    if f.is_file():
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"- \*\*(P\d+)\*\*(.*)", line)
            if m:
                out[m.group(1)] = m.group(2).strip()
    return out


def shapes_doc() -> dict[str, list[str]]:
    if not SHAPES.is_file():
        return {}
    _, rows = md_table(section(SHAPES.read_text(encoding="utf-8"), "Catalogue"))
    return {r[0]: r for r in rows if r and r[0].isdigit()}


def build(unit: Path, talk: Path, root: Path) -> tuple[Path, int]:
    md = (talk / "storyboard.md").read_text(encoding="utf-8")
    out = talk / "_output" / "storyboard.html"
    title = (re.search(r"^# (.+)", md, re.M) or [None, "分鏡稿"])[1]
    rows = deck_compile.extract_storyboard_rows(md)
    header = md_table(section(md, "投影片"))[0] or (list(rows[0]) if rows else [])
    pts, (tok, tokfile) = points(talk), tokens(talk)
    keys, fig = steps_decl(md)
    qs = choices(md)
    cited: dict[str, list[str]] = {}
    for s in rows:
        for p in re.findall(r"P\d+", s.get("來源論點", "")):
            cited.setdefault(p, []).append(s["#"])

    nav = (('<a class="sec" href="#choose">待選</a>' if qs else "")
           + ('<a class="sec" href="#map">流程地圖</a>' if keys else "")
           + '<a class="sec" href="#premise">前提</a><a class="sec" href="#style">風格</a>'
           + ('<a class="sec" href="#points">論點</a>' if pts else "")
           + "".join(f'<a href="#s{s["#"]}">{s["#"]}</a>' for s in rows))
    body = [f"<h1>{inline(title)}</h1>",
            f'<p class="sub">{html.escape(rel(talk, root))} · {len(rows)} 頁 · 由 ./fw storyboard-review 產生；'
            "改內容請改 storyboard.md（或 points.md、Model）再重產</p>",
            f'<nav class="toc">{nav}</nav>']

    note = re.search(r"<!--(.*?)-->", md, re.S)
    if note:
        body.append("<h2>審閱說明</h2>" + "".join(f'<p class="note">{inline(ln.strip())}</p>'
                                              for ln in note.group(1).strip().splitlines() if ln.strip()))

    if qs:
        blocks = []
        for i, (q, opts) in enumerate(qs):
            rec = re.search(r"建議\s*([A-Z])", q)
            radios = "".join(f'<label class="opt"><input type="radio" name="q{i}" value="{k}"'
                             f'{" checked" if rec and rec.group(1) == k else ""}><b>{k}</b> {inline(t)}</label>'
                             for k, t in opts)
            blocks.append(f'<fieldset class="q" data-q="{plain(re.sub(r"[（(].*", "", q).strip())}">'
                          f"<legend>{inline(q)}</legend>{radios}"
                          f'<label class="opt"><input type="radio" name="q{i}" value="其他">其他：'
                          '<input type="text" class="free" placeholder="寫你的版本"></label></fieldset>')
        body.append('<h2 id="choose">待你選</h2><p class="note">預設勾的是建議。選好按「複製我的選擇」，貼回對話即可；'
                    "選擇只存在這個瀏覽器，重產頁面不會清掉。</p>" + "".join(blocks)
                    + '<p><button id="copy">複製我的選擇</button> <span id="copied" class="note"></span></p>'
                    '<textarea id="picked" readonly rows="3"></textarea>')

    if keys:
        body.append('<h2 id="map">流程地圖：每頁改在哪個環節</h2>')
        diagram = model_diagram(model_files(unit, talk), fig) if fig else None
        if diagram:
            body.append(f'<h3>流程圖（Model 的 @{html.escape(fig)}）</h3><p class="note">{inline(diagram[1])}</p>'
                        f'<pre class="mermaid">{html.escape(diagram[0])}</pre>')
        if "環節" in header:
            trs = "".join(
                f'<tr><td><a href="#s{s["#"]}">{s["#"]}</a></td><td>{plain(s.get("畫面內容", ""), 38)}</td>'
                + "".join(f'<td class="{st.get(k, "")}">{ {"chg": "改", "say": "講"}.get(st.get(k, ""), "") }</td>'
                          for k in keys) + "</tr>"
                for s in rows for st in [steps_of(s.get("環節", ""), keys)])
            body.append('<h3>投影片 × 步驟</h3><p class="note">「改」（橘）＝這頁的數字來自改了這一格；'
                        "「講」（藍框）＝這頁解釋這一格、沒有改。取自分鏡的「環節」欄。</p>"
                        '<div class="scroll"><table class="grid"><tr><th>#</th><th>畫面內容（開頭）</th>'
                        + "".join(f"<th>{html.escape(k)}</th>" for k in keys) + f"</tr>{trs}</table></div>")
        cw = crosswalk(md, root)
        if cw:
            body.append(f"<h3>每一步裝什麼（{html.escape(cw[0])}）</h3>" + html_table(cw[1], cw[2]))

    premise = [inline(ln[2:]) for ln in section(md, "前提").splitlines() if ln.startswith("- ")]
    body.append('<h2 id="premise">前提</h2><ul class="premise">' + "".join(f"<li>{p}</li>" for p in premise) + "</ul>")

    body.append('<h2 id="style">簡報風格</h2>')
    names = [("ink", "底色"), ("ink-2", "底色 2"), ("text", "標題字"), ("body", "內文"), ("muted", "次要字"),
             ("accent", "強調"), ("c1", "章節 1"), ("c2", "章節 2"), ("c3", "章節 3"), ("c4", "章節 4")]
    theme = tok.get("theme-name", "").strip().strip('"')
    body.append(f'<p class="note">預設主題「{html.escape(theme)}」，取自 <code>{html.escape(rel(tokfile, root))}</code>；'
                "畫面 1920×1080；現場按 <code>c</code> 換主題。版型示意也用這組顏色。</p><div class=\"swatches\">"
                + "".join(f'<div class="sw"><i style="background:{tok[k].strip()}"></i>{n}<br><code>{tok[k].strip()}</code></div>'
                          for k, n in names if k in tok) + "</div>")
    doc, used = shapes_doc(), []
    for s in rows:
        n = re.match(r"\d+", s.get("內容形狀", ""))
        if n and n.group() not in used:
            used.append(n.group())
    if doc and used:
        body.append("<h3>本份用到的內容形狀（deck-plan）</h3>"
                    + html_table(["#", "形狀", "用在", "版型"], [doc[n][:4] for n in sorted(used, key=int) if n in doc]))

    deck_css = talk / "asset" / "deck.css"
    css_hrefs = [os.path.relpath(p, out.parent) for p in (tokfile, deck_css if deck_css.is_file() else DECK_CSS)]
    resolver = VisualRhythmResolver(deck_compile.extract_seed(md))
    special = ("#", "內容形狀", "版型", "講", "來源論點", "環節", "公式")
    fields = [k for k in header if k not in special]
    body.append("<h2>投影片</h2>")
    for idx, s in enumerate(rows):
        backup = s.get("講") == "備用"
        chips = [f'<span class="chip">{inline(s.get(k, ""))}</span>' for k in ("內容形狀", "版型")]
        chips += [f'<span class="chip{" tag" if backup else ""}">{inline(s.get("講", ""))}</span>',
                  f'<span class="chip">{inline(s.get("來源論點", ""))}</span>']
        dl = ""
        for k in fields:
            dl += f"<dt>{html.escape(k)}</dt><dd>{inline(s.get(k, ''))}</dd>"
            if k == "畫面內容" and s.get("公式", "—") not in ("", "—"):
                dl += f'<dt>公式</dt><dd class="formula">{inline(s["公式"])}</dd>'
        refs = re.findall(r"P\d+", s.get("來源論點", ""))
        det = ("<details><summary>論點原文（points.md）</summary>"
               + "".join(f'<p class="point"><b>{r}</b> {inline(pts.get(r, "（points.md 沒有這一點）"))}</p>' for r in refs)
               + "</details>") if refs and pts else ""
        pv, cap = preview(s, idx, len(rows), resolver, css_hrefs, tok, talk)
        side = ""
        if keys:
            st = steps_of(s.get("環節", ""), keys)
            side = ("<div><small>環節</small><div class=\"strip\">"
                    + "".join(f'<span class="{st.get(k, "")}">{html.escape(k)}</span>' for k in keys) + "</div></div>"
                    if st else "<div><small>環節：不放地圖</small></div>")
        body.append(f'<section class="card{" backup" if backup else ""}" id="s{s["#"]}">'
                    f'<div class="head"><span class="num">#{s["#"]}</span>{"".join(chips)}</div>'
                    f'<div class="top"><div>{pv}<small>{cap}</small></div>{side}</div>'
                    f"<dl>{dl}</dl>{det}</section>")

    if pts:
        body.append('<h2 id="points">論點（points.md）</h2><p class="note">每點後面是引用它的投影片；橘色編號＝沒有投影片引用。</p>'
                    + "".join(f'<p class="point{"" if p in cited else " unused"}"><b>{p}</b> {inline(t)} '
                              f'<span class="refs">← {"、".join("#" + n for n in cited.get(p, [])) or "未引用"}</span></p>'
                              for p, t in sorted(pts.items(), key=lambda kv: int(kv[0][1:]))))

    page = ('<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{html.escape(title)}｜{html.escape(talk.name)}</title>"
            f'<link rel="stylesheet" href="{KATEX}/katex.min.css"><style>{CSS}</style></head>'
            f'<body><main>{"".join(body)}</main><script>{JS}</script>'
            f'<script defer src="{KATEX}/katex.min.js"></script>'
            f'<script defer src="{KATEX}/contrib/auto-render.min.js" onload="renderMathInElement(document.body,'
            "{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}],"
            "ignoredClasses:['mermaid']})\"></script>"
            + (f'<script src="{MERMAID}"></script><script>mermaid.initialize({{startOnLoad:true,theme:"neutral"}});</script>'
               if keys else "")
            + "</body></html>\n")
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out, len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", nargs="?", help="a talk, or a unit whose storyboard.md sits at its root")
    parser.add_argument("--open", action="store_true", help="open the page in the default browser")
    args = parser.parse_args()
    root = course_root()
    found = find_talk(args.target)
    if found:
        unit, talk = found
    else:
        # A homework unit can carry its storyboard at the root without being a talk.
        unit = talk = resolve_unit(args.target)
    if not (talk / "storyboard.md").is_file():
        sys.exit(f"no storyboard.md in {rel(talk, root)}")
    out, n = build(unit, talk, root)
    print(f"{rel(out, root)}: {n} slides")
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
