"""The pipeline step map a storyboard declares: premise `流程步驟`, the 環節 column, and the strip each slide shows.

A course whose talks walk through one pipeline (read data → features → model → … → submit)
declares the steps once in 前提 and marks per row which step the slide changes or explains,
because an audience that hears "S4" cannot recall which stage that was, and a teacher
reading weekly decks could not tell where in the pipeline each change sat.

- `流程步驟：S1 讀取資料、S2 攤平、…、保留（圖：@fig-x）`: a step's key is its first word,
  which the 環節 column cites; its on-slide name is the first two characters of the rest
  (讀取資料 → 讀取), or of the key when there is no rest (保留).
- `小地圖：讀取、攤平、…` overrides those names in the same order, for a step whose name does
  not cut to two characters.
- 環節 `改：S3、保留；講：S6` fills S3 and 保留 (this slide's numbers come from changing them)
  and outlines S6 (explained, not changed); `—` puts no strip on the slide.

storyboard-review draws the slide × step table from the same functions, so the review page
and the deck cannot disagree. Standard library only.
"""

from __future__ import annotations

import html
import re


def section(md: str, title: str) -> str:
    m = re.search(rf"^## {re.escape(title)}\s*\n(.*?)(?=^## |\Z)", md, re.S | re.M)
    return m.group(1) if m else ""


def premise_value(md: str, key: str) -> str | None:
    m = re.search(rf"^- (?:\*\*)?{key}(?:\*\*)?\s*[：:]\s*(.+)$", section(md, "前提"), re.M)
    return m.group(1).strip() if m else None


def _items(val: str) -> list[str]:
    val = re.sub(r"[（(]圖[：:].*?[）)]", "", val)
    return [item.strip() for item in re.split("[、，,]", val) if item.split()]


def steps_decl(md: str) -> tuple[list[str], str | None]:
    """`流程步驟：S1 讀取資料、S2 攤平、保留（圖：@fig-x）` → (['S1', 'S2', '保留'], 'fig-x').
    A step's key is its first word, which is what the 環節 column cites."""
    val = premise_value(md, "流程步驟")
    if not val:
        return [], None
    fig = re.search(r"[（(]圖[：:]\s*@?([\w-]+)[）)]", val)
    return [item.split()[0] for item in _items(val)], fig.group(1) if fig else None


def step_names(md: str) -> dict[str, str]:
    """Key → the two-character name a slide shows (S1 讀取資料 → 讀取), or 小地圖's override."""
    val = premise_value(md, "流程步驟")
    if not val:
        return {}
    items = _items(val)
    keys = [it.split()[0] for it in items]
    names = [(it.split(maxsplit=1)[1] if len(it.split()) > 1 else it)[:2] for it in items]
    override = premise_value(md, "小地圖")
    if override:
        given = _items(override)
        if len(given) == len(keys):
            names = given
    return dict(zip(keys, names))


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


NO_MAP = {"—", "-", "–", "無", "none"}


def strip_html(cell: str, names: dict[str, str]) -> str:
    """The top-bar strip for one row: one cell per step, filled (改) or outlined (講)."""
    if not names or cell.strip() in NO_MAP:
        return ""
    marks = steps_of(cell, list(names))
    cells = "".join(
        f'<span class="pcell{" " + marks[k] if k in marks else ""}">{html.escape(n)}</span>'
        for k, n in names.items())
    return f'<span class="pmap" aria-label="流程地圖">{cells}</span>'
