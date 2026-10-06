"""The HTML deck's file map, shared by unit-init (scaffold) and deck-refresh.

Paths on the left are relative to the presentation unit; paths on the right
are framework files. Finding the unit itself is `_paths`' job, not this
module's.
"""

from __future__ import annotations

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


def presentation_files(variant: str) -> dict[str, Path]:
    """A deck is assembled from three skill layers, its Model and Controller
    (the report; points → storyboard), and the Beamer fallback.

    Keeping this map in one place is what lets a look or runtime change land
    in one skill and reach every deck scaffolded afterwards — and, through
    deck-refresh, every deck scaffolded before. Everything outside
    deck_assets() is a starter the author then owns.
    """
    scaffold = TEMPLATES / "presentation" / "scaffold"
    return {
        "deck.html": starter_deck(variant),
        **deck_assets(),
        "presentation.qmd": scaffold / "variants" / variant / "presentation.qmd",
        "draft.qmd": scaffold / "draft.qmd",                             # Model: the cited argument
        "points.md": scaffold / "points.md",                             # Controller: angle, ~8–12 points
        "storyboard.md": scaffold / "storyboard.md",                     # Controller: flow, point → slide
        "notes/.gitkeep": scaffold / "notes" / ".gitkeep",
    }


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
