#!/usr/bin/env python3
"""Assemble a deck's speaker notes from the knowledge points its slides name.

    ./fw deck-notes [<talk>]            write #speaker-notes into deck.html
    ./fw deck-notes [<talk>] --check    exit 1 if deck.html is out of date or a reference is broken
    ./fw deck-notes [<talk>] --init     create the unit's speaker-notes.md from the template

A speaker note is the presenter's backup knowledge, not a script: the terms,
abbreviations, facts and likely questions behind a slide, each with its page.
Each part has one owner (presentation protocol § Speaker notes):

  知識點  <unit>/speaker-notes.md, one `## K<n> <name>` or `## Q<n> <question>`
          section per point, first paragraph cited                 — backup knowledge
  綁定    each slide's data-notes="K3 K7 Q1"                         — View
  選擇    the storyboard's 講者備註 column; deck-compile copies it
          into data-notes                                           — Controller

The numbers sit on the slide, not in a list kept in slide order beside the
deck, so a moved or inserted slide keeps its own notes. The note copies only
each entry's first paragraph, short enough to glance at; the full entry stays
in the unit for preparation. The points are shared by every talk in the unit,
so citation and language gates read the file directly.

Decks from before the knowledge format still assemble: a per-slide 講法 file
`<talk>/speaker-notes.md` (`## <n>｜<label>` sections) plus notes/glossary.md
and notes/qa.md routed by the storyboard's 名詞與提問 column.
"""

from __future__ import annotations

import html as html_lib
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _deck import TEMPLATES, is_knowledge_file, notes_source, unmanaged_notes  # noqa: E402
from _paths import course_root, rel, resolve_talk  # noqa: E402

NOTES_MD, GLOSSARY, QA = "speaker-notes.md", "notes/glossary.md", "notes/qa.md"
REFS_COLUMN = "名詞與提問"
BLOCK = re.compile(r'(<script type="application/json" id="speaker-notes">)(.*?)(</script>)', re.S)
SECTION = re.compile(r'<section\b([^>]*)>', re.S)
SLIDE_HEADING = re.compile(r"^(\d+)\s*[｜|]\s*(.*)$")
QUESTION_ID = re.compile(r"^(Q\d+)\b")
ENTRY_ID = re.compile(r"^([KQ]\d+)\b")
NOTE_ID = re.compile(r"^[KQ]\d+$")
LABEL_PREFIX = re.compile(r"^\*\*[^*]+\*\*[：:]\s*")
CITE = re.compile(r"\[(@[\w:.-]+),\s*\{([^}]*)\}\]")
# An abbreviation the audience reads: two or more capitals standing alone (FPA, MAD).
ABBREVIATION = re.compile(r"(?<![A-Za-z])[A-Z]{2,}(?![A-Za-z])")
NONE_MARKS = {"—", "-", "–"}

def strip_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def headed_sections(text: str) -> list[tuple[str, str]]:
    """(heading, body) for every level-2 heading, comments removed."""
    parts = re.split(r"(?m)^## +(.+?)\s*$", strip_comments(text))
    return [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts), 2)]


def note_cites(text: str) -> str:
    """[@key, {12}] → [@key, p. 12]: the presenter window shows plain text,
    and the protocol's note locator form is [@bibkey, p. 15]."""
    def one(m: re.Match) -> str:
        loc = m.group(2).strip()
        if re.fullmatch(r"\d+", loc):
            loc = f"p. {loc}"
        elif re.fullmatch(r"[\d\s,–-]+", loc):
            loc = f"pp. {loc}"
        return f"[{m.group(1)}, {loc}]"
    return CITE.sub(one, text)


