#!/usr/bin/env python3
"""Compile storyboard.md into deck.html using the Layout Catalog and seeded PRNG.

    ./fw deck-compile [<talk>]          compile storyboard.md into deck.html
    ./fw deck-compile [<talk>] --check  exit 1 if deck.html is out of sync with storyboard.md
    ./fw deck-compile [<talk>] --dry-run print compiled slides without writing deck.html

The compiler reads <talk>/storyboard.md, extracts the random seed from 前提,
validates layout codes against the Layout Catalog, resolves visual rhythm
(accents, depth variants), generates valid HTML slides, and updates deck.html.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _deck_catalog import CATALOG, VisualRhythmResolver, get_layout, parse_slot_payload  # noqa: E402
from _paths import course_root, rel, resolve_talk  # noqa: E402

STAGE_OPEN = re.compile(r"(<deck-stage\b[^>]*>)", re.I)
NOTES_BLOCK = re.compile(r'(<script\b[^>]*\bid="speaker-notes"[^>]*>.*?</script>)', re.S | re.I)
STAGE_CLOSE = re.compile(r"(</deck-stage>)", re.I)


def extract_seed(storyboard_text: str, default_seed: int = 42) -> int:
    """Extract Seed from storyboard premises: - **Seed:** 42 or - Seed: 42."""
    m = re.search(r"(?im)^[-*]\s*(?:\*\*)?Seed(?:\*\*)?\s*[:：]\s*(\w+)", storyboard_text)
    if m:
        val = m.group(1).strip()
        if val.isdigit():
            return int(val)
        # If it's a string like "2026-autumn" or "r4821", hash it deterministically
        return int(hashlib.md5(val.encode("utf-8")).hexdigest()[:8], 16)
    return default_seed


def extract_storyboard_rows(storyboard_text: str) -> list[dict[str, str]]:
    """Parse rows under ## 投影片 table into list of row dicts."""
    rows: list[dict[str, str]] = []
    lines = storyboard_text.splitlines()
    in_table = False
    headers: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cols = [c.strip() for c in stripped.strip("|").split("|")]
        if not cols:
            continue
        if cols[0] == "#":
            headers = cols
            in_table = True
            continue
        if in_table and cols[0] != ":---" and not cols[0].startswith("---"):
            if cols[0].isdigit() and len(cols) >= 4:
                row_dict = {}
                for idx, h in enumerate(headers):
                    if idx < len(cols):
                        row_dict[h] = cols[idx]
                rows.append(row_dict)
    return rows


def compile_storyboard(talk: Path) -> tuple[str, list[str]]:
    """Compile storyboard.md of a talk into HTML slides block and warnings."""
    sb_file = talk / "storyboard.md"
    if not sb_file.is_file():
        sys.exit(f"storyboard.md missing at {sb_file}")

    text = sb_file.read_text(encoding="utf-8")
    seed = extract_seed(text)
    rows = extract_storyboard_rows(text)
    if not rows:
        sys.exit(f"no slide rows found in {sb_file}")

    resolver = VisualRhythmResolver(seed)
    slides_html: list[str] = []
    warnings: list[str] = []
    total = len(rows)

    for idx, row in enumerate(rows):
        slide_num = int(row.get("#", idx))
        shape_col = row.get("內容形狀", "")
        layout_col = row.get("版型", "").strip()
        content_col = row.get("畫面內容", "")

        # Try to resolve layout
        try:
            layout_def = get_layout(layout_col)
        except ValueError as e:
            warnings.append(f"投影片 #{slide_num}: {e}")
            continue

        # Parse slots from content column
        slots = parse_slot_payload(content_col)

        # Infer title from shape/content if not provided in slot
        if "title" not in slots:
            # Check if there is a heading in content
            first_line = content_col.split("<br>")[0].strip()
            if first_line and not first_line.startswith(("-", "*", "cards:", "items:")):
                slots["title"] = first_line.split(":")[-1].strip()
            else:
                slots["title"] = shape_col or f"投影片 {slide_num}"

        # Resolve context and depth variant
        ctx, chosen_variant = resolver.resolve(
            layout=layout_def,
            slide_num=slide_num,
            total_slides=total - 1 if total > 1 else 1,
            eyebrow=shape_col.split()[0] if shape_col else "研討進度",
            title=slots.get("title", ""),
        )

        # Render slide HTML
        rendered = layout_def.render_func(slots, chosen_variant, ctx)
        slides_html.append(rendered)

    compiled_block = "\n\n".join(slides_html)
    return compiled_block, warnings


def apply_compilation(talk: Path, compiled_slides: str, dry_run: bool = False) -> bool:
    """Inject compiled slides into talk/deck.html."""
    deck_file = talk / "deck.html"
    if not deck_file.is_file():
        sys.exit(f"deck.html missing at {deck_file}")

    original = deck_file.read_text(encoding="utf-8")

    m_stage = STAGE_OPEN.search(original)
    if not m_stage:
        sys.exit(f"no <deck-stage> found in {deck_file}")

    stage_open_end = m_stage.end()
    m_notes = NOTES_BLOCK.search(original, stage_open_end)

    if m_notes:
        notes_start = m_notes.start()
        new_html = (
            original[:stage_open_end]
            + "\n\n"
            + compiled_slides
            + "\n\n  "
            + original[notes_start:]
        )
    else:
        m_close = STAGE_CLOSE.search(original, stage_open_end)
        if not m_close:
            sys.exit(f"malformed deck.html: no </deck-stage> found in {deck_file}")
        close_start = m_close.start()
        new_html = (
            original[:stage_open_end]
            + "\n\n"
            + compiled_slides
            + "\n\n"
            + original[close_start:]
        )

    if original == new_html:
        return False

    if not dry_run:
        deck_file.write_text(new_html, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("talk", nargs="?", help="the talk to compile (defaults to current)")
    parser.add_argument("--check", action="store_true", help="exit 1 if deck.html needs recompilation")
    parser.add_argument("--dry-run", action="store_true", help="print compiled output without writing")
    parser.add_argument("--explorer", action="store_true", help="print file:// URI to open the interactive layout explorer")
    args = parser.parse_args()

    if args.explorer:
        explorer_path = HERE.parent / "docs" / "layout-explorer.html"
        print(f"file://{explorer_path.resolve()}")
        return 0

    root = course_root()
    unit, talk = resolve_talk(args.talk)

    compiled_slides, warnings = compile_storyboard(talk)
    if warnings:
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)

    deck_file = talk / "deck.html"
    if args.check:
        original = deck_file.read_text(encoding="utf-8") if deck_file.is_file() else ""
        # Check if applying would change it
        changed = apply_compilation(talk, compiled_slides, dry_run=True)
        if changed:
            print(f"{rel(deck_file, root)} is out of sync with storyboard.md; run ./fw deck-compile {rel(talk, root)}")
            return 1
        return 0

    if args.dry_run:
        print(compiled_slides)
        return 0

    changed = apply_compilation(talk, compiled_slides, dry_run=False)
    if changed:
        print(f"compiled storyboard.md → {rel(deck_file, root)}")
    else:
        print(f"{rel(deck_file, root)} is already current")

    # If speaker-notes.md exists or notes script is present, run deck-notes to sync speaker notes
    notes_script = HERE / "deck-notes.py"
    if notes_script.is_file():
        subprocess.run([sys.executable, str(notes_script), str(talk)], capture_output=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
