#!/usr/bin/env python3
"""Manage where a source lives in a course repo.

    ./fw refs where <key>       which tier holds the key, and who cites it
    ./fw refs promote <key>     move a source from its unit into library/

A source's files exist in exactly one place: the unit that fetched it, or —
once a second unit wants to cite it — library/. `promote` moves everything
that belongs to the key in one step, so its audit history travels with it:

    <unit>/references.bib entry      → library/references.bib
    <unit>/refs/<key>.md             → library/refs/<key>.md
    <unit>/refs/<key>-summary.md     → library/refs/
    <unit>/refs/audit/<key>.jsonl    → library/refs/audit/
    <unit>/refs/archive/<key>.*      → library/refs/archive/   (originals, untracked)
    library/refs/MANIFEST.tsv        path rewritten; the release asset is unchanged

When the same key already sits in more than one unit (a duplicate fetch),
promote keeps one copy and folds the others in: transcripts must be identical
(or absent), and audit lines are merged — never dropped — because every line
is a judgment someone made. It does not commit; review the diff, then commit.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import course_root, library, list_units, rel  # noqa: E402

BIB = "references.bib"
CITE_RE = r"(?<![\w@])@{key}(?![\w:.-]*[\w])"


def bib_entry_span(text: str, key: str) -> tuple[int, int] | None:
    m = re.search(r"^@\w+\s*\{\s*" + re.escape(key) + r"\s*,", text, re.M)
    if not m:
        return None
    depth, i = 0, m.start()
    while i < len(text):
        depth += text[i] == "{"
        depth -= text[i] == "}"
        i += 1
        if depth == 0 and text[i - 1] == "}":
            break
    while i < len(text) and text[i] == "\n":
        i += 1
    return m.start(), i


def homes(root: Path, key: str) -> list[Path]:
    """Tier directories (a unit, or library/) whose bib holds the key."""
    out = []
    for d in [*list_units(root), library(root)]:
        bib = d / BIB
        if bib.is_file() and bib_entry_span(bib.read_text(encoding="utf-8"), key):
            out.append(d)
    return out


def citing_units(root: Path, key: str) -> list[Path]:
    pat = re.compile(CITE_RE.format(key=re.escape(key)))
    out = []
    for u in list_units(root):
        for q in u.rglob("*.qmd"):
            if q.name.startswith("_"):
                continue
            text = re.sub(r"<!--.*?-->", "", q.read_text(encoding="utf-8"), flags=re.S)
            if pat.search(text):
                out.append(u)
                break
    return out


def key_files(tier: Path, key: str) -> list[Path]:
    refs = tier / "refs"
    found = [refs / f"{key}.md", refs / f"{key}-summary.md", refs / "audit" / f"{key}.jsonl"]
    for d in (refs, refs / "archive"):
        if d.is_dir():
            found += [p for p in d.glob(f"{key}.*") if p.suffix != ".md"]
    return [p for p in found if p.is_file()]


def tracked(root: Path, path: Path) -> bool:
    return subprocess.run(["git", "-C", str(root), "ls-files", "--error-unmatch", str(path)],
                          capture_output=True).returncode == 0


def move(root: Path, src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if tracked(root, src):
        subprocess.run(["git", "-C", str(root), "mv", str(src), str(dst)], check=True)
    else:
        shutil.move(str(src), str(dst))


def cmd_where(root: Path, key: str) -> int:
    hs = homes(root, key)
    if not hs:
        print(f"@{key} is in no references.bib of this course")
        return 1
    for h in hs:
        files = ", ".join(rel(f, root) for f in key_files(h, key)) or "(bib entry only)"
        print(f"home:  {rel(h, root)}   {files}")
    if len(hs) > 1:
        print(f"→ one source, {len(hs)} homes: ./fw refs promote {key}")
    for u in citing_units(root, key):
        print(f"cited: {rel(u, root)}")
    return 0


def cmd_promote(root: Path, key: str) -> int:
    lib = library(root)
    hs = homes(root, key)
    sources = [h for h in hs if h != lib]
    if not hs:
        sys.exit(f"@{key} is in no references.bib of this course")
    if not sources:
        print(f"@{key} already lives in library/ — nothing to do")
        return 0

    # Check everything before touching anything, so a refusal leaves no mess.
    transcripts = {h: (h / "refs" / f"{key}.md") for h in [*sources, lib]}
    texts = {h: p.read_bytes() for h, p in transcripts.items() if p.is_file()}
    if len(set(texts.values())) > 1:
        sys.exit("the copies of refs/" + key + ".md differ:\n  "
                 + "\n  ".join(rel(transcripts[h], root) for h in texts)
                 + "\nDecide which is the real transcript and delete the other, then run promote "
                   "again. They are not merged automatically: two transcripts of one key usually "
                   "means one of them is the wrong document.")
    for h in sources:
        for f in key_files(h, key):
            dst = lib / f.relative_to(h)
            if dst.exists() and f.suffix != ".jsonl" and dst.read_bytes() != f.read_bytes():
                sys.exit(f"{rel(dst, root)} already exists and differs from {rel(f, root)}")

    # 1. bib entry: keep the first copy, drop the rest.
    lib_bib = lib / BIB
    lib_text = lib_bib.read_text(encoding="utf-8") if lib_bib.is_file() else ""
    entry = None
    for h in sources:
        bib = h / BIB
        text = bib.read_text(encoding="utf-8")
        a, b = bib_entry_span(text, key)
        entry = entry or text[a:b].rstrip("\n")
        bib.write_text(text[:a] + text[b:], encoding="utf-8")
    if not bib_entry_span(lib_text, key):
        lib_bib.parent.mkdir(parents=True, exist_ok=True)
        lib_bib.write_text((lib_text.rstrip("\n") + "\n\n" if lib_text.strip() else "") + entry + "\n",
                           encoding="utf-8")

    # 2. files. Audit logs are merged line by line; everything else moves.
    moved = []
    for h in sources:
        for f in key_files(h, key):
            dst = lib / f.relative_to(h)
            if f.suffix == ".jsonl" and dst.exists():
                lines = dst.read_text(encoding="utf-8").splitlines() + f.read_text(encoding="utf-8").splitlines()
                seen, merged = set(), []
                for ln in lines:
                    if ln.strip() and ln not in seen:
                        seen.add(ln)
                        merged.append(ln)
                merged.sort(key=lambda ln: json.loads(ln).get("ts", "") if ln.startswith("{") else "")
                dst.write_text("\n".join(merged) + "\n", encoding="utf-8")
                subprocess.run(["git", "-C", str(root), "rm", "-q", "--cached", "--ignore-unmatch", str(f)])
                f.unlink()
            elif dst.exists():
                f.unlink()                       # identical copy, checked above
            else:
                move(root, f, dst)
            moved.append((f, dst))

    # 3. manifest paths (the release asset is named by basename, so no re-upload).
    manifest = lib / "refs" / "MANIFEST.tsv"
    if manifest.is_file():
        text = manifest.read_text(encoding="utf-8")
        for src, dst in moved:
            text = text.replace(rel(src, root) + "\t", rel(dst, root) + "\t")
        manifest.write_text(text, encoding="utf-8")

    # 4. support lines must say which unit they judged, or no unit can count them.
    log = lib / "refs" / "audit" / f"{key}.jsonl"
    unscoped = 0
    if log.is_file():
        for ln in log.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(ln)
            except json.JSONDecodeError:
                continue
            unscoped += e.get("check") == "support" and not e.get("unit")

    print(f"promoted @{key} → library/   (from {', '.join(rel(h, root) for h in sources)})")
    for src, dst in moved:
        print(f"  {rel(src, root)} → {rel(dst, root)}")
    if unscoped:
        print(f"note: {unscoped} support line(s) in the log carry no \"unit\" and will not count for any "
              "unit. Do not edit them — append a new support line with the unit named.")
    print("not committed — review `git status`, then commit.")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if len(argv) != 2 or argv[0] not in ("where", "promote"):
        print(__doc__.strip())
        return 2
    root = course_root()
    return (cmd_where if argv[0] == "where" else cmd_promote)(root, argv[1].lstrip("@"))


if __name__ == "__main__":
    sys.exit(main())
