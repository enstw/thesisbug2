"""Locate the course root, the current unit, and the shared library.

A course repo looks like:

    <course>/            <- course root: holds .framework/ and units/
      library/           <- sources shared by two or more units
      units/NN-type-x/   <- a unit: any directory containing WORK.json

Every script resolves paths through this module so that none of them
hard-codes a layout. See docs/DESIGN.md § Course repository layout.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

UNIT_MARKER = "WORK.json"


def course_root(start: Path | None = None) -> Path:
    """Nearest ancestor that holds .framework/ or units/.

    FW_COURSE_ROOT (set by the fw dispatcher) wins, so a script behaves the
    same whether it was started from the course root or from inside a unit.
    """
    env = os.environ.get("FW_COURSE_ROOT")
    if env:
        return Path(env).resolve()
    here = (start or Path.cwd()).resolve()
    for d in (here, *here.parents):
        if (d / ".framework").exists() or (d / "units").is_dir():
            return d
    sys.exit(
        "not inside a course repo: no .framework/ or units/ found above "
        f"{here}. Run this from a course root created by course-init."
    )


def list_units(root: Path) -> list[Path]:
    units = root / "units"
    if not units.is_dir():
        return []
    return sorted(p.parent for p in units.glob(f"*/{UNIT_MARKER}"))


def resolve_unit(arg: str | None = None) -> Path:
    """The unit to act on.

    An explicit argument wins (a path, or a bare unit name under units/).
    Otherwise use the nearest WORK.json at or above the working directory.
    From the course root with nothing given, list the units and stop:
    guessing would let a gate or an edit land on the wrong assignment.
    """
    root = course_root()
    if arg:
        for cand in (Path(arg), root / arg, root / "units" / arg):
            if (cand / UNIT_MARKER).is_file():
                return cand.resolve()
        # The short name given to unit-init (`final` for 03-paper-final) is what
        # an author remembers; accept it when exactly one unit ends with it, and
        # refuse to guess between two.
        short = [u for u in list_units(root) if u.name.split("-", 2)[-1] == arg
                 or u.name.endswith("-" + arg)]
        if len(short) == 1:
            return short[0].resolve()
        if len(short) > 1:
            sys.exit(f"'{arg}' matches more than one unit: "
                     + ", ".join(u.name for u in short) + " — use the full name")
        sys.exit(f"not a unit (no {UNIT_MARKER}): {arg}")
    here = Path.cwd().resolve()
    for d in (here, *here.parents):
        if (d / UNIT_MARKER).is_file():
            return d
        if d == root:
            break
    names = [str(u.relative_to(root)) for u in list_units(root)]
    listing = "\n  ".join(names) if names else "(none yet — create one with: ./fw unit-init)"
    sys.exit(f"which unit? pass one of:\n  {listing}")


def library(root: Path | None = None) -> Path:
    return (root or course_root()) / "library"


def manuscript_files(unit: Path) -> list[Path]:
    """The unit's prose sources: chapters/*.qmd plus top-level *.qmd."""
    files = sorted((unit / "chapters").glob("*.qmd")) + sorted(unit.glob("*.qmd"))
    return [f for f in files if not f.name.startswith("_")]


def rel(path: Path, root: Path | None = None) -> str:
    """Path relative to the course root, for messages an agent can act on."""
    try:
        return str(path.resolve().relative_to((root or course_root()).resolve()))
    except ValueError:
        return str(path)
