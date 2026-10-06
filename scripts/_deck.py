"""The HTML deck's file map, shared by unit-init (scaffold) and deck-refresh.

Paths on the left are relative to the presentation unit; paths on the right
are framework files. Finding the unit itself is `_paths`' job, not this
module's.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

FRAMEWORK = Path(__file__).resolve().parent.parent
SKILLS = FRAMEWORK / ".agents" / "skills"
TEMPLATES = FRAMEWORK / "assets" / "templates"


def deck_assets() -> dict[str, Path]:
    """The framework-owned files a deck carries in asset/ so it opens offline.

    These are the only files deck-refresh may overwrite, because they are
    copies of framework files: a deck picks its look with a per-deck default
    theme in deck.html, and a new theme or component belongs upstream, where
    every deck gets it. A local edit here is the exception; deck-refresh
    skips one that is uncommitted and lists a committed one as updated.
    """
    deck, house = SKILLS / "deck-svg" / "template", SKILLS / "house-style" / "assets"
    runtime = SKILLS / "deck-runtime" / "template" / "asset"
    return {
        "asset/deck.css": deck / "asset" / "deck.css",                   # engine
        "asset/deck-font-controls.js": deck / "asset" / "deck-font-controls.js",
        "asset/deck-check.js": deck / "asset" / "deck-check.js",         # deck.html#debug self-check
        "asset/deck-theme-controls.js": deck / "asset" / "deck-theme-controls.js",   # c/g live themes
        "asset/deck-theme-rules.js": house / "themes" / "deck-theme-rules.js",      # colour rules (one source)
        "asset/deck-palette.js": house / "themes" / "deck-palette.js",              # check + seeded generator
        "asset/tokens.css": house / "css" / "tokens.css",                # look
        "asset/ENSFont.woff2": house / "fonts" / "ENSFont.woff2",
        "asset/ENSFont-Bold.woff2": house / "fonts" / "ENSFont-Bold.woff2",
        "asset/deck-stage.js": runtime / "deck-stage.js",                # runtime
        "asset/presenter-stage.js": runtime / "presenter-stage.js",
    }


def starter_deck(variant: str) -> Path:
    return SKILLS / "deck-svg" / "template" / "variants" / variant / "deck.html"


def talk_files(variant: str) -> dict[str, Path]:
    """Files owned by one talk: its Controller, View and frozen assets."""
    scaffold = TEMPLATES / "presentation" / "scaffold"
    return {
        "deck.html": starter_deck(variant),
        **deck_assets(),
        "points.md": scaffold / "points.md",
        "storyboard.md": scaffold / "storyboard.md",
    }


def presentation_files(variant: str) -> dict[str, Path]:
    """Files for a standalone presentation unit.

    A reading guide gets ``guide.qmd``: a theme-focused Model derived from
    stable per-source summaries.  A thesis-style presentation keeps
    ``draft.qmd`` for compatibility with the legacy presentation scaffold. Generic
    paper/thesis units add a talk with ``talk-init`` instead and declare their
    existing manuscript as the Model.

    Keeping this map in one place is what lets a look or runtime change land
    in one skill and reach every deck scaffolded afterwards — and, through
    deck-refresh, every deck scaffolded before. Everything outside
    deck_assets() is a starter the author then owns.
    """
    scaffold = TEMPLATES / "presentation" / "scaffold"
    model = "guide.qmd" if variant == "reading-guide" else "draft.qmd"
    return {
        **talk_files(variant),
        "presentation.qmd": scaffold / "variants" / variant / "presentation.qmd",
        model: scaffold / model,
        "notes/glossary.md": scaffold / "notes" / "glossary.md",
        "notes/qa.md": scaffold / "notes" / "qa.md",
    }


def deck_problems(talk: Path) -> list[str]:
    """Structural problems in a freshly scaffolded HTML deck."""
    html = (talk / "deck.html").read_text(encoding="utf-8")
    problems = []
    slides = len(re.findall(r'<section\b[^>]*\bclass="slide\b', html))
    m = re.search(r'<script type="application/json" id="speaker-notes">(.*?)</script>', html, re.S)
    notes = json.loads(m.group(1)) if m else []
    if slides != len(notes) or not all(str(n).strip() for n in notes):
        problems.append(f"{slides} slides but {len(notes)} speaker notes (or an empty note)")
    for js in sorted((talk / "asset").glob("*.js")):
        if f'<script src="asset/{js.name}"></script>' not in html:
            problems.append(f"deck.html does not load asset/{js.name}")
    return problems


ASSET_TAG = re.compile(r"""<(?:script\b[^>]*\bsrc|link\b[^>]*\bhref)\s*=\s*["'](asset/[^"']+)["'][^>]*>(?:</script>)?""")


def asset_tags(html: str) -> list[tuple[str, str]]:
    """(asset path, the tag as written) for every <script src>/<link href> into asset/."""
    return [(m.group(1), m.group(0)) for m in ASSET_TAG.finditer(html)]


def missing_tags(deck_html: str, variant: str) -> list[tuple[str, str | None]]:
    """Tags the current starter has that the deck lacks, each with the starter
    tag it follows (None = first), because script order matters: the theme
    files must load before deck-stage rewrites the URL hash."""
    have = {path for path, _ in asset_tags(deck_html)}
    out, previous = [], None
    for path, tag in asset_tags(starter_deck(variant).read_text(encoding="utf-8")):
        if path not in have:
            out.append((tag, previous))
        previous = tag
    return out
