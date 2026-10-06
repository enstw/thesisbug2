#!/usr/bin/env python3
"""Build one unit to PDF.

    ./fw build [<unit-or-talk>] [--target <file.qmd>] [--no-bib-gate] [--no-progress-gate] [--no-deck-gate]

Reads the unit's WORK.json, takes the matching template from
assets/templates/<type>/, and writes two generated files into the unit
(both gitignored, rewritten on every build):

    _quarto.yml     the template with title/author/date filled in, the
                    framework path resolved, the unit's chapters listed,
                    and the bibliography pointing at both source tiers
    _preamble.tex   the template preamble with the font path resolved

then runs `quarto render` in the unit and copies the PDF to
<course>/_output/<unit-name>.pdf.

HTML talks are hand-authored deck.html files printed from a browser. Passing a
root presentation unit or a ``talks/<occasion>/`` directory runs the deck gate
instead of rendering. Passing an ordinary unit still builds its assignment;
its attached talks are checked individually by naming their directories.
--no-deck-gate skips the deck gate once.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRAMEWORK = HERE.parent
sys.path.insert(0, str(HERE))
from _paths import (course_root, find_talk, library, rel, resolve_unit,
                    talk_config, talk_model_files)  # noqa: E402

PLACEHOLDERS = {
    "[論文標題]": "title", "[論文主標題]": "title", "[簡報標題]": "title", "[簡報主標題]": "title",
    "[作業標題]": "title", "[準備標題]": "title",
    "[副標題]": "subtitle", "[作者]": "author", "[日期]": "date",
}
CITATION_TYPES = ("paper", "journal", "thesis")
GEN_YML, GEN_PREAMBLE = "_quarto.yml", "_preamble.tex"
GEN_BIB_ZH, GEN_BIB_EN = "_bib-zh.bib", "_bib-en.bib"
ZH_LANGIDS = {"chinese", "zh", "zh-tw", "zh-hant", "zh-hans", "zh-cn", "tchinese", "schinese"}


def yaml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def splice_chapters(yml: str, unit: Path) -> str:
    """List the unit's actual chapters/*.qmd in place of the template's.

    The chapter layout belongs to the unit, not to the shared template;
    non-chapter entries (index.qmd, references.qmd) keep their positions.
    """
    files = sorted(p.name for p in (unit / "chapters").glob("*.qmd")
                   if not p.name.startswith("_"))
    m = re.search(r"^  chapters:\n((?:    - .+\n)+)", yml, re.M)
    if not files or not m:
        return yml
    out, inserted = [], False
    for line in m.group(1).splitlines():
        if "chapters/" in line:
            if not inserted:
                out.extend(f"    - chapters/{name}" for name in files)
                inserted = True
        else:
            out.append(line)
    return yml.replace(m.group(1), "\n".join(out) + "\n")


def bib_entries(path: Path) -> list[tuple[str, str]]:
    """(key, raw entry text) for each entry, by brace matching."""
    text = path.read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r"^@(\w+)\s*\{\s*([^,\s]+)\s*,", text, re.M):
        if m.group(1).lower() in ("comment", "preamble", "string"):
            continue
        depth, i = 0, m.start()
        while i < len(text):
            depth += text[i] == "{"
            depth -= text[i] == "}"
            i += 1
            if depth == 0 and text[i - 1] == "}":
                break
        out.append((m.group(2), text[m.start():i]))
    return out


def is_zh(entry: str) -> bool:
    """An entry is 中文 when its langid says so, else when its title has CJK.

    langid is the rule (docs/DESIGN.md); the title check only keeps an
    entry that forgot langid from landing in the wrong list silently.
    """
    m = re.search(r"\blang(?:id|uage)\s*=\s*[{\"]\s*([^}\"]+)", entry, re.I)
    if m:
        return m.group(1).strip().lower() in ZH_LANGIDS
    t = re.search(r"\btitle\s*=\s*[{\"](.+)", entry)
    return bool(t and re.search(r"[一-鿿]", t.group(1)))


def bibliography_yaml(unit: Path, root: Path, apa_zh: bool) -> str:
    """The bibliography: block. Library first, unit second; only files that exist."""
    tiers = [b for b in (library(root) / "references.bib", unit / "references.bib") if b.is_file()]
    if not tiers:
        return ""
    if not apa_zh:
        paths = [os.path.relpath(b, unit) for b in tiers]
        return "bibliography:\n" + "".join(f"  - {p}\n" for p in paths)
    # APA-zh-TW prints 中文 and 西文 as two lists. The sources stay in one bib
    # per tier; the split files are build products, regenerated every time.
    zh, en, missing = [], [], []
    for b in tiers:
        for key, entry in bib_entries(b):
            if not re.search(r"\blangid\s*=", entry, re.I):
                missing.append(key)
            (zh if is_zh(entry) else en).append(entry)
    if missing:
        print("note: no langid on " + ", ".join(missing[:8]) +
              (" …" if len(missing) > 8 else "") +
              " — grouped by title script; add langid = {chinese} or {english}.")
    header = "% Generated by ./fw build from references.bib (both tiers). Do not edit.\n\n"
    (unit / GEN_BIB_ZH).write_text(header + "\n\n".join(zh) + "\n", encoding="utf-8")
    (unit / GEN_BIB_EN).write_text(header + "\n\n".join(en) + "\n", encoding="utf-8")
    return f"bibliography:\n  zh: {GEN_BIB_ZH}\n  en: {GEN_BIB_EN}\n"


def generate(unit: Path, root: Path, work: dict) -> None:
    ptype = work["type"]
    tdir = FRAMEWORK / "assets" / "templates" / ptype
    apa_zh = ptype == "paper" and work.get("citation") == "apa-zh"
    template = tdir / ("_quarto-apa-zh.yml" if apa_zh else "_quarto.yml")
    if not template.is_file():
        sys.exit(f"no template for type '{ptype}' at {template}")

    fw_rel = os.path.relpath(FRAMEWORK, unit)
    yml = template.read_text(encoding="utf-8")
    if ptype == "presentation" and work.get("variant") == "reading-guide":
        yml = yml.replace("    - draft.qmd", "    - guide.qmd")
    for placeholder, key in PLACEHOLDERS.items():
        yml = yml.replace(f'"{placeholder}"', f'"{yaml_escape(str(work.get(key, "")))}"')

    # The preamble carries a font path LaTeX resolves from the unit directory,
    # so it has to be generated per unit too.
    pre = tdir / "preamble.tex"
    if pre.is_file():
        (unit / GEN_PREAMBLE).write_text(
            "% Generated by ./fw build. Do not edit.\n"
            + pre.read_text(encoding="utf-8").replace("{{FW}}", fw_rel), encoding="utf-8")
        yml = yml.replace(f"{{{{FW}}}}/assets/templates/{ptype}/preamble.tex", GEN_PREAMBLE)
    yml = yml.replace("{{FW}}", fw_rel)

    # Replace whatever bibliography block the template has with both tiers.
    yml = re.sub(r"^bibliography:.*\n(?:[ \t]+.*\n)*", "", yml, flags=re.M)
    yml = yml.rstrip("\n") + "\n\n" + bibliography_yaml(unit, root, apa_zh)
    yml = splice_chapters(yml, unit)
    (unit / GEN_YML).write_text(
        "# Generated by ./fw build from " + rel(template, FRAMEWORK) + ". Do not edit.\n" + yml,
        encoding="utf-8")


def bib_gate(unit: Path, work: dict) -> None:
    """Refuse to build a citation-bearing unit below its own quality floor."""
    level = work.get("required_bib_level")
    if work.get("type") not in CITATION_TYPES or level is None or "--no-bib-gate" in sys.argv:
        return
    checker = [sys.executable, str(HERE / "check-bib.py"), str(unit)]
    # Integrity first: --assert trusts the audit logs, so a rewritten log
    # could forge a verdict and pass the ratchet.
    if subprocess.run([*checker, "--audit"]).returncode:
        sys.exit("\nBuild blocked: a committed audit line was edited or removed. A correction "
                 "is a new line, never a rewrite. Override once with --no-bib-gate.")
    if subprocess.run([*checker, f"--assert=L{level}"]).returncode:
        sys.exit(f"\nBuild blocked: bib quality is below the unit's required L{level}. "
                 f"Run `./fw check-bib {unit.name} --todo` for the list, or lower "
                 "required_bib_level in the unit's WORK.json. Override once with --no-bib-gate.")


def progress_gate(unit: Path) -> None:
    """Refuse to build while the unit's status files have turned into a log.

    They are read at the start of every session, so history left in them is a
    cost paid each time and a stale "current state" agents will believe. A
    build is the one step every workstream reaches, which makes it the place a
    cleanup cannot be skipped — the same reasoning as the bib ratchet.
    """
    if "--no-progress-gate" in sys.argv:
        return
    if subprocess.run([sys.executable, str(HERE / "check-progress.py"), str(unit)]).returncode:
        sys.exit("\nBuild blocked: see above. Override once with --no-progress-gate.")


def deck_gate(unit: Path, talk: Path, root: Path) -> None:
    """Refuse a deck that skipped the storyboard or leans on one pattern.

    The storyboard is where the author sees, per slide, which content shape
    was chosen before the slide exists; without it the choice only shows up
    as oddly reshaped content on a finished deck. The pattern counts catch
    the two substitutions that lose the most: everything as a comparison
    table, and slides that are documents in bullet form. The gate cannot
    judge whether a shape fits — that is the storyboard review.
    """
    deck = talk / "deck.html"
    html = deck.read_text(encoding="utf-8")
    sections = [s for s in re.findall(r"<section\b([^>]*)>(.*?)</section>", html, flags=re.S)
                if "slide" in s[0]]
    slides = sections
    # hero/finale carry no argument; the pattern counts cover only the rest
    body = [s for s in sections if not re.search(r"\b(hero|finale)\b", s[0])]
    n = len(body)
    problems: list[str] = []

    # A note, not a block: units created before points.md existed have none,
    # and the layer's value is traceability the author reviews, not a count.
    points = talk / "points.md"
    # Validate explicit declarations even when the deck itself is HTML-only.
    # A talk whose authoritative Model was renamed or moved must not keep
    # passing its gate while silently losing traceability. Root presentations
    # from before talk.json remain supported: some have only deck.html and no
    # recoverable declaration to validate.
    if (talk / "talk.json").is_file():
        talk_model_files(unit, talk)
    model = ", ".join(talk_config(unit, talk)["model"])
    if not points.is_file() or "[論點：一句話]" in points.read_text(encoding="utf-8"):
        print(f"note: {rel(points, root)} is missing or still the template — each storyboard row "
              f"should name a point condensed from the declared Model ({model}), so no slide carries a "
              "claim the Model lacks (deck-plan skill)")

    storyboard = talk / "storyboard.md"
    if not storyboard.is_file():
        problems.append(f"no {rel(storyboard, root)} — write the storyboard (one row per slide: "
                        "source point, content shape, pattern) and have the author review it "
                        "before the deck; see the deck-plan skill")
    else:
        rows = [ln for ln in storyboard.read_text(encoding="utf-8").splitlines()
                if ln.startswith("|") and not ln.startswith("| :---") and not ln.startswith("| #")]
        rows = [r for r in rows if "[編號＋名稱]" not in r]
        if n and abs(len(rows) - len(slides)) > 2:
            problems.append(f"storyboard has {len(rows)} rows but the deck has {len(slides)} slides — "
                            "one row per slide, so a slide added without a shape decision shows up here")

    # Notes assembled from speaker-notes.md and the glossary/Q&A must match the
    # deck, because the presenter reads deck.html on stage: a stale note or a
    # reference to a missing entry is a gap found mid-talk. Only a file written
    # for deck-notes (its header names the command) is checked: a unit may keep
    # its own notes file and sync script from before the command existed.
    notes_md = talk / "speaker-notes.md"
    if notes_md.is_file() and "./fw deck-notes" in notes_md.read_text(encoding="utf-8"):
        r = subprocess.run([sys.executable, str(HERE / "deck-notes.py"), str(talk), "--check"],
                           capture_output=True, text=True)
        if r.returncode:
            problems.append("speaker notes: " + (r.stdout + r.stderr).strip())

    if n:
        tables = sum(1 for _, b in body if 'class="cmp' in b or "table class=\"cmp" in b)
        if tables / n > 0.4 and tables >= 3:
            problems.append(f"{tables} of {n} content slides use table.cmp — a comparison table is for "
                            "3+ items on shared attributes (shape 7); typologies, contrasts and spectra "
                            "have their own patterns (deck-plan reference/content-shapes.md)")
        fat = [i for i, (_, b) in enumerate(body, 1) if len(re.findall(r"<li\b", b)) > 6]
        if fat:
            problems.append(f"slide(s) {fat} carry more than 6 bullets — move detail to speaker notes "
                            "or split the slide")

    if problems:
        sys.exit("deck gate: " + "\n            ".join(problems) +
                 "\n(./fw build --no-deck-gate skips this once)")


def fix_preamble_include(unit: Path, target: str) -> None:
    """Point a target .qmd's header include at the generated _preamble.tex.

    Older scaffolds included the template preamble itself, whose font path is
    still the {{FW}} token, so XeLaTeX could not find the font. Only build
    resolves that token, into _preamble.tex; rewriting the one include line
    lets units created before the fix build without a manual migration.
    """
    qmd = unit / target
    if not qmd.is_file():
        return
    s = qmd.read_text(encoding="utf-8")
    fixed = re.sub(r"^(\s*-\s*)\S*/assets/templates/\w+/preamble\.tex[ \t]*$",
                   rf"\g<1>{GEN_PREAMBLE}", s, count=1, flags=re.M)
    if fixed != s:
        qmd.write_text(fixed, encoding="utf-8")
        print(f"note: {target} included the unresolved template preamble; now includes {GEN_PREAMBLE}")


def render(unit: Path, root: Path, target: str | None) -> None:
    dirs = (unit / "_output", unit)
    before = {p: p.stat().st_mtime_ns for d in dirs for p in d.glob("*.pdf")}
    cmd = ["quarto", "render"] + ([target] if target else [])
    print(f"→ {' '.join(cmd)}   (in {rel(unit, root)}/)")
    r = subprocess.run(cmd, cwd=unit)
    if r.returncode:
        sys.exit(r.returncode)
    fresh = [p for d in dirs for p in d.glob("*.pdf") if before.get(p) != p.stat().st_mtime_ns]
    if not fresh:
        sys.exit("quarto render succeeded but produced no new PDF")
    out = root / "_output"
    out.mkdir(exist_ok=True)
    name = unit.name + (f"-{Path(target).stem}" if target else "") + ".pdf"
    shutil.copy2(max(fresh, key=lambda p: p.stat().st_mtime_ns), out / name)
    print(f"→ {rel(out / name, root)}")


def main() -> None:
    argv = sys.argv[1:]
    target = None
    if "--target" in argv:
        i = argv.index("--target")
        if i + 1 >= len(argv):
            sys.exit("--target needs a filename")
        target = argv[i + 1]
        del argv[i:i + 2]
    positional = [a for a in argv if not a.startswith("--")]
    root = course_root()
    scope = positional[0] if positional else None
    talk_scope = find_talk(scope)
    if talk_scope and not target:
        unit, talk = talk_scope
        work = json.loads((unit / "WORK.json").read_text(encoding="utf-8"))
        progress_gate(unit)
        deck = talk / "deck.html"
        if not deck.is_file():
            sys.exit(f"no deck at {rel(deck, root)} — scaffold one with ./fw talk-init")
        if "--no-deck-gate" not in argv:
            deck_gate(unit, talk, root)
        print(f"The deck is {rel(deck, root)}. It has no build step: open it in a browser "
              "and Print → Save as PDF (one slide per page).")
        fallback = talk / "presentation.qmd"
        if fallback.is_file() and talk == unit:
            print(f"Beamer fallback: ./fw build {unit.name} --target presentation.qmd")
        return
    if talk_scope and target and talk_scope[1] != talk_scope[0]:
        sys.exit("--target builds a unit QMD; pass the owning unit, not a talks/<occasion> directory")

    unit = resolve_unit(scope)
    work = json.loads((unit / "WORK.json").read_text(encoding="utf-8"))

    progress_gate(unit)

    if work.get("type") == "presentation" and not (target and target.endswith(".qmd")):
        sys.exit(f"no deck at {rel(unit / 'deck.html', root)} — scaffold one with ./fw unit-init")

    bib_gate(unit, work)
    generate(unit, root, work)
    if target:
        fix_preamble_include(unit, target)
    render(unit, root, target)


if __name__ == "__main__":
    main()