def first_paragraph(body: str) -> str:
    """An entry's short version: its first paragraph, label removed."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if not paras:
        return ""
    text = " ".join(line.strip() for line in paras[0].splitlines())
    return note_cites(LABEL_PREFIX.sub("", text)).replace("**", "")


def plain(body: str) -> str:
    """Markdown 講法 → presenter-window text: list items become ・ lines,
    nesting becomes full-width indent, emphasis markers are dropped."""
    out, levels = [], [0]
    for line in strip_comments(body).splitlines():
        if not line.strip() or line.strip() == "---":
            continue
        indent = len(line) - len(line.lstrip())
        # Nesting is counted by indentation levels seen, not a fixed width,
        # because "1." lists nest by three spaces and "-" lists by two or four.
        while indent < levels[-1]:
            levels.pop()
        if indent > levels[-1]:
            levels.append(indent)
        item = re.match(r"^\s*(?:\d+\.|[-*])\s+", line)
        text = note_cites(line[item.end():] if item else line.strip()).replace("**", "")
        out.append("　" * (len(levels) - 1) + ("・" if item else "") + text)
    return "\n".join(out)


def entries(path: Path, questions: bool) -> dict[str, tuple[str, str]]:
    """{id: (heading, short version)}; placeholders (headings with '[') are skipped."""
    found: dict[str, tuple[str, str]] = {}
    if not path.is_file():
        return found
    for heading, body in headed_sections(path.read_text(encoding="utf-8")):
        if "[" in heading:
            continue
        key = heading
        if questions:
            m = QUESTION_ID.match(heading)
            if not m:
                continue
            key = m.group(1)
        found[key] = (heading, first_paragraph(body))
    return found


def table_column(storyboard: Path, name: str) -> dict[int, str]:
    """{slide number: cell} for one named column of the storyboard table."""
    cells: dict[int, str] = {}
    if not storyboard.is_file():
        return cells
    col = None
    for line in strip_comments(storyboard.read_text(encoding="utf-8")).splitlines():
        if not line.startswith("|"):
            continue
        row = [c.strip() for c in line.strip().strip("|").split("|")]
        if row and row[0] == "#":
            col = row.index(name) if name in row else None
            continue
        if col is not None and row and row[0].isdigit() and col < len(row):
            cells[int(row[0])] = row[col]
    return cells


def references(cell: str) -> list[str]:
    tokens = [t.strip() for t in re.split(r"[、，,；;]", cell)]
    return [t for t in tokens if t and t not in ("—", "-") and not t.startswith("[")]


def slide_labels(html: str) -> list[str]:
    labels = []
    for m in SECTION.finditer(html):
        attrs = m.group(1)
        cls = re.search(r'class="([^"]*)"', attrs)
        if cls and re.search(r"slide", cls.group(1)):
            label = re.search(r'data-label="([^"]*)"', attrs)
            labels.append(label.group(1) if label else "")
    return labels


def assemble(unit: Path, talk: Path, root: Path) -> tuple[list[str], list[str]]:
    """(notes, problems) for one talk's deck."""
    html = (talk / "deck.html").read_text(encoding="utf-8")
    labels = slide_labels(html)
    problems: list[str] = []

    sections = []
    for heading, body in headed_sections((talk / NOTES_MD).read_text(encoding="utf-8")):
        m = SLIDE_HEADING.match(heading)
        if m:
            sections.append((int(m.group(1)), m.group(2).strip(), body))
        else:
            problems.append(f"{NOTES_MD}: heading '## {heading}' is not '## <number>｜<label>'")
    numbers = [n for n, _, _ in sections]
    if numbers != list(range(len(numbers))):
        problems.append(f"{NOTES_MD}: sections must be numbered 0, 1, 2, … in order; found {numbers}")
    if len(sections) != len(labels):
        problems.append(f"{NOTES_MD} has {len(sections)} sections but deck.html has {len(labels)} slides")
    for n, label, body in sections:
        if n < len(labels) and " ".join(label.split()) != " ".join(labels[n].split()):
            problems.append(f"{NOTES_MD} § {n} is '{label}' but slide {n} is data-label '{labels[n]}' — "
                            "a slide was added or moved without renumbering")
        if not plain(body).strip() or "[講法]" in body:
            problems.append(f"{NOTES_MD} § {n} has no 講法 yet")

    glossary, qa = entries(unit / GLOSSARY, False), entries(unit / QA, True)
    refs = table_column(talk / "storyboard.md", REFS_COLUMN)
    notes = []
    for n, label, body in sections:
        terms, questions = [], []
        for ref in references(refs.get(n, "")):
            if QUESTION_ID.fullmatch(ref):
                if ref in qa:
                    questions.append(qa[ref])
                else:
                    problems.append(f"storyboard row {n} names {ref}, which {QA} does not have")
            else:
                if ref in glossary:
                    terms.append((ref, glossary[ref][1]))
                else:
                    problems.append(f"storyboard row {n} names '{ref}', which {GLOSSARY} does not have — "
                                    "write the entry there first, because a term the note explains is a fact")
        parts = [label, "【講法】", plain(body)]
        if terms:
            parts += ["【名詞】"] + [f"・{t}：{short}" for t, short in terms]
        if questions:
            parts += ["【提問】"] + [f"・{q}\n　{short}" for q, short in questions]
        notes.append("\n".join(parts))
    beyond = sorted(k for k, v in refs.items() if k >= len(sections) and references(v))
    if beyond:
        problems.append(f"storyboard rows {beyond} name terms or questions but {NOTES_MD} has no such slide")
    return notes, problems



