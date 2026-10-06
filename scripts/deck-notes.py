#!/usr/bin/env python3
"""Assemble a deck's speaker notes from the three parts of the talk.

    ./fw deck-notes [<talk>]            write #speaker-notes into deck.html
    ./fw deck-notes [<talk>] --check    exit 1 if deck.html is out of date or a reference is broken
    ./fw deck-notes [<talk>] --init     create speaker-notes.md, one section per slide

A speaker note is the presenter's backup: how to say the slide, and what the
presenter needs to understand it and to answer questions. Each kind comes
from the part of the talk that owns it (presentation protocol § Source Files):

  講法  <talk>/speaker-notes.md, one section per slide              — View
  名詞  <unit>/notes/glossary.md, one section per term              — backup knowledge
  提問  <unit>/notes/qa.md, one section per question                — backup knowledge

The storyboard's 名詞與提問 column (Controller) says which terms and questions
each slide carries. Terms and answers are factual backup shared by every talk
in the unit, so citation and language gates read them directly; they do not
need to be appended to a submitted paper. The note copies only each entry's
first paragraph, short enough to read at a glance; the full entry stays in the
unit for preparation before the talk.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import course_root, rel, resolve_talk  # noqa: E402

NOTES_MD, GLOSSARY, QA = "speaker-notes.md", "notes/glossary.md", "notes/qa.md"
REFS_COLUMN, SPOKEN_COLUMN = "名詞與提問", "口說重點"
BLOCK = re.compile(r'(<script type="application/json" id="speaker-notes">)(.*?)(</script>)', re.S)
SECTION = re.compile(r'<section\b([^>]*)>', re.S)
SLIDE_HEADING = re.compile(r"^(\d+)\s*[｜|]\s*(.*)$")
QUESTION_ID = re.compile(r"^(Q\d+)\b")
LABEL_PREFIX = re.compile(r"^\*\*[^*]+\*\*[：:]\s*")
CITE = re.compile(r"\[(@[\w:.-]+),\s*\{([^}]*)\}\]")

SPEAKER_NOTES_HEADER = """# 講者備註

<!-- View：每張投影片一節，標題「## 編號｜標籤」是它在 deck.html 的順序（從 0 起）與 data-label，./fw deck-notes 會核對兩者，
     因為插入或刪掉一張投影片後，編號沒跟著改，講稿就會接到別張投影片上。
     這裡只寫「講法」：照順序講什麼、時間、轉場、要停下來問大家的地方，依分鏡的口說重點與 talk.json 宣告的 Model 寫成（下面預先填了口說重點）。
     名詞解說與預想提問不寫在這裡：它們是事實，寫在單元共用的 notes/glossary.md 與 notes/qa.md（關卡會直接檢查）；
     分鏡「名詞與提問」欄指定每張帶哪些，./fw deck-notes 把它們的一句話版本接在講法後面，一起寫進 deck.html。
     改完這份就跑 ./fw deck-notes <talk>；不要直接改 deck.html 的 #speaker-notes，下一次組裝會蓋掉。 -->
"""


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


def init(unit: Path, talk: Path, root: Path) -> None:
    target = talk / NOTES_MD
    if target.exists():
        sys.exit(f"{rel(target, root)} exists; edit it instead")
    labels = slide_labels((talk / "deck.html").read_text(encoding="utf-8"))
    spoken = table_column(talk / "storyboard.md", SPOKEN_COLUMN)
    out = [SPEAKER_NOTES_HEADER]
    for n, label in enumerate(labels):
        seed = spoken.get(n, "")
        seed = "" if seed.startswith("[") else seed
        lines = [f"- {s.strip()}" for s in re.split(r"<br\s*/?>", seed) if s.strip()]
        out.append(f"## {n}｜{label}\n\n" + ("\n".join(lines) or "- [講法]") + "\n")
    target.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {rel(target, root)}: {len(labels)} sections seeded from the storyboard's {SPOKEN_COLUMN}")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    root = course_root()
    unit, talk = resolve_talk(args[0] if args else None)
    if not (talk / "deck.html").is_file():
        sys.exit(f"no deck at {rel(talk / 'deck.html', root)}")
    if "--init" in sys.argv:
        init(unit, talk, root)
        return
    if not (talk / NOTES_MD).is_file():
        sys.exit(f"no {rel(talk / NOTES_MD, root)} — create it with ./fw deck-notes {rel(talk, root)} --init")

    notes, problems = assemble(unit, talk, root)
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
        print(f"OK — {len(notes)} speaker notes match {NOTES_MD}, the storyboard and the glossary/Q&A")
        return
    payload = "\n" + json.dumps(notes, ensure_ascii=False, indent=0) + "\n"
    (talk / "deck.html").write_text(html[:m.start(2)] + payload + html[m.end(2):], encoding="utf-8")
    print(f"wrote {len(notes)} speaker notes into {rel(talk / 'deck.html', root)}")


if __name__ == "__main__":
    main()
