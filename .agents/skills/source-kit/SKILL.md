---
name: source-kit
description: >
  Acquires, stores, and audits the sources behind cited academic work. Use when
  adding references.bib entries, fetching fulltext into <unit>/refs/, a URL
  returns 403 or a challenge page, mapping claims to sources before a draft, or
  reviewing whether a source actually supports its claim. Covers think-tank
  landing pages, blocked hosts (robust-web-fetch), and recording
  identity/support verdicts to <unit>/refs/audit/<key>.jsonl for the bib-quality
  ratchet. Use for /bib_audit, "audit the bib", "稽核來源".
user-invocable: true
---

# source-kit — source acquisition + audit

Owns everything between *"a citation key exists in `<unit>/references.bib`"* and
*"the claim it supports is verified against local fulltext."* The pipeline:

```
acquire → store → audit (before drafting) → [draft] → review (after drafting)
                        ↘ record verdicts to refs/audit/<key>.jsonl, ratchet the level (§7)
```

## When to use

- A new entry is added to `<unit>/references.bib` and its fulltext must be saved.
- A think-tank / CDN URL won't fetch (403, "Just a moment…", challenge page).
- Building a claim-to-source map before an evidence-heavy draft.
- Reviewing whether each cited claim is actually backed by its local source.

**Pairs with**

- **cite-check** — mechanical format + key consistency (the *gate*). source-kit
  checks whether a source *supports* a claim; cite-check checks the citation's
  *form*. Run cite-check last, never as the only review.
- **house-style** `reference/content-integrity.md` — the integrity rules cited
  claims must honor (disputed claims stay disputes, speculation labeled,
  citations stay attached, do-not-misphrase, match source language).

## 0. Where a source lives — unit first, library on reuse

A course repo has two tiers, and a source's files exist in exactly one of
them:

| Tier | Path | Holds |
| :--- | :--- | :--- |
| Unit | `<unit>/references.bib`, `<unit>/refs/` | sources only this unit uses — the default for anything new |
| Library | `library/references.bib`, `library/refs/` | sources two or more units cite, and assigned course readings |

- **Look before you fetch.** Search `library/references.bib` and the other
  units' bib files for the work first. Keys are unique across the course repo,
  and `./fw check-citations` fails on a duplicate — a second copy of a source
  means a second, diverging audit history.
- **New sources land in the unit.** Scans pull in many sources that never get
  cited; the library stays useful only if it holds what is actually shared.
- **Promote on reuse:** `./fw refs promote <key>` moves the transcript, the
  audit log, the bib entry, and the manifest line into `library/` in one
  `git mv`. Run it when a second unit wants the source; never copy the files.
- Below, `<unit>/refs/…` means the source's current home — read `library/refs/…`
  for a promoted source.

## 1. Acquire & store

When a new entry lands in `<unit>/references.bib`, save its fulltext under
`<unit>/refs/` so `para.` and `p.` locators can be verified during writing.
Markdown (`<unit>/refs/<citation_key>.md`) is the preferred form.

1. Fetch the source from the `url` or `doi` field in the bib entry.
1. **PDFs** → `<unit>/refs/<citation_key>.pdf`. PDF→Markdown conversion is out of
   scope here — use the **`pdf-to-markdown`** skill if your agent has it (same
   `enstw/skill-jz` source as robust-web-fetch; page-marked output, OCR
   fallback).
1. **Other types** (DOCX, HTML save, EPUB) → save the fulltext directly as
   `<unit>/refs/<citation_key>.md`, preserving paragraph structure.
1. **Paywalled / inaccessible** → create `<unit>/refs/<citation_key>.md` noting
   that, with whatever metadata is available (title, abstract, etc.). Do **not**
   fabricate content.

**Originals are not tracked in git.** The raw fulltext files (`*.pdf`, `*.epub`,
`*.html`) under `<unit>/refs/` are gitignored; their bytes live in a GitHub
Release managed by `./fw refs-snapshot`, pinned by the committed
`MANIFEST.tsv` beside the originals (path + sha256 + release tag; one Release
per course repo). Transcripts (`*.md`)
and audit logs (`audit/*.jsonl`) stay in git.

