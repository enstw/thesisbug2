#!/usr/bin/env python3
"""Compile storyboard.md into deck.html using the Layout Catalog and seeded PRNG.

    ./fw deck-compile [<talk>]          compile storyboard.md into deck.html
    ./fw deck-compile [<talk>] --check  exit 1 if deck.html is out of sync with storyboard.md
    ./fw deck-compile [<talk>] --dry-run print compiled slides without writing deck.html
    ./fw deck-compile --explorer        build the layout explorer (every layout × variant) and print its address
    ./fw deck-compile --icons <keyword> list the icon names for the icons: slot

The compiler reads <talk>/storyboard.md, extracts the random seed from 前提,
validates layout codes against the Layout Catalog, resolves visual rhythm
(accents, depth variants), generates valid HTML slides, and updates deck.html.
A storyboard without a `Seed` bullet gets a random one written into 前提 on the
first compile, so each deck has its own mix of variants and compiles to the same
deck every time after; --check and --dry-run never write.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _deck import NOTES_FILE, deck_assets, notes_source, unmanaged_notes  # noqa: E402
from _deck_catalog import (CATALOG, ICON_LAYOUTS, VisualRhythmResolver, art_names,  # noqa: E402
                           get_layout, icon_names, icon_set, parse_slot_payload, with_art)
from _deck_content import (FLOORS, art_credit, lost_content, missing_required,  # noqa: E402
                           sign_problem, type_floor)
from _deck_motion import apply_motion, split_codes  # noqa: E402
from _deck_outline import ensure_seed, extract_seed, extract_storyboard_rows, row_eyebrow, row_title  # noqa: E402
from _deck_steps import step_names, strip_html  # noqa: E402
from _paths import course_root, rel, resolve_talk  # noqa: E402

import html as html_lib
from html.parser import HTMLParser

WARNING_RE = re.compile(r"<!-- deck-compile warning: (.*?) -->")


class DeckStageLocator(HTMLParser):
    """Locate the deck-stage boundaries and speaker-notes block using standard HTML5 parser.

    Completely avoids regex pitfalls with HTML comments, CDATA, script variables, etc.
    """

    def __init__(self, raw_html: str):
        super().__init__()
        self.raw_html = raw_html
        self._line_offsets: list[int] = []
        cur = 0
        for line in raw_html.splitlines(keepends=True):
            self._line_offsets.append(cur)
            cur += len(line)
        self.stage_open: tuple[int, int] | None = None
        self.stage_close: int | None = None
        self.notes_start: int | None = None

    def _get_offset(self, line: int, col: int) -> int:
        if 1 <= line <= len(self._line_offsets):
            return self._line_offsets[line - 1] + col
        return len(self.raw_html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag_lower = tag.lower()
        if tag_lower == "deck-stage" and not self.stage_open:
            start = self._get_offset(*self.getpos())
            end = self.raw_html.find(">", start) + 1
            if end > 0:
                self.stage_open = (start, end)
        elif tag_lower == "script" and not self.notes_start:
            attrs_dict = dict(attrs)
            if attrs_dict.get("id") == "speaker-notes":
                self.notes_start = self._get_offset(*self.getpos())

    def handle_endtag(self, tag: str):
        if tag.lower() == "deck-stage" and not self.stage_close:
            self.stage_close = self._get_offset(*self.getpos())


def locate_stage(html: str) -> DeckStageLocator:
    loc = DeckStageLocator(html)
    loc.feed(html)
    return loc


def find_stage_open(html: str) -> tuple[int, int] | None:
    return locate_stage(html).stage_open


def add_formula(rendered: str, cell: str) -> str:
    """The 公式 column as one `p.fx` line at the foot of the slide body, typeset by asset/katex.

    `$…$` becomes `\\(…\\)`, the only delimiter deck-math.js typesets, because `$` also
    appears in ordinary slide text. A cover or closing slide has no `.content` and gets none.
    """
    cell = cell.strip()
    if not cell or cell in {"—", "-", "–"} or '<div class="content' not in rendered:
        return rendered
    tex = html_lib.escape(re.sub(r"\$(.+?)\$", r"\\(\1\\)", cell), quote=False)
    tex = tex.replace("｜", '<span class="sep">｜</span>')
    line = f'      <p class="fx rise d4">{tex}</p>\n'
    head, sep, tail = rendered.rpartition("    </div>\n  </section>")
    return head + line + sep + tail if sep else rendered


NOTES_COLUMN = "講者備註"
NOTE_SEPARATORS = re.compile(r"[、，,；;\s]+")


def bind_notes(rendered: str, row: dict[str, str]) -> str:
    """The 講者備註 column as the slide's data-notes, and 講 as its data-time.

    The knowledge-point numbers go on the slide itself, not into a list kept
    in slide order beside the deck, so a moved or inserted slide keeps its own
    notes. Tokens are copied as written; deck-notes refuses any that is not a
    K/Q number. A storyboard without the column (the older 名詞與提問 and
    口說重點 pair) compiles exactly as before.
    """
    if NOTES_COLUMN not in row:
        return rendered
    cell = row[NOTES_COLUMN].strip()
    tokens = [t for t in NOTE_SEPARATORS.split(cell) if t and t not in {"—", "-", "–"}]
    attrs = f' data-notes="{html_lib.escape(" ".join(tokens) or "—")}"'
    minutes = re.match(r"\s*(\d+(?:\.\d+)?)", row.get("講", ""))
    if minutes:
        attrs += f' data-time="{minutes.group(1)}"'
    return re.sub(r"<section\b", lambda m: m.group(0) + attrs, rendered, count=1)


NO_LAYOUT = {"", "—", "-", "–"}


def render_row(row: dict[str, str], idx: int, total: int,
               resolver: VisualRhythmResolver, talk: Path | None = None,
               steps: dict[str, str] | None = None,
               losses: list[str] | None = None) -> tuple[str | None, list[str]]:
    """Render one storyboard row as a slide, or None with a warning when its layout is not a catalog code.

    Content of the row that the slide does not show is reported in `losses` (in the
    warnings when the caller passes none): a layout that cannot show what the row says
    is the wrong layout, and trimming the row to fit is not the design stage's call.

    Shared with storyboard-review, which previews each row the way the deck will show it."""
    warnings: list[str] = []
    slide_num = int(row.get("#", idx))
    layout_col = row.get("版型", "").strip().strip("`")
    content_col = row.get("畫面內容", "")

    # Try to resolve layout
    if layout_col in NO_LAYOUT:
        warnings.append(f"投影片 #{slide_num}: 還沒選版型（設計階段在「版型」欄填 L- 代碼；"
                        "見 deck-svg 的 reference/layout-catalog.md）")
        return None, warnings
    try:
        layout_def = get_layout(layout_col)
    except ValueError as e:
        warnings.append(f"投影片 #{slide_num}: {e}")
        return None, warnings

    # Parse slots from content column
    slots = parse_slot_payload(content_col)

    # The title and the eyebrow fall back to the row's first line and its shape name;
    # the derived Views read them through the same functions (`_deck_outline`).
    slots.setdefault("title", row_title(row, slots, slide_num))
    resolved_eyebrow = row_eyebrow(row, slots)

    # Resolve context and depth variant; `variant: <name>` pins one when the drawn
    # variant does not suit the row's content (a long text that only fits the other form).
    pinned = slots.get("variant")
    pinned = pinned.strip() if isinstance(pinned, str) else ""
    if pinned and pinned not in layout_def.allowed_variants:
        warnings.append(f"投影片 #{slide_num}: {layout_def.id} 沒有變體 '{pinned}'"
                        f"（可用：{'、'.join(layout_def.allowed_variants)}），改用種子選的")
        pinned = ""
    ctx, chosen_variant = resolver.resolve(
        layout=layout_def,
        slide_num=slide_num,
        total_slides=total - 1 if total > 1 else 1,
        eyebrow=resolved_eyebrow,
        title=slots.get("label") or slots.get("data_label") or slots.get("title", ""),
        pinned=pinned,
    )

    # Render slide HTML, then the 動態 column's motion codes (deck-motion.js attributes).
    # A renderer that names a file (L-CANVAS `svg:`) reads it relative to the talk; a
    # renderer reports a problem as an HTML comment, lifted out here so it reaches stderr.
    ctx.base = talk
    # The step strip goes in the top bar only when the storyboard declares 流程步驟 and has
    # a 環節 column, so a storyboard without them compiles exactly as before.
    ctx.pmap = strip_html(row["環節"], steps) if steps and "環節" in row else ""
    rendered = with_art(layout_def.render_func(slots, chosen_variant, ctx), slots, talk, slide_num)
    if icon_names(slots) and layout_def.id not in ICON_LAYOUTS:
        warnings.append(f"投影片 #{slide_num}: {layout_def.id} 不畫 icons:（有圖示的版型：{'、'.join(ICON_LAYOUTS)}）")
    for msg in WARNING_RE.findall(rendered):
        warnings.append(f"投影片 #{slide_num}: {html_lib.unescape(msg)}")
    rendered = WARNING_RE.sub("", rendered)
    warnings.extend(f"投影片 #{slide_num}: {layout_def.id} 少了必填槽位 {name}"
                    for name in missing_required(layout_def, slots))
    lost = [f"投影片 #{slide_num}: {msg}" for msg in lost_content(layout_def.id, slots, rendered)]
    (warnings if losses is None else losses).extend(lost)
    rendered = add_formula(rendered, row.get("公式", ""))
    rendered, motion_warnings = apply_motion(rendered, split_codes(row.get("動態", "")))
    rendered = bind_notes(rendered, row)
    warnings.extend(f"投影片 #{slide_num}: {w}" for w in motion_warnings)
    return rendered, warnings


def compile_storyboard(talk: Path) -> tuple[str, list[str]]:
    """Compile storyboard.md of a talk into HTML slides block and warnings (lost content among them)."""
    compiled, warnings, losses = compile_checked(talk)
    return compiled, warnings + losses


def compile_checked(talk: Path) -> tuple[str, list[str], list[str]]:
    """(slides, warnings, problems): problems are what must be fixed before the deck is used —
    content the slides do not show, and content changed after the author signed it off."""
    sb_file = talk / "storyboard.md"
    if not sb_file.is_file():
        sys.exit(f"storyboard.md missing at {sb_file}")

    text = sb_file.read_text(encoding="utf-8")
    seed = extract_seed(text)
    rows = extract_storyboard_rows(text)
    if not rows:
        sys.exit(f"no slide rows found in {sb_file}")

    resolver = VisualRhythmResolver(seed)
    steps = step_names(text)
    slides_html: list[str] = []
    warnings: list[str] = []
    problems: list[str] = []
    total = len(rows)

    for idx, row in enumerate(rows):
        rendered, row_warnings = render_row(row, idx, total, resolver, talk, steps, problems)
        warnings.extend(row_warnings)
        if rendered is not None:
            slides_html.append(rendered)
    changed = sign_problem(text)
    if changed:
        problems.insert(0, changed)

    # Whoever watches the deck is told once, on the last slide, where its pictures come from.
    if slides_html and any(art_names(parse_slot_payload(row.get("畫面內容", ""))) for row in rows):
        credit = art_credit(text)
        if credit:
            head, _, tail = slides_html[-1].rpartition("  </section>")
            mark = '    <div class="plate'
            body, plate, rest = head.partition(mark)
            slides_html[-1] = f'{body}    <p class="art-credit">{html_lib.escape(credit)}</p>\n{plate}{rest}  </section>{tail}'
        else:
            warnings.append("有投影片用了 art: 圖片，但前提沒有說明來源；加一行「- 情境圖：AI 生成（工具名稱），"
                            "僅作氣氛，不代表實際場景」，這句話會印在最後一頁")

    compiled_block = "\n\n".join(slides_html)
    return compiled_block, warnings, problems


def apply_compilation(talk: Path, compiled_slides: str, dry_run: bool = False) -> bool:
    """Inject compiled slides into talk/deck.html."""
    deck_file = talk / "deck.html"
    if not deck_file.is_file():
        sys.exit(f"deck.html missing at {deck_file}")

    original = deck_file.read_text(encoding="utf-8")

    loc = locate_stage(original)
    if not loc.stage_open:
        sys.exit(f"no <deck-stage> found in {deck_file}")

    stage_open_end = loc.stage_open[1]

    if loc.notes_start and loc.notes_start > stage_open_end:
        new_html = (
            original[:stage_open_end]
            + "\n\n"
            + compiled_slides
            + "\n\n  "
            + original[loc.notes_start:]
        )
    elif loc.stage_close and loc.stage_close > stage_open_end:
        new_html = (
            original[:stage_open_end]
            + "\n\n"
            + compiled_slides
            + "\n\n"
            + original[loc.stage_close:]
        )
    else:
        sys.exit(f"malformed deck.html: no </deck-stage> found in {deck_file}")

    if original == new_html:
        return False

    if not dry_run:
        deck_file.write_text(new_html, encoding="utf-8")
    return True


def stale_deck_css(talk: Path, talk_arg: str) -> str:
    """A warning when the talk's copy of deck.css is not the framework's, "" otherwise.

    The renderers and deck.css change together, and a talk keeps its own copy of the
    stylesheet: slides compiled against an older copy carry classes it does not style.
    """
    mine, current = talk / "asset" / "deck.css", deck_assets()["asset/deck.css"]
    if mine.is_file() and mine.read_bytes() != current.read_bytes():
        return (f"{mine.parent.name}/deck.css differs from the framework's, so new layout variants may be "
                f"unstyled; run ./fw deck-refresh {talk_arg}")
    return ""


def floor_problem(talk: Path) -> str:
    """A warning when the room's type floor in 前提 is not the one deck.html declares, "" otherwise.

    deck.html is the author's file, so the compiler does not edit its <html> tag; it says
    what to write there, because the floor in 前提 changes nothing until the deck declares it.
    """
    sb_file, deck_file = talk / "storyboard.md", talk / "deck.html"
    if not sb_file.is_file() or not deck_file.is_file():
        return ""
    floor = type_floor(sb_file.read_text(encoding="utf-8"))
    if floor not in FLOORS:
        return (f"前提的字級下限 {floor}px 不是支援的值（{'／'.join(str(f) for f in FLOORS)}px）；"
                "它們各是 34px 標籤在 100%／90%／80% 字級的大小")
    m = re.search(r'<html\b[^>]*\bdata-deck-type-floor="(\d+)"', deck_file.read_text(encoding="utf-8"))
    declared = int(m.group(1)) if m else 34
    if declared == floor:
        return ""
    fix = (f'在 deck.html 的 <html> 加上 data-deck-type-floor="{floor}"' if floor != 34
           else "拿掉 deck.html <html> 上的 data-deck-type-floor")
    return f"前提的字級下限是 {floor}px，deck.html 宣告的是 {declared}px；{fix}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("talk", nargs="?", help="the talk to compile (defaults to current)")
    parser.add_argument("--check", action="store_true", help="exit 1 if deck.html needs recompilation")
    parser.add_argument("--dry-run", action="store_true", help="print compiled output without writing")
    parser.add_argument("--icons", metavar="KEYWORD", help="list the icon names that contain every word of KEYWORD (for the icons: slot)")
    parser.add_argument("--explorer", action="store_true", help="build the interactive layout explorer from the catalog examples and print its file:// URI")
    args = parser.parse_args()

    if args.icons:
        words = args.icons.lower().replace(",", " ").split()
        names = [name for name in sorted(icon_set()) if all(w in name for w in words)]
        print("\n".join(names) if names else f"no icon name contains {' and '.join(words)}; try one English word (ship, shield, users)")
        return 0 if names else 1
    if args.explorer:
        from _deck_explorer import build_explorer
        print(build_explorer().resolve().as_uri())
        return 0

    root = course_root()
    unit, talk = resolve_talk(args.talk)

    sb_file = talk / "storyboard.md"
    if sb_file.is_file() and not (args.check or args.dry_run):
        seed, written = ensure_seed(sb_file)
        if written:
            print(f"{rel(sb_file, root)}: 前提 had no Seed, wrote Seed: {seed} "
                  "(change the number for another mix of variants)")
    for note in (stale_deck_css(talk, rel(talk, root)), floor_problem(talk)):
        if note:
            print(f"warning: {note}", file=sys.stderr)

    compiled_slides, warnings, problems = compile_checked(talk)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    for p in problems:
        print(f"error: {p}", file=sys.stderr)
    if problems:
        print(f"{len(problems)} problem(s): the slides must show everything the storyboard says. "
              "Choose a layout that holds the row (deck-svg reference/layout-catalog.md), write one "
              "(L-CUSTOM), or hand the row back to the storyboard stage; do not trim it here.", file=sys.stderr)

    deck_file = talk / "deck.html"
    if not compiled_slides.strip() and not args.check:
        print(f"{rel(talk, root)}: no row has a layout yet, so nothing was compiled and deck.html is untouched; "
              "the design stage fills 版型 after the storyboard is signed off", file=sys.stderr)
        return 1
    if args.check:
        # Check if applying would change it
        changed = apply_compilation(talk, compiled_slides, dry_run=True)
        if changed:
            print(f"{rel(deck_file, root)} is out of sync with storyboard.md; run ./fw deck-compile {rel(talk, root)}")
        return 1 if changed or problems else 0

    if args.dry_run:
        print(compiled_slides)
        return 1 if problems else 0

    changed = apply_compilation(talk, compiled_slides, dry_run=False)
    if changed:
        print(f"compiled storyboard.md → {rel(deck_file, root)}")
    else:
        print(f"{rel(deck_file, root)} is already current")

    # Reassemble the notes, and say so when that fails or cannot happen: a
    # refusal swallowed here left decks whose notes nobody regenerated, so
    # agents typed them into deck.html instead. Compiled slides carry the
    # 講者備註 numbers in data-notes, so the notes move with their slide. A
    # unit's own notes file keeps its own sync script.
    source = notes_source(unit, talk)
    if source in ("knowledge", "deck-notes"):
        r = subprocess.run([sys.executable, str(HERE / "deck-notes.py"), str(talk)],
                           capture_output=True, text=True)
        if r.returncode:
            print((r.stdout + r.stderr).strip(), file=sys.stderr)
            fix = ("add the missing entries to the unit's speaker-notes.md or fix the storyboard's 講者備註 numbers"
                   if source == "knowledge" else
                   f"renumber or relabel the sections of {NOTES_FILE} to match the compiled slides")
            print(f"speaker notes not updated: {fix}, then run ./fw deck-notes {rel(talk, root)}",
                  file=sys.stderr)
            return 1
        print(r.stdout.strip())
    elif source == "none":
        print(f"note: {unmanaged_notes(rel(talk, root))}", file=sys.stderr)

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
