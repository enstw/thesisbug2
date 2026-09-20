#!/usr/bin/env python3
"""Write to, and query, a unit's CHANGELOG.md without reading it.

    ./fw log [<unit>] "ch5 初稿完成，6,900 字"     add one dated milestone line
    ./fw log [<unit>] --list [N]                   table of contents: id · date · title
    ./fw log [<unit>] --find <keyword>...          matching entries as id · date · title + a short snippet
    ./fw log [<unit>] --show <id>                  one entry in full

CHANGELOG.md is history, and history is never read at session start. But a
plain `grep` over it is not a cheap query either: an entry can be a single line
of several thousand characters, so one hit returns kilobytes and a common
keyword returns most of the file. What costs context is the size of the
*answer*, not the scan. So querying goes in three steps, each as small as it
can be: `--list` or `--find` to locate (one line plus a snippet per entry),
then `--show` for the one entry that matters.

`--find` takes several keywords (all must match, case-insensitive) and also
lists matching commit subjects from the unit's git history, because the full
story of a change lives in its commit message — `git show <hash>` reads one.

Writing is the other half: `./fw log "…"` is the cheap, correct place for
"what just got done", so it does not get written into PROGRESS.md instead.
One line per milestone.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _paths import course_root, list_units, rel, resolve_unit  # noqa: E402

ENTRY = re.compile(r"^\s*[-*]\s*\[?((?:19|20)\d\d-\d\d-\d\d)\]?\s*[-–—:：]?\s*(.*)$")
SNIPPET = 60          # characters of context on each side of a hit
MAX_HITS = 12


def entries(unit: Path) -> list[tuple[str, str]]:
    """(date, text) per entry, file order. Undated lines join an 'archive' pseudo-date."""
    f = unit / "CHANGELOG.md"
    if not f.is_file():
        sys.exit(f"no CHANGELOG.md in {unit.name}")
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        m = ENTRY.match(line)
        if m:
            out.append((m.group(1), m.group(2).strip()))
        elif line.strip() and not line.startswith((">", "#", "（", "---", "<!--")):
            out.append(("(undated)", line.strip()))
    return out


def title(text: str, width: int = 72) -> str:
    m = re.match(r"\*\*(.+?)\*\*", text)
    t = (m.group(1) if m else text).strip()
    return t if len(t) <= width else t[:width - 1] + "…"


def snippet(text: str, kw: str) -> str:
    i = text.lower().find(kw.lower())
    a, b = max(0, i - SNIPPET), min(len(text), i + len(kw) + SNIPPET)
    return ("…" if a else "") + text[a:b].replace("\n", " ") + ("…" if b < len(text) else "")


def split_unit(args: list[str]) -> tuple[str | None, list[str]]:
    """A leading argument is the unit when it names one; otherwise everything is payload."""
    if args and not args[0].startswith("-"):
        root = course_root()
        names = {u.name for u in list_units(root)}
        a = args[0]
        if a in names or (root / a / "WORK.json").is_file() or Path(a, "WORK.json").is_file() \
                or sum(n.endswith("-" + a) for n in names) == 1:
            return a, args[1:]
    return None, args


def main() -> None:
    raw = sys.argv[1:]
    if not raw or raw[0] in ("-h", "--help"):
        sys.exit(__doc__.strip())
    unit_arg, rest = split_unit(raw)
    ap = argparse.ArgumentParser(prog="fw log", add_help=False)
    ap.add_argument("--list", nargs="?", const=20, type=int, metavar="N")
    ap.add_argument("--find", nargs="+", metavar="KEYWORD")
    ap.add_argument("--show", type=int, metavar="ID")
    ap.add_argument("text", nargs="?")
    a = ap.parse_args(rest)
    root, unit = course_root(), resolve_unit(unit_arg)

    if a.text and not (a.list or a.find or a.show is not None):
        sys.exit(subprocess.run([sys.executable, str(HERE / "check-progress.py"), str(unit),
                                 "--log", a.text]).returncode)

    es = entries(unit)
    if a.show is not None:
        if not 1 <= a.show <= len(es):
            sys.exit(f"no entry {a.show}; there are {len(es)}")
        d, t = es[a.show - 1]
        print(f"[{a.show}] {d}\n{t}")
        return
    if a.list:
        for n, (d, t) in list(enumerate(es, 1))[:a.list]:
            print(f"[{n:>3}] {d}  {title(t)}   ({len(t):,} chars)")
        if len(es) > a.list:
            print(f"… {len(es) - a.list} older — ./fw log --list {len(es)}")
        return

    kws = a.find or []
    hits = [(n, d, t) for n, (d, t) in enumerate(es, 1) if all(k.lower() in t.lower() for k in kws)]
    print(f"{len(hits)} of {len(es)} entries match {' + '.join(kws)}  ({rel(unit / 'CHANGELOG.md', root)})")
    for n, d, t in hits[:MAX_HITS]:
        print(f"[{n:>3}] {d}  {title(t, 60)}\n        {snippet(t, kws[0])}")
    if len(hits) > MAX_HITS:
        print(f"… {len(hits) - MAX_HITS} more — add a keyword to narrow")
    if hits:
        print("→ full entry: ./fw log --show <id>")
    g = subprocess.run(["git", "-C", str(root), "log", "-i", "--all-match", *[f"--grep={k}" for k in kws],
                        "--format=%h %ad %s", "--date=short", "-n", "8", "--", str(unit)],
                       capture_output=True, text=True).stdout.strip()
    if g:
        print("\ncommits touching this unit whose message matches (git show <hash> for the story):")
        print("\n".join("  " + line[:150] for line in g.splitlines()))


if __name__ == "__main__":
    main()
