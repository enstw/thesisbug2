#!/usr/bin/env python3
"""Bib source-management gate + lifecycle tracker.

Complements ``check-citations.py``. That script is the *consistency* gate (keys
resolve, format is clean, nothing unused). This one is the *source-backing* gate
and the *lifecycle* view — is every cited source actually on disk as usable full
text, has its identity and claim-support been judged, and do its page locators
resolve?

Lifecycle states, in pipeline order, from the state machine in
``docs/bib-lifecycle.md``:

  found       entry present in references.bib (author/title/year)
  downloaded  original retained under refs/archive/<key>.* (or provenance "saved")
  transcribed a local refs/<key>.md exists that looks like full text (filesystem)
  audited     newest `identity` verdict in refs/audit/<key>.jsonl is `genuine`
  reviewed    newest `support`  verdict in refs/audit/<key>.jsonl is `backed`
  cited       referenced by a [@key] in a .qmd  (else: unused)

Authority: `transcribed`/`downloaded`/`cited` are filesystem/grep FACTS.
`audited`/`reviewed` are recorded human/agent JUDGMENTS, read from the per-key
append-only audit log `refs/audit/<key>.jsonl` (one JSON object per line; current
state = newest line per `check`). There is no consolidated audit report — this
script's `--lifecycle` output IS the rollup, generated on demand.

Enforcement (non-zero exit), keyed off the audit-log identity verdict:
  · identity `review-of` / `wrong-file` on a cited key  → error (wrong document)
  · a `[@key, N]` page locator whose source is not `genuine`, or whose markers
    don't cover N → error (unbacked)
  · a cited key with no local refs/<key>.md               → error (missing)
Advisories (exit 0): bare-cite `stub`/`missing`, cited-but-unaudited,
cited-but-not-`reviewed=backed`, relative/offset-marker locators, log-vs-
filesystem drift.

Usage:
  ./fw check-bib [<unit>]                # gate + lifecycle summary for one unit
  ./fw check-bib [<unit>] --lifecycle    # + full per-key lifecycle table
  ./fw check-bib --library               # state of the shared library (no level)
  ./fw check-bib [<unit>] --audit        # append-only guard: no committed
                                         #   refs/audit/<key>.jsonl line was
                                         #   edited or removed (diff vs HEAD)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import course_root, library, list_units, rel, resolve_unit  # noqa: E402

# ── Patterns ─────────────────────────────────────────────────────────────────

CITE_KEY_RE = re.compile(r"(?<![\w@])@([a-zA-Z0-9_:.-]+)")
PAGE_MARKER_RE = re.compile(r"(?:第\s*(\d+)\s*頁開始|Page\s+(\d+)\s+start)")

# Provenance phrases that mark a .md as NOT genuine full text (filesystem hint
# for the `transcribed` facet; the authoritative identity call is the audit log).
STUB_MARKERS = (
    "source-role note only", "全文不在本機", "metadata-only", "metadata + abstract",
    "summary note from", "structured summary", "source note initially prepared",
    "not transcribed here", "not freely available", "inaccessible",
)
DOWNLOADED_MARKERS = ("pdf saved", "full text markdown", "全文", "已取得", "epub 全文", "saved-pdf")
ARCHIVE_EXTS = (".pdf", ".epub", ".html", ".htm", ".txt", ".docx")

# Identity verdicts (refs/audit/<key>.jsonl, check=identity).
IDENTITY_WRONG_DOC = ("review-of", "wrong-file")   # never acceptable as the source
IDENTITY_THIN = ("stub", "missing")                # right work, insufficient text

LADDER = ["found", "downloaded", "transcribed", "audited", "reviewed"]
FACETS = LADDER + ["cited"]

# Bib-quality assertion ladder (cited keys only). Each level subsumes the prior;
# a level is met iff it has zero blockers. L0 (keys resolve in the .bib) is
# check-citations.py's gate; this script owns L1–L4. See docs/bib-lifecycle.md.
LEVELS = {
    1: "has-local-text",     # every cited key has a refs/<key>.md
    2: "genuine-identity",   # every cited key's newest identity verdict = genuine
    3: "locators-backed",    # every [@key, p] resolves against page markers
    4: "claims-supported",   # every cited key's newest support verdict = backed
}


def parse_level(s: str):
    """'L2' | '2' -> 2. Returns None if unparseable."""
    m = re.fullmatch(r"[Ll]?(\d+)", s.strip())
    return int(m.group(1)) if m else None


# ── Bib + citation parsing ───────────────────────────────────────────────────

def parse_bib_keys(bib_path: Path) -> dict[str, dict]:
    entries: dict[str, dict] = {}
    key, fields = None, set()
    for line in bib_path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"@(\w+)\{(.+?),", line)
        if m:
            if key:
                entries[key] = {"fields": fields}
            key, fields = m.group(2).strip(), set()
            continue
        m = re.match(r"\s*(\w+)\s*=", line)
        if m and key:
            fields.add(m.group(1).lower())
    if key:
        entries[key] = {"fields": fields}
    return entries


def find_locator_cites(qmd_dir: Path) -> dict[str, list[tuple[str, list[int], str]]]:
    """Return {key: [(rawspan, [pages], file), ...]}. Locators bind per-key
    inside a Pandoc [@a; @b, 7] multi-key span."""
    cites: dict[str, list[tuple[str, list[int], str]]] = {}
    for qmd in sorted(qmd_dir.rglob("*.qmd")):
        text = qmd.read_text(encoding="utf-8")
        for span in re.findall(r"\[[^\[\]]*@[^\[\]]*\]", text):
            for seg in span[1:-1].split(";"):
                m = CITE_KEY_RE.search(seg)
                if not m:
                    continue
                pages = [int(n) for n in re.findall(r"\d+", seg[m.end():])]
                cites.setdefault(m.group(1), []).append(
                    (span, pages, str(qmd.relative_to(qmd_dir))))
    return cites


# ── Per-key state detection ──────────────────────────────────────────────────

def classify_fulltext(md_path: Path) -> str:
    """Full-text facet: 'fulltext' | 'stub' | 'missing'.

    Authority order:
      1. file absent                               → 'missing'
      2. frontmatter ``local_status: fulltext|stub`` → the declared value wins
      3. STUB_MARKERS heuristic over the head        → fallback for un-migrated keys

    A declared ``local_status`` retires the heuristic *for that key*: the phrase
    scan is a guess (a stub note reads as prose once fleshed out, and vice-versa),
    so once a source is deliberately classified it should not be re-guessed. The
    heuristic remains only for keys that carry no ``local_status`` yet."""
    if not md_path.exists():
        return "missing"
    declared = read_frontmatter(md_path).get("local_status", "").strip().lower()
    if declared in ("fulltext", "stub"):
        return declared
    head = "\n".join(md_path.read_text(encoding="utf-8").splitlines()[:40]).lower()
    return "stub" if any(m in head for m in STUB_MARKERS) else "fulltext"


def provenance_line(md_path: Path) -> str:
    if not md_path.exists():
        return ""
    for line in md_path.read_text(encoding="utf-8").splitlines()[:40]:
        if line.lower().lstrip().startswith("provenance:"):
            return line.lower()
    return ""


def read_audit_log(refs_dir: Path, key: str, unit_name: str | None = None) -> dict[str, dict]:
    """Newest event per `check` from the append-only refs/audit/<key>.jsonl.

    `identity` is a fact about the source, so every unit inherits it. `support`
    is a judgment about one claim in one unit: with `unit_name` given, only
    support lines carrying that unit count — otherwise a verdict earned by the
    midterm would silently mark the final paper's different claim as reviewed.
    `unit_name=None` (the --library view) accepts support from any unit.
    """
    p = refs_dir / "audit" / f"{key}.jsonl"
    latest: dict[str, dict] = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            c = e.get("check")
            if c == "support" and unit_name is not None and e.get("unit") != unit_name:
                continue
            if c and (c not in latest or e.get("ts", "") > latest[c].get("ts", "")):
                latest[c] = e
    return latest


def page_marker_range(md_path: Path):
    if not md_path.exists():
        return None
    pages = [int(a or b) for a, b in PAGE_MARKER_RE.findall(md_path.read_text(encoding="utf-8"))]
    return (min(pages), max(pages)) if pages else None


FRONTMATTER_RE = re.compile(r"---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)


def read_frontmatter(md_path: Path) -> dict:
    """Flat leading YAML ``---`` block → dict of scalars. Only flat scalars are
    needed (``marker_offset``, ``local_status``), so no yaml dependency."""
    if not md_path.exists():
        return {}
    text = md_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        line = re.sub(r"\s+#.*$", "", line)   # strip inline YAML comment ( ` # …`)
        mm = re.match(r"\s*([A-Za-z_][\w-]*)\s*:\s*(.+?)\s*$", line)
        if mm:
            fm[mm.group(1)] = mm.group(2).strip().strip("\"'")
    return fm


def marker_offset(md_path: Path) -> int:
    """``printed_page = physical_marker + marker_offset``. 0 when unset — pdf2md's
    physical page markers (1..N) are then assumed to equal printed page numbers.
    Set it in refs/<key>.md frontmatter when the source's printed pages are offset
    from the physical PDF sequence (journal articles, Statutes-at-Large, Fed. Reg.)."""
    try:
        return int(read_frontmatter(md_path).get("marker_offset"))
    except (TypeError, ValueError):
        return 0


def has_local_original(archive_dir: Path, key: str) -> bool:
    return archive_dir.is_dir() and any(
        (archive_dir / f"{key}{ext}").exists() for ext in ARCHIVE_EXTS)


def compute_state(key, info, refs_dir, archive_dir, cites, unit_name=None) -> dict:
    md = refs_dir / f"{key}.md"
    ft = classify_fulltext(md)
    prov = provenance_line(md)
    audit = read_audit_log(refs_dir, key, unit_name)
    identity = (audit.get("identity") or {}).get("verdict")   # or None
    support = (audit.get("support") or {}).get("verdict")     # or None
    return {
        "found": {"title", "year"} <= info["fields"],
        "downloaded": has_local_original(archive_dir, key)
                      or any(m in prov for m in DOWNLOADED_MARKERS),
        "transcribed": ft == "fulltext",
        "audited": identity == "genuine",
        "reviewed": support == "backed",
        "cited": key in cites,
        "_ft": ft,
        "_md": md,
        "_identity": identity,
        "_support": support,
        "_marker_offset": marker_offset(md),
        "_page_cites": [(s, p, f) for s, p, f in cites.get(key, []) if p],
    }


# ── Append-only audit-log guard (--audit) ───────────────────────────────────

def _git(cwd: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args],
                          capture_output=True, text=True)


def _canonical_lines(text: str) -> list[str]:
    """One comparable token per non-blank line. JSON lines are re-serialised with
    sorted keys so whitespace / key-order churn is not read as a history edit;
    a line that will not parse falls back to its stripped raw form."""
    out = []
    for ln in text.splitlines():
        if not ln.strip():
            continue
        try:
            out.append("j:" + json.dumps(json.loads(ln), sort_keys=True))
        except json.JSONDecodeError:
            out.append("r:" + ln.strip())
    return out


def audit_append_only_check(refs_dir: Path) -> int:
    """``--audit``: enforce the append-only rule (docs/bib-lifecycle.md §Rules) by
    diffing every ``refs/audit/<key>.jsonl`` against its committed ``HEAD`` blob.
    A committed line may never be modified or removed — only new lines appended.
    Returns the number of tampered files (0 = clean)."""
    audit_dir = refs_dir / "audit"
    tl = _git(refs_dir if refs_dir.is_dir() else Path.cwd(), "rev-parse", "--show-toplevel")
    if tl.returncode != 0:
        print("--audit: not a git repository — no HEAD to diff against, nothing to enforce.")
        return 0
    repo_root = Path(tl.stdout.strip())

    def rel(p: Path) -> str:
        return os.path.relpath(p.resolve(), repo_root.resolve()).replace(os.sep, "/")

    audit_rel = rel(audit_dir)
    head_ls = _git(repo_root, "ls-tree", "-r", "--name-only", "HEAD", "--", audit_rel)
    head_files = {ln for ln in head_ls.stdout.splitlines() if ln.endswith(".jsonl")}
    wt_files = {rel(p) for p in audit_dir.glob("*.jsonl")} if audit_dir.is_dir() else set()

    violations = []
    for path in sorted(head_files | wt_files):
        show = _git(repo_root, "show", f"HEAD:{path}")
        committed = _canonical_lines(show.stdout) if show.returncode == 0 else []
        if not committed:
            continue  # new file (no committed history to protect) → all-append, allowed
        wt_path = repo_root / path
        key = Path(path).stem
        if not wt_path.exists():
            violations.append((key, f"deleted from working tree — {len(committed)} committed line(s) lost"))
            continue
        current = _canonical_lines(wt_path.read_text(encoding="utf-8"))
        if len(current) < len(committed):
            violations.append((key, f"{len(committed) - len(current)} committed line(s) removed "
                                    f"({len(committed)}→{len(current)} lines)"))
            continue
        edited = next((i for i, (c, w) in enumerate(zip(committed, current), 1) if c != w), None)
        if edited:
            violations.append((key, f"committed line {edited} was modified (history rewrite, not an append)"))

    if violations:
        print("APPEND-ONLY VIOLATIONS — a committed refs/audit/<key>.jsonl line was edited or removed:")
        for key, why in violations:
            print(f"  @{key}  ({why})")
        print(f"\n{len(violations)} audit log(s) violate append-only. A correction is a NEW line with a "
              "later `ts` (and optional `supersedes`), never an edit to a committed one "
              "(docs/bib-lifecycle.md §Rules).")
    else:
        print(f"--audit: append-only OK — {len(head_files)} committed audit log(s), no history edits.")
    return len(violations)


# ── Report ───────────────────────────────────────────────────────────────────

def main() -> None:
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a.split("=", 1)[0] for a in sys.argv[1:] if a.startswith("--")}
    assert_arg = None  # None=off · ""=use WORK.json · "L2"/"2"=explicit
    for a in sys.argv[1:]:
        if a == "--assert":
            assert_arg = ""
        elif a.startswith("--assert="):
            assert_arg = a.split("=", 1)[1]
    croot = course_root()
    lib = library(croot)
    lib_bib, lib_refs = lib / "references.bib", lib / "refs"
    library_view = "--library" in flags

    if library_view:
        root, unit_name = lib, None
        bib_files = [lib_bib]
        cite_roots = list_units(croot)          # "cited" = cited by any unit
    else:
        root = resolve_unit(argv[0] if argv else None)
        unit_name = root.name
        bib_files = [root / "references.bib", lib_bib]
        cite_roots = [root]
    bib_files = [b for b in bib_files if b.exists()]
    if not bib_files:
        print(f"ERROR: no references.bib in {rel(root, croot)}/ or library/")
        sys.exit(1)

    refs_dir = root / "refs"
    print(f"Checking bib sources: {', '.join(rel(b, croot) for b in bib_files)}")
    print(f"Scope: {'library (all units)' if library_view else 'unit ' + rel(root, croot)}\n")

    # --audit: standalone append-only integrity guard over the per-key logs,
    # in both tiers — a promoted source's history lives in library/refs/audit/.
    if "--audit" in flags:
        bad = sum(audit_append_only_check(d) for d in {refs_dir, lib_refs})
        sys.exit(1 if bad else 0)

    cites: dict = {}
    for cr in cite_roots:
        for k, v in find_locator_cites(cr).items():
            cites.setdefault(k, []).extend(v)

    # Each key's home tier decides where its transcript and audit log are read.
    entries, home = {}, {}
    for b in bib_files:
        for k, info in parse_bib_keys(b).items():
            if k in entries:
                continue                        # duplicates are check-citations' job
            entries[k], home[k] = info, b.parent / "refs"
    if not library_view:
        # A library entry this unit never cites is another unit's business.
        entries = {k: v for k, v in entries.items()
                   if home[k] != lib_refs or k in cites}

    states = {k: compute_state(k, entries[k], home[k], home[k] / "archive", cites, unit_name)
              for k in sorted(entries)}

    misident, missing, stub_locator = [], [], []
    stub_bare, unaudited, not_reviewed = [], [], []
    unbacked, unverified, no_markers, drift = [], [], [], []

    for key, st in states.items():
        cited, idv, page = st["cited"], st["_identity"], st["_page_cites"]

        # ── identity enforcement ──
        if cited and idv in IDENTITY_WRONG_DOC:
            misident.append((key, idv))
        elif cited and st["_ft"] == "missing":
            missing.append(key)
        elif cited and idv in IDENTITY_THIN:
            (stub_locator if page else stub_bare).append(key)
        elif cited and idv is None:
            unaudited.append(key)

        # support gate (advisory until the review pass populates it)
        if cited and st["_support"] != "backed":
            not_reviewed.append(key)

        # log-vs-filesystem drift (the metafile promise: verify, don't trust)
        if idv == "genuine" and st["_ft"] == "stub":
            drift.append((key, "log=genuine but .md reads as a stub"))
        elif idv in IDENTITY_THIN and st["_ft"] == "fulltext":
            drift.append((key, f"log={idv} but .md now reads as full text — re-audit?"))

        # ── page-locator backing (mechanical) ──
        for span, pages, f in page:
            if idv != "genuine":
                unbacked.append((key, span, f, f"identity={idv or 'unaudited'}"))
            else:
                rng = page_marker_range(st["_md"])
                if rng is None:
                    no_markers.append((key, span))
                    break
                off = st["_marker_offset"]          # printed = physical + off
                lo, hi = rng[0] + off, rng[1] + off
                out = [p for p in pages if not (lo <= p <= hi)]
                if out:
                    unverified.append(key)

    # ── quality-level ladder (cited keys only) ──
    cited_keys = [k for k, st in states.items() if st["cited"]]
    blockers = {
        1: sorted(k for k in cited_keys if states[k]["_ft"] == "missing"),
        2: sorted(k for k in cited_keys if states[k]["_identity"] != "genuine"),
        3: sorted(set(unverified) | {k for k, _ in no_markers}
                  | {r[0] for r in unbacked if states[r[0]]["_identity"] == "genuine"}),
        4: sorted(k for k in cited_keys if states[k]["_support"] != "backed"),
    }
    current_level = 0
    for lv in (1, 2, 3, 4):
        if blockers[lv]:
            break
        current_level = lv

    # ── --assert / --todo short-circuit before the full report ──
    if assert_arg is not None or "--todo" in flags:
        req = None
        if assert_arg not in (None, ""):
            req = parse_level(assert_arg)
        elif assert_arg == "":  # the ratchet is per unit: read it from the unit's WORK.json
            cand = root / "WORK.json"
            if cand.exists():
                req = json.loads(cand.read_text(encoding="utf-8")).get("required_bib_level")
        print(f"Bib quality: L{current_level} "
              f"({LEVELS.get(current_level, 'below L1')}) · {len(cited_keys)} cited keys")
        target = req if req is not None else min(current_level + 1, 4)
        show = range(current_level + 1, (req or 4) + 1) if assert_arg is not None else range(current_level + 1, 5)
        for lv in show:
            if lv > 4 or not blockers[lv]:
                continue
            print(f"\nL{lv} {LEVELS[lv]} — {len(blockers[lv])} key(s) blocking:")
            for k in blockers[lv][:40]:
                why = {2: states[k]["_identity"] or "unaudited",
                       4: states[k]["_support"] or "unreviewed"}.get(lv, "")
                print(f"  @{k}{'  (' + why + ')' if why else ''}")
            if len(blockers[lv]) > 40:
                print(f"  … +{len(blockers[lv]) - 40} more")
        if assert_arg is not None:
            ok = req is None or current_level >= req
            print(f"\nassert L{req if req is not None else '?'}: "
                  f"{'PASS' if ok else 'FAIL'} (at L{current_level})"
                  if req is not None else
                  "\nassert: no level given and no required_bib_level in WORK.json — nothing to assert")
            sys.exit(0 if ok else 1)
        sys.exit(0)

    errors = 0

    def sect(title, rows, fmt):
        if rows:
            print(title)
            for r in rows:
                print(fmt(r))
            print()

    # ── errors ──
    if misident:
        errors += len(misident)
        sect("MISIDENTIFIED SOURCE (cited, but audit says it is the WRONG document):",
             misident, lambda r: f"  @{r[0]}  (identity = {r[1]})")
    if missing:
        errors += len(missing)
        sect("MISSING FULL TEXT (cited, but no refs/<key>.md):", missing, lambda k: f"  @{k}")
    if unbacked:
        errors += len(unbacked)
        sect("UNBACKED PAGE LOCATORS (page cite whose source is not audited-genuine):",
             unbacked, lambda r: f"  @{r[0]} {r[1]}  <- {r[2]}  ({r[3]})")

    # ── advisories ──
    if stub_locator:
        sect("STUB + PAGE LOCATOR — advisory (thin source carrying a page claim; see UNBACKED):",
             stub_locator, lambda k: f"  @{k}")
    if stub_bare:
        sect("CITED STUB — advisory (bare whole-work cite of a right-work-but-thin source):",
             stub_bare, lambda k: f"  @{k}  ({provenance_line(states[k]['_md']).split('provenance:')[-1].strip()[:56]})")
    if unaudited:
        sect("CITED BUT UNAUDITED — advisory (no refs/audit/<key>.jsonl identity verdict):",
             unaudited, lambda k: f"  @{k}")
    if not_reviewed and "--lifecycle" in flags:
        print("CITED BUT NOT REVIEWED=backed — advisory (claim-support review pass not yet run):")
        print("  " + ", ".join(f"@{k}" for k in not_reviewed) + "\n")
    if drift:
        sect("LOG↔FILESYSTEM DRIFT — advisory (audit log disagrees with the .md; re-audit):",
             drift, lambda r: f"  @{r[0]}  ({r[1]})")
    if unverified:
        per_key = {}
        for k in unverified:
            per_key[k] = per_key.get(k, 0) + 1
        print("UNVERIFIED LOCATORS — advisory (genuine source; cited page falls outside the "
              "marker range — map printed↔physical with `marker_offset:` frontmatter in "
              "refs/<key>.md, or cite by ¶/section):")
        for k, c in sorted(per_key.items()):
            print(f"  @{k}  ({c} locator{'s' if c > 1 else ''})")
        print()
    if no_markers:
        sect("NO PAGE MARKERS (page-cited genuine source without printed-page markers — cite by chapter):",
             no_markers, lambda r: f"  @{r[0]}  (e.g. {r[1]})")

    # ── lifecycle view ──
    n = len(entries)
    cov = {f: sum(1 for st in states.values() if st[f]) for f in FACETS}
    scale = 60 / n if n else 0
    print("LIFECYCLE COVERAGE (keys reaching each state):")
    for f in FACETS:
        print(f"  {f:<12} {cov[f]:>3}/{n}  {'█' * round(cov[f] * scale)}")
    print(f"  {'unused':<12} {n - cov['cited']:>3}/{n}\n")

    if "--lifecycle" in flags:
        print("PER-KEY LIFECYCLE  (F=found D=downloaded T=transcribed A=audited R=reviewed · C=cited):")
        print(f"  {'key':<38} F D T A R  use   identity")
        for key, st in states.items():
            marks = " ".join("✓" if st[f] else "·" for f in LADDER)
            use = "cited" if st["cited"] else "unused"
            idv = st["_identity"] or "—"
            print(f"  {key:<38} {marks}  {use:<6} {idv}")
        print()

    ge = sum(1 for st in states.values() if st["audited"])
    print(f"Summary: {n} entries · {ge} audited-genuine · {cov['cited']} cited · "
          f"{len(misident)} misidentified · {len(unbacked)} unbacked · {errors} error(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
