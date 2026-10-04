#!/usr/bin/env python3
"""Bring a presentation unit's deck assets up to the current framework.

    ./fw deck-refresh [<unit>] [--dry-run]

A deck copies its engine, look and runtime into <unit>/asset/ when it is
scaffolded, so it opens offline; that also means `./fw update` never reaches
an existing deck. This re-copies exactly the framework-owned files unit-init
copies (the same map, scripts/_deck.py) and prints each as new, updated or
unchanged. Author-owned files — deck.html, storyboard.md, points.md,
draft.qmd, presentation.qmd, notes/, anything else in the unit — are never
written. An asset with uncommitted changes is skipped, because overwriting
it would lose work git cannot give back.

deck.html is the author's, so it is not edited either: when it lacks a
<script>/<link> tag the current starter has (a newly added script does
nothing until it is loaded), the exact tags to add are printed. Exit status
1 when a tag is missing or an asset was skipped. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _deck import deck_assets, missing_tags  # noqa: E402
from _paths import rel, resolve_unit  # noqa: E402


def uncommitted(unit: Path, names: list[str]) -> set[str]:
    """Asset paths git reports as modified; empty outside a git work tree."""
    r = subprocess.run(["git", "-C", str(unit), "status", "--porcelain", "--", *names],
                       capture_output=True, text=True)
    if r.returncode:
        return set()
    top = subprocess.run(["git", "-C", str(unit), "rev-parse", "--show-prefix"],
                         capture_output=True, text=True).stdout.strip()
    out = set()
    for line in r.stdout.splitlines():
        if line[:2].strip() and not line.startswith("??"):
            path = line[3:].strip().strip('"')
            out.add(path[len(top):] if path.startswith(top) else path)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Re-copy the framework-owned deck assets into a presentation unit.")
    ap.add_argument("unit", nargs="?", help="the presentation unit (path or name); default: the current one")
    ap.add_argument("--dry-run", action="store_true", help="show what would change without writing")
    a = ap.parse_args()

    unit = resolve_unit(a.unit)
    work = json.loads((unit / "WORK.json").read_text(encoding="utf-8"))
    if work.get("type") != "presentation":
        sys.exit(f"{rel(unit)} is a {work.get('type', 'unknown')} unit, not a presentation: "
                 "only a presentation unit carries deck assets")
    variant = work.get("variant", "thesis")
    assets = deck_assets()
    missing = [str(src) for src in assets.values() if not src.is_file()]
    if missing:
        sys.exit("framework deck assets missing (incomplete checkout?):\n  " + "\n  ".join(missing))

    dirty = uncommitted(unit, list(assets))
    print(f"{rel(unit)}: deck assets ({'dry run, nothing written' if a.dry_run else 'refreshed'})")
    skipped = updated = 0
    for dst, src in assets.items():
        target = unit / dst
        if not target.exists():
            state = "new"
        elif target.read_bytes() == src.read_bytes():
            print(f"  unchanged  {dst}")
            continue
        elif dst in dirty:
            print(f"  skipped    {dst}  (uncommitted local changes: commit or discard them, then rerun)")
            skipped += 1
            continue
        else:
            state = "updated"
        if not a.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
        print(f"  {state:<9}  {dst}")
        updated += state == "updated"

    deck = unit / "deck.html"
    tags = missing_tags(deck.read_text(encoding="utf-8"), variant) if deck.is_file() else []
    if tags:
        print(f"\ndeck.html does not load everything the current {variant} starter loads. deck.html is "
              "yours, so it was not edited; add these tags (order matters, so each goes right after "
              "the tag named):")
        for tag, after in tags:
            print(f"  {tag}" + (f"\n      after {after}" if after else "\n      before the first asset tag"))
    if updated and not a.dry_run:
        print(f"\nreview with: git diff -- {rel(unit)}/asset   (a committed local edit there was replaced)")
    return 1 if tags or skipped else 0


if __name__ == "__main__":
    sys.exit(main())
