#!/usr/bin/env python3
"""Add one talk to any existing course unit.

    ./fw talk-init <unit> --name week16-seminar --model paper.qmd
                       [--title "…"] [--variant thesis|reading-guide]

Creates ``<unit>/talks/<name>/`` with talk.json, points.md, storyboard.md,
deck.html and its frozen assets.  Model paths in talk.json are relative to
the unit, so the talk reads the assignment's existing manuscript instead of
copying it.  The unit-level glossary and Q&A are created only when missing;
they are shared by every talk attached to that assignment.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRAMEWORK = HERE.parent
sys.path.insert(0, str(HERE))
from _deck import deck_problems, talk_files  # noqa: E402
from _paths import course_root, rel, resolve_unit  # noqa: E402

SCAFFOLD = FRAMEWORK / "assets" / "templates" / "presentation" / "scaffold"


def fill_placeholders(root: Path, values: dict[str, str], fw_rel: str) -> None:
    slots = {"[簡報標題]": "title", "[簡報主標題]": "title", "[副標題]": "subtitle",
             "[作者]": "author", "[日期]": "date"}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in (".html", ".md", ".qmd"):
            continue
        text = original = path.read_text(encoding="utf-8")
        for slot, key in slots.items():
            text = text.replace(slot, str(values.get(key, "")))
        text = text.replace("{{FW}}", fw_rel)
        if text != original:
            path.write_text(text, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Add a talk to an existing unit without copying its Model.")
    ap.add_argument("unit", help="unit path or name")
    ap.add_argument("--name", required=True,
                    help="occasion slug under talks/, e.g. week16-seminar")
    ap.add_argument("--model", required=True, nargs="+",
                    help="unit-relative Model file(s), e.g. paper.qmd")
    ap.add_argument("--title", help="default: the unit title")
    ap.add_argument("--variant", choices=("thesis", "reading-guide"), default="thesis")
    args = ap.parse_args()

    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.name):
        sys.exit("--name must be lowercase ASCII letters, digits, and hyphens")
    root = course_root()
    unit = resolve_unit(args.unit)
    work = json.loads((unit / "WORK.json").read_text(encoding="utf-8"))
    model = []
    for raw in args.model:
        path = (unit / raw).resolve()
        if not path.is_relative_to(unit.resolve()):
            sys.exit(f"--model leaves the unit: {raw}")
        if not path.is_file():
            sys.exit(f"--model does not exist: {raw}")
        model.append(path.relative_to(unit).as_posix())

    talk = unit / "talks" / args.name
    if talk.exists():
        sys.exit(f"{rel(talk, root)} already exists")
    title = args.title or work.get("title", args.name)
    files = talk_files(args.variant)
    missing = [str(src) for src in files.values() if not src.is_file()]
    if missing:
        sys.exit("deck skills incomplete, missing:\n  " + "\n  ".join(missing))
    for dst, src in files.items():
        target = talk / dst
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)

    notes = unit / "notes"
    notes.mkdir(exist_ok=True)
    for name in ("glossary.md", "qa.md"):
        target = notes / name
        if not target.exists():
            shutil.copy2(SCAFFOLD / "notes" / name, target)

    values = {**work, "title": title}
    fill_placeholders(talk, values, os.path.relpath(FRAMEWORK, talk))
    (talk / "talk.json").write_text(
        json.dumps({"title": title, "variant": args.variant, "model": model},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    problems = deck_problems(talk)
    if problems:
        sys.exit("the talk was created but the deck check failed:\n  " + "\n  ".join(problems))
    print(f"created {rel(talk, root)}/  (Model: {', '.join(model)})")
    print(f"next: write {rel(talk / 'points.md', root)} from the declared Model, then the storyboard")


if __name__ == "__main__":
    main()