- After fetching a new original: `./fw refs-snapshot push`, then commit
  the updated `MANIFEST.tsv` alongside the bib/transcript change.
- To verify a source against its transcript on a machine without the file:
  `./fw refs-snapshot pull <key>` (sha256-verified on download).
- `./fw refs-snapshot status` shows missing/modified originals. Sources
  are immutable — a `MODIFIED` verdict means something is wrong; investigate,
  never re-push over it silently.

Two live tracking files are scaffolded into `<unit>/refs/` — they hold the full
conventions, so follow them rather than duplicating here:

- **`DOWNLOADS.md`** — the job queue: what's still to fetch, why each blocked
  entry is blocked, Wayback snapshot IDs, and which robust-web-fetch tier won.
- **`README.md`** — current retention: what is *now* local (full text / PDF /
  landing-page-only / inaccessible / deprecated). Do not track PDF→Markdown
  progress here; that's pdf2md's concern.

## 2. When the source is behind a CDN

When `curl`, `wget`, or a built-in fetcher returns 403 or a "Just a moment…"
challenge, use the **`robust-web-fetch`** skill if your agent has it (install via
`pnpm dlx skills add enstw/skill-jz --skill robust-web-fetch`). It escalates
curl-cffi → Wayback → Chromium print → camoufox; with `--html-fallback` it
writes a Markdown rendering when the PDF itself can't be retrieved. Record the
winning tier in `DOWNLOADS.md` Notes so a re-fetch skips dead ends.

## 3. Landing page vs. direct asset URL

Think-tank citation URLs (CSIS, RAND, CNAS, FDD, …) almost always point to a
**landing page** (HTML abstract + download button), not the report PDF. Before
fetching:

1. Decide what the claim needs. A landing-page abstract rarely backs a
   substantive claim — if the citation supports a specific argument, you need the
   report body.
1. **Parse the landing-page DOM for the underlying asset URL** (typical patterns:
   `csis-website-prod.s3.amazonaws.com/.../<slug>.pdf`,
   `s3.us-east-1.amazonaws.com/files.cnas.org/.../<slug>.pdf`,
   `rand.org/content/dam/rand/pubs/.../<slug>.pdf`) and fetch *that*. S3/CDN PDFs
   usually clear robust-web-fetch tier 1 (curl-cffi); landing pages often need
   Wayback or camoufox. Skipping this produces silent "full text"
   classifications that are really abstract shells.
1. Record **both** URLs: citation URL (landing page) in the bib `url =`; direct
   asset URL as a `% Direct report PDF: <url>` comment above the entry and in
   `DOWNLOADS.md`. In `README.md`, distinguish `Landing page markdown` from
   `Full text markdown` — landing-page-only is *not* full text.

## 4. Bib metadata

For sources with a visible "last updated" timestamp on the page, the bib
`date =` should be the source's **own update date**, not a Wayback snapshot date
or your fetch date. Snapshot IDs live in `DOWNLOADS.md` Notes, not in the bib.

## 5. Source audit — BEFORE long drafts

For journal, thesis, and evidence-heavy homework or policy analysis, audit
sources *before* drafting. Do **not** write the full argument first and verify
afterward.

1. Build a **claim-to-source map** for the core argument.
1. Separate source roles:
   - **Incident facts** → direct reports, official releases, datasets, court
     filings, primary news reports.
   - **Official policy / law / guidance** → government, regulator, agency, or
     institutional documents.
   - **Think-tank / scholarly interpretation** → framing and analysis, *not* a
     substitute for incident or policy facts.
1. Confirm each central claim has ≥1 source that is reachable, correctly titled,
   and precise enough for the claim being made.
1. Record retention status in `<unit>/refs/README.md` (full text / PDF only /
   source-role note / inaccessible / deprecated).
1. If the audit changes the actual corpus, update the **title, methodology,
   bibliography, and comparison dimensions together** before expanding the draft.
