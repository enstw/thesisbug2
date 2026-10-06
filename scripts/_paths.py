"""Locate the course root, the current unit, and the shared library.

A course repo looks like:

    <course>/            <- course root: holds .framework/ and units/
      library/           <- sources shared by two or more units
      units/NN-type-x/   <- a unit: any directory containing WORK.json

Every script resolves paths through this module so that none of them
hard-codes a layout. See docs/DESIGN.md § Course repository layout.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

UNIT_MARKER = "WORK.json"
TALK_MARKER = "talk.json"


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


def _containing_unit(path: Path, root: Path) -> Path | None:
    """Nearest unit containing *path*, without guessing across units."""
    path = path.resolve()
    start = path if path.is_dir() else path.parent
    for d in (start, *start.parents):
        if (d / UNIT_MARKER).is_file():
            return d
        if d == root:
            break
    return None


def _talk_at(path: Path, root: Path) -> tuple[Path, Path] | None:
    """Return ``(unit, talk_dir)`` when *path* names a talk.

    New talks carry ``talk.json``.  A presentation unit whose deck predates
    that marker remains a root talk, because framework updates must not force
    migrations on already-authored coursework.
    """
    path = path.resolve()
    if path.is_file():
        path = path.parent
    unit = _containing_unit(path, root)
    if not unit:
        return None
    if (path / TALK_MARKER).is_file():
        return unit, path
    if path == unit and (path / "deck.html").is_file():
        try:
            work = json.loads((unit / UNIT_MARKER).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if work.get("type") == "presentation":
            return unit, path
    return None


def find_talk(arg: str | None = None) -> tuple[Path, Path] | None:
    """Find a talk without exiting; used by commands that also accept units.

    A talk is either a legacy/root presentation unit or a directory with
    ``talk.json`` (normally ``<unit>/talks/<occasion>/``).  A unit with more
    than one talk is never guessed: callers must name the talk directory.
    """
    root = course_root()
    if arg:
        candidates = [Path(arg), root / arg, root / "units" / arg]
        # Preserve the convenient bare unit name accepted by resolve_unit.
        candidates += [u for u in list_units(root)
                       if u.name == arg or u.name.split("-", 2)[-1] == arg
                       or u.name.endswith("-" + arg)]
        seen: set[Path] = set()
        for cand in candidates:
            resolved = cand.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            found = _talk_at(resolved, root)
            if found:
                return found
        return None

    here = Path.cwd().resolve()
    for d in (here, *here.parents):
        found = _talk_at(d, root)
        if found:
            return found
        if d == root:
            break
    return None


def resolve_talk(arg: str | None = None) -> tuple[Path, Path]:
    """Resolve one talk as ``(unit, talk_dir)`` or stop with useful choices."""
    found = find_talk(arg)
    if found:
        return found
    root = course_root()
    talks = []
    for unit in list_units(root):
        root_talk = _talk_at(unit, root)
        if root_talk:
            talks.append(unit)
        talks.extend(sorted((unit / "talks").glob(f"*/{TALK_MARKER}")))
    names = [str((p.parent if p.name == TALK_MARKER else p).relative_to(root)) for p in talks]
    listing = "\n  ".join(names) if names else "(none yet — create one with: ./fw talk-init)"
    label = f"'{arg}' is not a talk" if arg else "which talk?"
    sys.exit(f"{label}; pass one of:\n  {listing}")


def talk_config(unit: Path, talk: Path) -> dict:
    """A talk's variant and declared unit-level Model files.

    ``talk.json`` paths are relative to the unit, not the talk directory: a
    paper can serve several talks without copying ``paper.qmd`` into each one.
    Root presentation units created before the marker default to their old
    ``draft.qmd`` contract; a migrated reading guide may instead have
    ``guide.qmd``.
    """
    marker = talk / TALK_MARKER
    if marker.is_file():
        try:
            config = json.loads(marker.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            sys.exit(f"{marker}: invalid JSON: {exc}")
    else:
        work = json.loads((unit / UNIT_MARKER).read_text(encoding="utf-8"))
        default = "guide.qmd" if (unit / "guide.qmd").is_file() else "draft.qmd"
        config = {"title": work.get("title", ""), "variant": work.get("variant", "thesis"),
                  "model": [default]}
    model = config.get("model")
    if not isinstance(model, list) or not model or not all(isinstance(p, str) and p for p in model):
        sys.exit(f"{marker if marker.is_file() else unit / UNIT_MARKER}: 'model' must be a non-empty list of unit-relative paths")
    if config.get("variant") not in ("thesis", "reading-guide"):
        sys.exit(f"{marker if marker.is_file() else unit / UNIT_MARKER}: 'variant' must be thesis or reading-guide")
    return config


def talk_model_files(unit: Path, talk: Path) -> list[Path]:
    """Validated Model entry files declared by the talk."""
    out = []
    for name in talk_config(unit, talk)["model"]:
        path = (unit / name).resolve()
        if not path.is_relative_to(unit.resolve()):
            sys.exit(f"{talk / TALK_MARKER}: model path leaves the unit: {name}")
        if not path.is_file():
            sys.exit(f"{talk / TALK_MARKER}: model file does not exist: {name}")
        out.append(path)
    return out


def library(root: Path | None = None) -> Path:
    return (root or course_root()) / "library"


def workflow_paths(unit: Path) -> dict[str, Path]:
    """The workflow store and its reading surfaces share one layout definition."""
    data = unit / ".workflow"
    return {"data": data, "task": data / "tasks", "decision": data / "decisions",
            "context": data / "context.json", "manifest": data / "store.json",
            "lock": data / ".lock", "archive": data / "migration.json",
            "progress": unit / "PROGRESS.md", "decisions": unit / "DECISIONS.md"}


INCLUDE_RE = re.compile(r"\{\{<\s*include\s+(\S+?)\s*>\}\}")

# Files the author writes but that are not prose to check: status files quote
# tool output and sources verbatim, refs/ keeps transcripts in the source's own
# script, gpt-review/ keeps a second model's report as received.
NOT_PROSE_NAMES = {"PROGRESS.md", "DECISIONS.md", "CHANGELOG.md"}
NOT_PROSE_DIRS = {"refs", "gpt-review"}


def included_files(source: Path, unit: Path) -> list[Path]:
    """Files `source` pulls in with Quarto's include shortcode, recursively.

    A Model assembled from local files is checked as it renders, because the
    facts may live in included notes rather than in the few lines of the .qmd.
    Includes inside HTML comments do not render and are skipped. So is a path
    outside the unit: a unit never includes another unit's file (DESIGN.md
    § Building on an earlier unit), and a gate should not report on it.
    """
    found: list[Path] = []

    def walk(path: Path) -> None:
        text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S)
        for m in INCLUDE_RE.finditer(text):
            target = m.group(1)
            # Quarto resolves a leading / from the project directory (the unit),
            # anything else from the including file.
            inc = (unit / target.lstrip("/") if target.startswith("/") else path.parent / target).resolve()
            if inc in found or not inc.is_file() or not inc.is_relative_to(unit.resolve()):
                continue
            found.append(inc)
            walk(inc)

    walk(source)
    return found


def manuscript_files(unit: Path) -> list[Path]:
    """The unit's prose sources: chapters/*.qmd plus top-level *.qmd, each
    followed by the files it includes."""
    files = sorted((unit / "chapters").glob("*.qmd")) + sorted(unit.glob("*.qmd"))
    out: list[Path] = []
    for f in files:
        if f.name.startswith("_"):
            continue
        for g in (f.resolve(), *included_files(f, unit)):
            if g not in out:
                out.append(g)
    return out


def citation_files(unit: Path) -> list[Path]:
    """Files whose citations are part of the unit's authored factual layer.

    All QMD entry points and their includes are checked.  The presenter's
    glossary and anticipated answers are checked directly even when they are
    deliberately absent from the submitted paper: they are factual backup the
    presenter may say aloud, not appendices the assignment must contain.
    """
    out: list[Path] = []
    for qmd in sorted(unit.rglob("*.qmd")):
        if any(part.startswith(("_", ".")) for part in qmd.relative_to(unit).parts):
            continue
        for f in (qmd.resolve(), *included_files(qmd, unit)):
            if f not in out:
                out.append(f)
    for name in ("notes/glossary.md", "notes/qa.md"):
        path = (unit / name).resolve()
        if path.is_file() and path not in out:
            out.append(path)
    return out


def prose_files(unit: Path) -> list[Path]:
    """Everything the author writes for the unit: the manuscript with its
    includes, plus the unit's other Markdown — notes, points, storyboard,
    handouts — because those feed the Model and the slides even when no
    .qmd includes them."""
    out = manuscript_files(unit)
    for md in sorted(unit.rglob("*.md")):
        parts = md.relative_to(unit).parts
        if (parts[0] in NOT_PROSE_DIRS or md.name in NOT_PROSE_NAMES
                or any(p.startswith(("_", ".")) for p in parts)):
            continue
        if md.resolve() not in out:
            out.append(md.resolve())
    return out


def rel(path: Path, root: Path | None = None) -> str:
    """Path relative to the course root, for messages an agent can act on."""
    try:
        return str(path.resolve().relative_to((root or course_root()).resolve()))
    except ValueError:
        return str(path)
