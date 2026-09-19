#!/usr/bin/env python3
"""Create a new unit in a course repo.

    ./fw unit-init --type paper --name final --title "…" --author "…"
                   [--subtitle "…"] [--date YYYY-MM-DD]
                   [--citation apa|apa-zh]          (paper only)
                   [--variant thesis|reading-guide] (presentation only)
                   [--extends <earlier-unit>] [--no-build]

Creates units/NN-<type>-<name>/ (NN = next free number), copies the type's
scaffold into it, writes WORK.json, adds a row to STATUS.md, and — for the
Quarto types — runs one build to prove the unit renders before any writing
starts. It does not commit; the caller does, so the commit message is theirs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRAMEWORK = HERE.parent
sys.path.insert(0, str(HERE))
from _paths import course_root, list_units, rel  # noqa: E402

TYPES = ("preparation", "homework", "paper", "journal", "thesis", "presentation")
CITATION_TYPES = ("preparation", "paper", "journal", "thesis", "presentation")
SKILLS = FRAMEWORK / ".agents" / "skills"
TEMPLATES = FRAMEWORK / "assets" / "templates"
SHARED = FRAMEWORK / "assets" / "scaffold"


def copy_tree(src: Path, dst: Path) -> None:
    for path in src.rglob("*"):
        if path.is_file():
            target = dst / path.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def presentation_files(variant: str) -> dict[str, Path]:
    """A deck is assembled from three skill layers plus the Beamer fallback.

    Keeping this map in one place is what lets a look or runtime change land
    in one skill and reach every deck scaffolded afterwards.
    """
    deck, house = SKILLS / "deck-svg" / "template", SKILLS / "house-style" / "assets"
    runtime = SKILLS / "deck-runtime" / "template" / "asset"
    scaffold = TEMPLATES / "presentation" / "scaffold"
    return {
        "deck.html": deck / "variants" / variant / "deck.html",          # engine
        "asset/deck.css": deck / "asset" / "deck.css",
        "asset/tokens.css": house / "css" / "tokens.css",                # look
        "asset/ENSFont.woff2": house / "fonts" / "ENSFont.woff2",
        "asset/ENSFont-Bold.woff2": house / "fonts" / "ENSFont-Bold.woff2",
        "asset/deck-stage.js": runtime / "deck-stage.js",                # runtime
        "asset/presenter-stage.js": runtime / "presenter-stage.js",
        "presentation.qmd": scaffold / "variants" / variant / "presentation.qmd",
        "draft.qmd": scaffold / "draft.qmd",
        "notes/.gitkeep": scaffold / "notes" / ".gitkeep",
    }


def fill_placeholders(unit: Path, work: dict, fw_rel: str) -> None:
    """Scaffold files carry [標題]-style slots and the {{FW}} path token."""
    slots = {"[論文標題]": "title", "[論文主標題]": "title", "[簡報標題]": "title",
             "[作業標題]": "title", "[準備標題]": "title", "[副標題]": "subtitle",
             "[作者]": "author", "[日期]": "date"}
    for f in unit.rglob("*"):
        if f.suffix not in (".qmd", ".html", ".md") or not f.is_file():
            continue
        s = o = f.read_text(encoding="utf-8")
        for slot, key in slots.items():
            s = s.replace(slot, str(work.get(key, "")))
        s = s.replace("{{FW}}", fw_rel)
        if s != o:
            f.write_text(s, encoding="utf-8")


def update_status(root: Path, unit_name: str, ptype: str) -> None:
    status = root / "STATUS.md"
    if not status.is_file():
        return
    s = status.read_text(encoding="utf-8")
    s = re.sub(r"^Current unit:.*$", f"Current unit: `units/{unit_name}`", s, count=1, flags=re.M)
    s = s.rstrip("\n") + f"\n| `{unit_name}` | {ptype} | 未開始 | | |\n"
    status.write_text(s, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Create a new unit in a course repo.")
    ap.add_argument("--type", required=True, choices=TYPES)
    ap.add_argument("--name", required=True,
                    help="short ASCII slug for the directory, e.g. final, midterm-blockade")
    ap.add_argument("--title", required=True)
    ap.add_argument("--author", required=True)
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--citation", choices=("apa", "apa-zh"), default="apa")
    ap.add_argument("--variant", choices=("thesis", "reading-guide"))
    ap.add_argument("--extends", help="earlier unit this one builds on (recorded, never included live)")
    ap.add_argument("--no-build", action="store_true", help="skip the verification build")
    a = ap.parse_args()

    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", a.name):
        sys.exit("--name must be lowercase ASCII letters, digits, and hyphens: the directory "
                 "name ends up in paths, tags, and PDF filenames on every machine")
    if a.type == "presentation" and not a.variant:
        sys.exit("--variant thesis|reading-guide is required for a presentation")

    root = course_root()
    existing = list_units(root)
    if a.extends and not any(u.name == a.extends for u in existing):
        sys.exit(f"--extends: no unit named {a.extends}")
    numbers = [int(m.group(1)) for u in existing if (m := re.match(r"(\d+)-", u.name))]
    unit_name = f"{max(numbers, default=0) + 1:02d}-{a.type}-{a.name}"
    unit = root / "units" / unit_name
    if unit.exists():
        sys.exit(f"{rel(unit, root)} already exists")

    work = {"type": a.type, "title": a.title, "subtitle": a.subtitle,
            "author": a.author, "date": a.date}
    if a.type == "paper":
        work["citation"] = a.citation
    if a.type == "presentation":
        work["variant"] = a.variant
    if a.extends:
        work["extends"] = a.extends

    unit.mkdir(parents=True)
    if a.type == "presentation":
        files = presentation_files(a.variant)
        missing = [str(src) for src in files.values() if not src.is_file()]
        if missing:
            shutil.rmtree(unit)
            sys.exit("deck skills incomplete, missing:\n  " + "\n  ".join(missing))
        for dst, src in files.items():
            (unit / dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, unit / dst)
    else:
        copy_tree(TEMPLATES / a.type / "scaffold", unit)
        if a.type == "paper" and a.citation == "apa-zh":
            copy_tree(TEMPLATES / "paper" / "apa-zh", unit)

    shutil.copy2(SHARED / "PROGRESS.md", unit / "PROGRESS.md")
    if a.type in CITATION_TYPES and not (unit / "references.bib").exists():
        # One bib per tier, APA-zh included: entries carry langid and the
        # build groups 中文／西文. refs/ is created by the first fetch.
        shutil.copy2(SHARED / "references.bib", unit / "references.bib")

    import os
    fill_placeholders(unit, work, os.path.relpath(FRAMEWORK, unit))
    (unit / "WORK.json").write_text(json.dumps(work, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8")
    update_status(root, unit_name, a.type)
    print(f"created {rel(unit, root)}/  ({a.type})")

    if a.type != "presentation" and not a.no_build:
        print("verifying the unit builds …")
        r = subprocess.run([sys.executable, str(HERE / "build.py"), str(unit)])
        if r.returncode:
            sys.exit("the scaffold was created but the verification build failed — see above")
    print(f"next: commit it, e.g.  git add -A && git commit -m \"init: {unit_name} — {a.title}\"")


if __name__ == "__main__":
    main()