1. When a source contributes a framework but you reject part of its argument
   (adopt its lens, not its specific event attributions), state the **scope of
   adoption** in-text where the citation appears, so a reader can't assume the
   rest came along.

## 6. Source review — AFTER drafting

Reviewing references means cross-reading each cited claim against the local
`<unit>/refs/<key>.md`/`.pdf` — **not** just running `check-citations.py`. The
script confirms keys resolve; it does not confirm the source supports the claim.

1. For each citation, open the ref file and locate the supporting passage. If the
   local file is a landing-page abstract (not the report body), treat support as
   **unverified** until the report PDF is fetched (§3).
1. Watch for silent gaps: landing-page md mislabeled `Full text markdown` in
   `README.md`, citation URLs that now redirect elsewhere, or `date =` fields
   that no longer match the source's current update timestamp.
1. Run **cite-check** (`./fw check-citations <unit>`) **last**, as a
   consistency pass — never as the only review.

## 7. Recording verdicts & the bib-quality ratchet — `/bib_audit`

The audit (§5) and review (§6) produce **judgments**, not just prose. Record each
as an append-only line in the per-key log `<unit>/refs/audit/<key>.jsonl` — one file
per source, never rewritten (a correction is a new line with a later `ts`). This
is the machine source of truth `./fw check-bib` reads; there is no
consolidated report. Full model + schema: `docs/bib-lifecycle.md`.

Two verdict kinds:

- **`identity`** — is the local transcript the cited work *itself*? `genuine` ·
  `review-of` (a review/summary **of** the work — the wrong document) · `stub`
  (right work, too thin) · `wrong-file` · `missing`.
- **`support`** — does it back the claim? `backed` · `weak` · `contradicts`.
  A support line always carries `"unit":"<unit-name>"`: support is a judgment
  about one claim in one unit, so `./fw check-bib <unit>` counts only that
  unit's lines. An `identity` line has no unit — it is a fact about the source
  and every unit inherits it, which is why a promoted source is never
  re-audited for identity.
  Record a `support` verdict only against a transcript whose newest `identity`
  is `genuine`. When the local file is a review, a stub, or the wrong file,
  you have not read the cited work, so any support verdict — including
  `contradicts` — would be a judgment about some other document, and it would
  sit in the log as the key's support state after the real text replaces the
  file. Put what the wrong document says in the `identity` line's `evidence`
  and in your reply to the author instead.

```json
{"ts":"2026-07-06T17:04:10+08:00","actor":"<model/person>","key":"<key>","check":"identity","verdict":"genuine","evidence":"<pages checked / why>"}
```

Take `ts` from the clock at write time (`date +%Y-%m-%dT%H:%M:%S%z`) rather
than composing it by hand. Current state is "newest line per `check`", so a
hand-written timestamp that lands in the future is the one mistake a later
correction line cannot supersede — it keeps winning until real time passes it.
If you do write one, fix it before the file is committed and tell the author
you did; once committed, the file is append-only with no exceptions.

**The loop (drive it with the ratchet, don't audit blind):**

1. `./fw check-bib <unit> --todo` → the exact keys blocking the next quality
   level (L1 has-local-text → L2 genuine-identity → L3 locators-backed → L4
   claims-supported).
1. For each blocking key, **actually open the transcript** and judge. Fan-out is
   safe: one subagent per key, each appends to its own `audit/<key>.jsonl` — the
   per-key partition means concurrent auditors never conflict.
1. Append the verdict line(s). **Honesty guard — before you may write
   `identity: genuine`:** confirm the transcript's title/container matches the
   bib entry and is not headed "Review of…". A byte-clean transcript is *not*
   proof of identity; a review of the work passes every mechanical check, so only
   this judgment catches it. When unsure, write `review-of`/`stub`, not `genuine`.
1. `./fw check-bib <unit> --assert=L<n>` to confirm the level clears, then
   raise `required_bib_level` in `WORK.json` so the floor ratchets and dirt can't
   re-enter.