def attribute(attrs: str, name: str) -> str | None:
    m = re.search(rf'\b{name}="([^"]*)"', attrs)
    return html_lib.unescape(m.group(1)) if m else None


def slides(html: str) -> list[dict]:
    """Each slide's label, kind and knowledge binding, in deck order."""
    out = []
    for m in SECTION.finditer(html):
        attrs = m.group(1)
        cls = attribute(attrs, "class") or ""
        if "slide" not in cls:      # deck-svg's .slide and deck-image's .imgslide
            continue
        out.append({"label": attribute(attrs, "data-label") or "",
                    "notes": attribute(attrs, "data-notes"),
                    "time": attribute(attrs, "data-time"),
                    "chrome": bool(re.search(r"\b(hero|finale)\b", cls))})
    return out


def visible_texts(html: str) -> list[str]:
    """What the audience reads on each slide (deck-text's extraction)."""
    spec = importlib.util.spec_from_file_location("deck_text", HERE / "deck-text.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.slide_texts(html)


def knowledge(path: Path) -> dict[str, tuple[str, str]]:
    """{K7: (heading, short version)}; placeholder headings (with '[') are skipped."""
    found: dict[str, tuple[str, str]] = {}
    for heading, body in headed_sections(path.read_text(encoding="utf-8")):
        m = ENTRY_ID.match(heading)
        if m and "[" not in heading:
            found[m.group(1)] = (heading, first_paragraph(body))
    return found


def assemble_knowledge(unit: Path, talk: Path, root: Path) -> tuple[list[str], list[str]]:
    """(notes, problems): each slide's data-notes expanded from the unit's knowledge points."""
    html = (talk / "deck.html").read_text(encoding="utf-8")
    path = unit / NOTES_MD
    problems: list[str] = []
    if not is_knowledge_file(path):
        return [], [f"{rel(path, root)} is missing or not in the knowledge format — "
                    f"create it with ./fw deck-notes {rel(talk, root)} --init"]
    points = knowledge(path)
    for key, (heading, short) in points.items():
        if "[@" not in short:
            problems.append(f"{NOTES_MD} § {heading}: the first paragraph carries no citation — the note "
                            "shows only that paragraph, and the presenter may say it aloud")
    deck_slides = slides(html)
    texts = visible_texts(html)
    notes = []
    for n, slide in enumerate(deck_slides):
        where = f"slide {n} ({slide['label']})"
        if slide["notes"] is None:
            if not slide["chrome"]:
                problems.append(f"{where} has no data-notes — list its knowledge points (K/Q numbers) on the "
                                "slide, or data-notes=\"—\" when it needs none")
            ids = []
        else:
            ids = [t for t in re.split(r"[\s、，,；;]+", slide["notes"]) if t and t not in NONE_MARKS]
        for token in ids:
            if not NOTE_ID.match(token):
                problems.append(f"{where}: data-notes holds only K/Q numbers, found '{token}' — write the "
                                f"point into {NOTES_MD} and list its number")
            elif token not in points:
                problems.append(f"{where} names {token}, which {NOTES_MD} does not have")
        headings = " ".join(points[t][0] for t in ids if t in points)
        shown = texts[n] if n < len(texts) else ""
        for abbr in sorted(set(ABBREVIATION.findall(shown))):
            if f"（{abbr}）" not in headings and f"({abbr})" not in headings:
                problems.append(f"{where} shows '{abbr}' but none of its knowledge points is titled "
                                f"全名（{abbr}） — the presenter must be able to expand every abbreviation on the slide")
        head = slide["label"] + (f"（{slide['time']} 分）" if slide["time"] else "")
        parts = [head]
        for token in ids:
            if token in points:
                heading, short = points[token]
                parts.append(f"・{heading}\n　{short}" if token.startswith("Q") else f"・{heading}：{short}")
        notes.append("\n".join(parts))
    return notes, problems


def init(unit: Path, talk: Path, root: Path) -> None:
    target = unit / NOTES_MD
    if is_knowledge_file(target):
        sys.exit(f"{rel(target, root)} exists; edit it instead")
    if target.exists():
        sys.exit(f"{rel(target, root)} exists in another format (per-slide 講法 or the unit's own); move its "
                 "facts into K/Q entries by hand, because a script cannot tell a fact from a delivery cue")
    shutil.copy2(TEMPLATES / "presentation" / "scaffold" / NOTES_MD, target)
    print(f"wrote {rel(target, root)}: add K/Q entries, then list each slide's numbers in the storyboard's "
          "講者備註 column (deck-compile copies them into data-notes)")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    root = course_root()
    unit, talk = resolve_talk(args[0] if args else None)
    if not (talk / "deck.html").is_file():
        sys.exit(f"no deck at {rel(talk / 'deck.html', root)}")
    if "--init" in sys.argv:
        init(unit, talk, root)
        return

    source = notes_source(unit, talk)
    if source == "knowledge":
        notes, problems = assemble_knowledge(unit, talk, root)
    elif (talk / NOTES_MD).is_file():
        notes, problems = assemble(unit, talk, root)
    else:
        sys.exit(unmanaged_notes(rel(talk, root)))
    if problems:
        print("\n".join(f"  {p}" for p in problems))
        sys.exit(f"deck-notes: {len(problems)} problem(s); deck.html not written")
    html = (talk / "deck.html").read_text(encoding="utf-8")
    m = BLOCK.search(html)
    if not m:
        sys.exit("deck.html has no <script type=\"application/json\" id=\"speaker-notes\"> block")
    if "--check" in sys.argv:
        try:
            current = json.loads(m.group(2))
        except json.JSONDecodeError:
            current = None
        if current != notes:
            sys.exit(f"deck.html speaker notes are out of date — run ./fw deck-notes {rel(talk, root)}")
        print(f"OK — {len(notes)} speaker notes match {NOTES_MD} and the slides' references")
        return
    payload = "\n" + json.dumps(notes, ensure_ascii=False, indent=0) + "\n"
    (talk / "deck.html").write_text(html[:m.start(2)] + payload + html[m.end(2):], encoding="utf-8")
    print(f"wrote {len(notes)} speaker notes into {rel(talk / 'deck.html', root)}")


if __name__ == "__main__":
    main()
