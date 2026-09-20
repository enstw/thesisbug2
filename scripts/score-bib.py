#!/usr/bin/env python3
"""Bib quality profile — per-source axes, portfolio balance, and worklists.

    ./fw score-bib [<unit>] [--table]

The third view of a bibliography, beside the two gates:

    ./fw check-citations   consistency — keys resolve, format clean, none unused
    ./fw check-bib         backing     — fulltext on disk, identity and support
                                         audited, page locators covered
    ./fw score-bib         quality     — how good is each source for the role it
                                         plays, and is the set balanced?

check-bib asks whether a source *backs* the claim made from it; this asks
whether it is the right *kind* of source to be carrying that claim at all.
Neither answer implies the other: a party's press release can back its own
quoted figure perfectly and still be the wrong thing to hang a finding on.

Axes (0-3), judged by hand and kept in the `bib-scores.yml` sidecar:

  authority     3 peer-reviewed / university press / official primary document
                2 established working-paper series (NBER/BIS/IMF), IGO and
                  central-bank reports, legislative research services, flagship
                  industry annual reports, expert trade books
                1 think-tank analysis, vendor research notes, quality media
                0 promotional / anonymous web
  fitness       is this the right kind of source for the way it is used?
                (media reporting an event = 3; media standing in for an
                unpublished judgment or a secondhand transcription = 2;
                mismatch = 0-1)
  load          3 argument anchor — a section falls without it
                2 direct evidence for specific claims
                1 context / supporting · 0 uncited
  independence  3 independent academic / enacted statute / independent court
                2 institutional viewpoint, commercial vendor, independent media
                1 party to the events cited (enforcement agency, regulator,
                  disputant), conflicted author, state media
                0 promotional
  recency_fit   3 current for the claim, or a classic used as a classic
                (the default; set it lower only where staleness is a real risk)

Derived here rather than stored, so they cannot go out of date: year and
language from the bib entry, citation count and citing files from the unit's
.qmd, key family (the prefix before the first underscore).

Composite = 3*load + 2*fitness + authority + independence + recency_fit (/24).
It only ranks; the WORKLISTS are the actionable output:

  UPGRADE / CORROBORATE     load>=2 and authority<=1
  POSITION-EVIDENCE CHECK   load>=2 and independence<=1
  TRANSCRIPTION RISK        fitness<=2 and load>0
  STALE RISK                recency_fit<=1
  PARK / CUT                load==0

## The sidecar, and why `load` is the one axis per unit

`bib-scores.yml` sits beside the `references.bib` it scores, one per tier:
`<unit>/bib-scores.yml` and `library/bib-scores.yml`. A unit's entry overrides
the library's axis by axis, because four of the axes are facts about the source
that every unit inherits, while `load` is a fact about *one manuscript* — the
same source can anchor the final paper and be background in the midterm. Same
split as the audit log, where an `identity` line carries no unit and a `support`
line must.

Format is a strict YAML subset — two-space indent, `key: value`, full-line `#`
comments, no inline comments, no quoting — parsed here so the framework keeps
its no-dependency rule:

    schema: 1
    entries:
      strange_persistent_1987:
        class: academic        # academic|book|wp|primary|industry|thinktank|policy|media|web
        perspective: academic  # academic|intl-org|<x>-gov|industry|thinktank|media-<x>|web
        authority: 3
        fitness: 3
        load: 3
        independence: 3
        note: structural-power anchor
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _paths import course_root, library, rel, resolve_unit  # noqa: E402

AXES = ("authority", "fitness", "load", "independence", "recency_fit")
DEFAULTS = {"recency_fit": 3}
SIDECAR = "bib-scores.yml"


def parse_bib(path: Path) -> dict[str, dict]:
    """Minimal .bib parser: key -> {type, year, title}."""
    entries: dict[str, dict] = {}
    key = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"@(\w+)\{([^,]+),", line.strip())
        if m:
            key = m.group(2).strip()
            entries[key] = {"type": m.group(1).lower(), "year": None, "title": ""}
            continue
        if key is None:
            continue
        fm = re.match(r"\s*(year|title)\s*=\s*\{(.*)\},?\s*$", line)
        if fm:
            field, val = fm.group(1), fm.group(2).rstrip("},").strip()
            if field == "year":
                ym = re.search(r"\d{4}", val)
                entries[key]["year"] = int(ym.group()) if ym else None
            else:
                entries[key]["title"] = val
    return entries


def parse_sidecar(path: Path) -> tuple[dict, dict[str, dict]]:
    """Parse the strict YAML subset: header scalars + an `entries:` mapping."""
    header: dict = {}
    entries: dict[str, dict] = {}
    current: dict | None = None
    in_entries = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if indent == 0:
            in_entries = line == "entries:"
            if not in_entries and ":" in line:
                k, v = line.split(":", 1)
                header[k.strip()] = v.strip()
            current = None
        elif in_entries and indent == 2 and line.endswith(":"):
            current = {}
            entries[line[:-1].strip()] = current
        elif in_entries and indent >= 4 and current is not None and ":" in line:
            k, v = line.split(":", 1)
            v = v.strip()
            current[k.strip()] = int(v) if v.isdigit() else v
        else:
            sys.exit(f"{path}: unparseable line: {raw!r}")
    return header, entries


def count_citations(unit: Path) -> dict[str, Counter]:
    """key -> Counter of the unit's .qmd files where @key appears.

    Same file set as check-citations (every .qmd except generated `_` files),
    so a key counted here is a key that gate also sees.
    """
    cites: dict[str, Counter] = defaultdict(Counter)
    for qmd in sorted(unit.rglob("*.qmd")):
        if any(part.startswith(("_", ".")) for part in qmd.relative_to(unit).parts):
            continue
        label = qmd.stem.split("-")[0].lstrip("0") or qmd.stem
        text = re.sub(r"<!--.*?-->", "", qmd.read_text(encoding="utf-8"), flags=re.S)
        for m in re.finditer(r"@([A-Za-z][\w]+)", text):
            cites[m.group(1)][label] += 1
    return cites


def bar(n: int, total: int, width: int = 30) -> str:
    return "█" * max(1 if n else 0, round(width * n / max(total, 1)))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("unit", nargs="?", help="unit path or name; default: the nearest one")
    ap.add_argument("--table", action="store_true", help="print the full per-entry table")
    args = ap.parse_args()

    root = course_root()
    unit = resolve_unit(args.unit)
    lib = library(root)

    # Library first, unit second: the unit's own judgment wins, axis by axis.
    tiers = [(lib / "references.bib", lib / SIDECAR), (unit / "references.bib", unit / SIDECAR)]
    bib: dict[str, dict] = {}
    home: dict[str, Path] = {}
    scores: dict[str, dict] = {}
    sidecars: list[Path] = []
    for bib_file, sidecar in tiers:
        if bib_file.is_file():
            for key, info in parse_bib(bib_file).items():
                bib.setdefault(key, info)          # duplicates are check-citations' job
                home.setdefault(key, bib_file.parent)
        if sidecar.is_file():
            sidecars.append(sidecar)
            for key, axes in parse_sidecar(sidecar)[1].items():
                scores.setdefault(key, {}).update(axes)

    if not bib:
        sys.exit(f"no references.bib in {rel(unit, root)}/ or {rel(lib, root)}/")
    if not sidecars:
        print(f"no {SIDECAR} yet for {rel(unit, root)}.\n\n"
              f"The axes are judgments, so there is nothing to derive them from: write\n"
              f"{rel(unit / SIDECAR, root)} by hand (see this command's --help for the\n"
              "format and what each axis means), scoring the keys that carry the argument\n"
              "first. Keys with no entry score 0 on every axis but recency_fit.")
        return

    cites = count_citations(unit)
    # A library entry this unit never cites belongs to another unit's profile.
    keys = sorted(k for k in bib if home[k] != lib or k in cites)

    missing = [k for k in keys if k not in scores]
    extra = sorted(set(scores) - set(keys))
    if missing:
        print(f"⚠ {len(missing)} bib key(s) with no {SIDECAR} entry: {', '.join(missing)}")
    if extra:
        print(f"⚠ {len(extra)} {SIDECAR} key(s) not in scope for this unit: {', '.join(extra)}")

    rows = []
    for key in keys:
        s = scores.get(key, {})
        ax = {a: int(s.get(a, DEFAULTS.get(a, 0))) for a in AXES}
        n = sum(cites.get(key, {}).values())
        chs = ",".join(sorted(cites.get(key, {}), key=lambda c: (len(c), c)))
        composite = (3 * ax["load"] + 2 * ax["fitness"]
                     + ax["authority"] + ax["independence"] + ax["recency_fit"])
        rows.append({
            "key": key, "class": s.get("class", "?"), "persp": s.get("perspective", "?"),
            "year": bib[key]["year"], "zh": bool(re.search(r"[一-鿿]", bib[key]["title"])),
            "n": n, "chs": chs, "note": s.get("note", ""), "score": composite, **ax,
        })

    total_cites = sum(r["n"] for r in rows)
    print(f"BIB QUALITY PROFILE — {rel(unit, root)} · {len(rows)} entries · "
          f"{total_cites} citations")
    print("Axes: " + " · ".join(rel(s, root) for s in sidecars) + "  (facts: derived)\n")

    def dist(field: str, weight: str | None = None) -> list[tuple[str, int]]:
        c: Counter = Counter()
        for r in rows:
            c[str(r[field])] += r["n"] if weight == "cites" else 1
        return c.most_common()

    print("PORTFOLIO")
    for label, field in (("class mix", "class"), ("perspective", "persp")):
        print(f"  {label} (entries · citation-weighted):")
        weighted = dict(dist(field, "cites"))
        for name, n in dist(field):
            w = weighted.get(name, 0)
            print(f"    {name:<10} {n:>3} ({n/len(rows):>4.0%})  ·  "
                  f"{w:>3} cites ({w/max(total_cites,1):>4.0%})")
    years = [r["year"] for r in rows if r["year"]]
    if years:
        print("  year:")
        newest = max(years)
        bands = [(f"≤{newest-12}", lambda y: y <= newest - 12),
                 (f"{newest-11}–{newest-5}", lambda y: newest - 11 <= y <= newest - 5),
                 (f"{newest-4}–{newest-2}", lambda y: newest - 4 <= y <= newest - 2),
                 (f"{newest-1}", lambda y: y == newest - 1),
                 (f"{newest}", lambda y: y == newest)]
        for label, pred in bands:
            n = sum(1 for y in years if pred(y))
            print(f"    {label:<10} {n:>3}  {bar(n, len(rows))}")
    zh_n = sum(1 for r in rows if r["zh"])
    print(f"  language of source: zh {zh_n} ({zh_n/len(rows):.0%}) · non-zh {len(rows)-zh_n}")
    fam: Counter = Counter()
    for r in rows:
        fam[r["key"].split("_")[0]] += r["n"]
    print("  citation concentration by source family (top 8):")
    for name, n in fam.most_common(8):
        keys_n = sum(1 for r in rows if r["key"].split("_")[0] == name)
        print(f"    {name:<12} {n:>3} cites ({n/max(total_cites,1):>4.0%}) "
              f"across {keys_n} key(s)")

    def worklist(title: str, cond, hint: str) -> None:
        hits = [r for r in rows if cond(r)]
        print(f"\n  {title} — {len(hits)}  ({hint})")
        for r in sorted(hits, key=lambda r: -r["n"]):
            note = f" — {r['note']}" if r["note"] else ""
            print(f"    {r['key']:<38} A{r['authority']} F{r['fitness']} L{r['load']} "
                  f"I{r['independence']} · {r['n']:>2}× [{r['chs']}]{note}")

    print("\nWORKLISTS")
    worklist("UPGRADE / CORROBORATE", lambda r: r["load"] >= 2 and r["authority"] <= 1,
             "load-bearing but low-tier: find a stronger source or add a primary corroborant")
    worklist("POSITION-EVIDENCE CHECK", lambda r: r["load"] >= 2 and r["independence"] <= 1,
             "load-bearing + party/conflicted: the text must frame it as that party's "
             "position or action")
    worklist("TRANSCRIPTION RISK", lambda r: r["fitness"] <= 2 and r["load"] > 0,
             "secondhand or mirrored text: keep the 轉述／轉引 flag, replace when the "
             "original publishes")
    worklist("STALE RISK", lambda r: r["recency_fit"] <= 1,
             "data presented as current may have aged out")
    worklist("PARK / CUT", lambda r: r["load"] == 0, "uncited — remove it or justify keeping it")

    if args.table:
        print("\nFULL TABLE (sorted by composite /24)")
        print(f"  {'key':<38} {'class':<10} A F L I R  score  cites  files")
        for r in sorted(rows, key=lambda r: (-r["score"], r["key"])):
            print(f"  {r['key']:<38} {r['class']:<10} {r['authority']} {r['fitness']} "
                  f"{r['load']} {r['independence']} {r['recency_fit']}   {r['score']:>2}    "
                  f"{r['n']:>3}   {r['chs']}")


if __name__ == "__main__":
    main()
