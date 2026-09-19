#!/usr/bin/env python3
"""Citation consistency gate for one unit of a course repo.

    ./fw check-citations [<unit>]

A unit's citations resolve against two tiers: its own references.bib and the
course's library/references.bib (sources shared by two or more units). Keys
are unique across the whole course repo, so the same key in two places — two
units, or a unit and the library — fails: one source would have two diverging
audit histories. The fix is `./fw refs promote <key>`.

Reports, for the unit:
  DUPLICATE   a key that lives in more than one bib file of the course   (fails)
  BROKEN      cited but in neither the unit's bib nor the library         (fails)
  INCOMPLETE  a bib entry this unit owns or cites lacks author/editor,
              title, or year                                              (fails)
  UNUSED      in the unit's own bib but never cited                       (warning)

Library entries this unit does not cite are not reported as unused: they are
there for other units.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import course_root, library, list_units, rel, resolve_unit  # noqa: E402

CITATION_RE = re.compile(r"(?<![\w@])@([a-zA-Z0-9_:.-]+)")
# Quarto cross-references share the @ syntax but are not citations.
CROSSREF_PREFIXES = ("fig-", "tbl-", "sec-", "eq-", "lst-", "thm-", "lem-", "cor-",
                     "prp-", "cnj-", "def-", "exm-", "exr-", "sol-", "rem-")
BIB_NAME = "references.bib"


def parse_bib_keys(bib_path: Path) -> dict[str, dict]:
    """Extract citation keys and their field names from a .bib file."""
    entries: dict[str, dict] = {}
    current_key = None
    current_fields: set[str] = set()
    for line in bib_path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("%"):
            continue
        m = re.match(r"@(\w+)\{(.+?),", line)
        if m:
            if current_key:
                entries[current_key] = {"fields": current_fields}
            current_key = m.group(2).strip()
            current_fields = set()
            continue
        m = re.match(r"\s*(\w+)\s*=", line)
        if m and current_key:
            current_fields.add(m.group(1).lower())
    if current_key:
        entries[current_key] = {"fields": current_fields}
    return entries


def find_cited_keys(unit: Path) -> dict[str, list[str]]:
    """All [@key] citations in the unit's .qmd files. Returns {key: [files]}."""
    cited: dict[str, list[str]] = {}
    for qmd in sorted(unit.rglob("*.qmd")):
        if any(part.startswith(("_", ".")) for part in qmd.relative_to(unit).parts):
            continue
        # Commented-out text is not part of the manuscript (scaffolds keep their
        # citation example in a comment).
        text = re.sub(r"<!--.*?-->", "", qmd.read_text(encoding="utf-8"), flags=re.S)
        for m in CITATION_RE.finditer(text):
            key = m.group(1).rstrip(".:")
            if key.startswith(CROSSREF_PREFIXES):
                continue
            name = str(qmd.relative_to(unit))
            if name not in cited.setdefault(key, []):
                cited[key].append(name)
    return cited


def missing_fields(info: dict) -> list[str]:
    missing = {"author", "title", "year"} - info["fields"]
    # Edited volumes carry editor instead of author; biblatex uses date for year.
    if "author" in missing and "editor" in info["fields"]:
        missing.discard("author")
    if "year" in missing and "date" in info["fields"]:
        missing.discard("year")
    return sorted(missing)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    root = course_root()
    unit = resolve_unit(args[0] if args else None)
    lib_bib = library(root) / BIB_NAME
    unit_bib = unit / BIB_NAME

    # Every bib file in the course, so a key living in two places is caught
    # no matter which unit the check was started from.
    all_bibs = [u / BIB_NAME for u in list_units(root)] + [lib_bib]
    if unit_bib not in all_bibs:
        all_bibs.append(unit_bib)
    all_bibs = [b for b in all_bibs if b.is_file()]

    if not unit_bib.is_file() and not lib_bib.is_file():
        print(f"ERROR: no {BIB_NAME} in {rel(unit, root)}/ or library/")
        sys.exit(1)

    where: dict[str, list[Path]] = {}
    entries: dict[str, dict] = {}
    for bib in all_bibs:
        for key, info in parse_bib_keys(bib).items():
            where.setdefault(key, []).append(bib)
            info["file"] = bib
            entries.setdefault(key, info)

    print(f"Unit:    {rel(unit, root)}")
    print("Bibs:    " + ", ".join(rel(b, root) for b in (unit_bib, lib_bib) if b.is_file()) + "\n")

    visible = {k for k, files in where.items() if unit_bib in files or lib_bib in files}
    cited = find_cited_keys(unit)
    errors = 0

    duplicates = {k: f for k, f in where.items() if len(f) > 1}
    if duplicates:
        errors += len(duplicates)
        print("DUPLICATE KEYS (one source, more than one home — promote it):")
        for key, files in sorted(duplicates.items()):
            print(f"  @{key}  in " + " and ".join(rel(f, root) for f in files))
            print(f"      fix: ./fw refs promote {key}")
        print()

    broken = {k: v for k, v in cited.items() if k not in visible}
    if broken:
        errors += len(broken)
        print("BROKEN CITATIONS (cited, but in neither this unit's bib nor the library):")
        for key, files in sorted(broken.items()):
            line = f"  @{key}  <- {', '.join(files)}"
            if key in where:  # it exists, but in another unit
                line += f"   (lives in {rel(where[key][0], root)} — ./fw refs promote {key})"
            print(line)
        print()

    own = {k for k, files in where.items() if unit_bib in files}
    unused = sorted(own - set(cited))
    if unused:
        print("UNUSED ENTRIES (in this unit's bib but never cited):")
        for key in unused:
            print(f"  @{key}")
        print()

    incomplete = []
    for key in sorted(own | (set(cited) & visible)):
        miss = missing_fields(entries[key])
        if miss:
            incomplete.append(f"  {key}: missing {', '.join(miss)}  ({rel(entries[key]['file'], root)})")
    if incomplete:
        errors += len(incomplete)
        print("MISSING REQUIRED FIELDS (author/editor, title, year/date):")
        print("\n".join(incomplete) + "\n")

    print(f"Summary: {len(cited)} cited keys, {len(own)} unit entries, "
          f"{len(visible - own)} library entries, {len(broken)} broken, "
          f"{len(unused)} unused, {len(incomplete)} incomplete, {len(duplicates)} duplicate")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
