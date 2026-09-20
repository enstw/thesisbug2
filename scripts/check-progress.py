#!/usr/bin/env python3
"""Keep a unit's status files small enough to be worth reading every session.

    ./fw check-progress [<unit>]           # exit 1 when a status file has turned into a log
    ./fw check-progress [<unit>] --sweep   # move finished and dated entries to CHANGELOG.md
    ./fw check-progress [<unit>] --log "one line"   # record a milestone in CHANGELOG.md

Every agent session starts by reading the unit's PROGRESS.md and DECISIONS.md.
Whatever sits in them is paid for in context on every session, and — worse —
is believed: a "current stage" paragraph from two months ago reads exactly like
a current one. Left alone, a status file grows by one proud paragraph per
session until the live to-do list is a few lines buried under history. A rule
asking agents not to do that does not hold; a gate does, the same way the bib
ratchet does. So each file has a contract this command checks:

  PROGRESS.md    where the unit is now, what is open, what it is waiting on.
                 No finished items, no dated entries, no paragraphs.
  DECISIONS.md   the rules in force — requirements and standing decisions —
                 each as the rule plus its reason. A superseded decision is
                 removed, not annotated: the file answers "what applies now".
  CHANGELOG.md   everything else. Never read at session start; grep it when a
                 task needs the history. Not checked — it may grow.

The narrative of a working session belongs in its commit messages, which git
already stores, dates, and scopes. CHANGELOG.md takes one line per milestone.

What counts as a violation (each has a reason):
  · over the size budget ............ it no longer gets read carefully
  · a line over MAX_LINE characters .. that is a paragraph, i.e. narrative
  · a checked item `- [x]` ........... finished work is history
  · a line that starts with a date ... that is a log entry

`./fw build` runs this check and refuses to build on a violation (override once
with --no-progress-gate), so the files cannot drift back between cleanups.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _paths import course_root, rel, resolve_unit  # noqa: E402

BUDGET = {"PROGRESS.md": 6_000, "DECISIONS.md": 9_000}    # bytes; CJK is 3 bytes a character
MAX_LINE = 320
DONE = re.compile(r"^\s*[-*]\s*\[[xX]\]")
DATED = re.compile(r"^\s*[-*]\s*(\*\*)?\[?(19|20)\d\d-\d\d-\d\d")
CHANGELOG_HEAD = ("# 變更紀錄\n\n> **不到必要不讀取。** 這是歷程，不是規則，也不是現況。"
                  "要追溯時用 `grep` 查關鍵字，不要整份讀進 context。\n\n（新→舊）\n\n")


def violations(path: Path) -> list[str]:
    out = []
    data = path.read_bytes()
    budget = BUDGET[path.name]
    if len(data) > budget:
        out.append(f"{len(data):,} bytes, budget {budget:,} — move history to CHANGELOG.md, "
                   "or split a rule's long rationale into the file it governs")
    fence = False
    for n, line in enumerate(data.decode("utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            fence = not fence
        if fence:
            continue
        if DONE.match(line):
            out.append(f"line {n}: finished item — history, not status")
        elif path.name == "PROGRESS.md" and DATED.match(line):
            out.append(f"line {n}: dated entry — a log line, not status")
        if len(line) > MAX_LINE:
            out.append(f"line {n}: {len(line)} characters — a paragraph; state the fact, "
                       "put the story in the commit message")
    return out


def prepend_changelog(unit: Path, entries: list[str]) -> None:
    f = unit / "CHANGELOG.md"
    text = f.read_text(encoding="utf-8") if f.is_file() else CHANGELOG_HEAD
    marker = "（新→舊）\n\n"
    block = "".join(e.rstrip("\n") + "\n" for e in entries)
    if marker in text:
        text = text.replace(marker, marker + block, 1)
    else:
        text = text.rstrip("\n") + "\n\n" + block
    f.write_text(text, encoding="utf-8")


def sweep(unit: Path) -> int:
    """Move finished and dated lines out of PROGRESS.md, verbatim, under today's date."""
    f = unit / "PROGRESS.md"
    if not f.is_file():
        return 0
    today = dt.date.today().isoformat()
    keep, moved = [], []
    for line in f.read_text(encoding="utf-8").splitlines(keepends=True):
        if DONE.match(line) or DATED.match(line):
            body = re.sub(r"^\s*[-*]\s*(\[[xX]\]\s*)?", "", line).rstrip("\n")
            moved.append(f"- {today} - （自 PROGRESS.md 移入）{body}")
        else:
            keep.append(line)
    if moved:
        f.write_text("".join(keep), encoding="utf-8")
        prepend_changelog(unit, moved)
    return len(moved)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("unit", nargs="?")
    ap.add_argument("--sweep", action="store_true",
                    help="move finished and dated lines from PROGRESS.md into CHANGELOG.md")
    ap.add_argument("--log", metavar="TEXT", help="add one dated milestone line to CHANGELOG.md")
    a = ap.parse_args()
    root, unit = course_root(), resolve_unit(a.unit)

    if a.log:
        prepend_changelog(unit, [f"- {dt.date.today().isoformat()} - {a.log.strip()}"])
        print(f"logged to {rel(unit / 'CHANGELOG.md', root)}")
        return
    if a.sweep:
        print(f"swept {sweep(unit)} line(s) from PROGRESS.md into CHANGELOG.md")

    bad = 0
    for name in BUDGET:
        f = unit / name
        if not f.is_file():
            continue
        v = violations(f)
        size = len(f.read_bytes())
        print(f"{rel(f, root)}: {size:,}/{BUDGET[name]:,} bytes — " + ("OK" if not v else f"{len(v)} problem(s)"))
        for line in v:
            print("  · " + line)
        bad += len(v)
    if bad:
        sys.exit("\nstatus files have turned into a log. Finished work: delete the line and run "
                 "./fw check-progress --log \"…\" (or --sweep). A rule that changed: rewrite it in "
                 "DECISIONS.md and drop the old wording. The story of how: the commit message.")


if __name__ == "__main__":
    main()
