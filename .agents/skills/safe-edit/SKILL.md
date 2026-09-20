---
name: safe-edit
description: >
  Batch-edit discipline for manuscript text in a unit. Use for any multi-spot
  prose edit: gap-filling, framing fixes, terminology sweeps, table updates, or
  applying accepted flow-check / gpt-review findings. Authors an exact-match
  JSON payload, applies it with ./fw apply-edits (validate all, then write
  all), then runs the gates: readability ratchet, 簡繁 variants, count-zh,
  check-citations. Defines what must not change (「」 quotes, 《》 titles, [@key]
  locators, hypothesis wording).
---

# safe-edit — 語料庫批次編輯紀律

Every multi-spot edit to `<unit>/` goes through the same three stages: payload →
engine → gates. The point is that a drifted anchor, an ambiguous match, or a
readability regression is caught by machinery, not by rereading.

**Per-unit values.** Several things this skill protects differ from unit to
unit, so read them before the first batch rather than assuming: the
hypothesis or research-question labels and their exact wording (from the
unit's theory or framing section), which chapters are summary chapters, the
readability ceiling (one `./fw lint-readability <unit> --all` run *before*
editing — its worst score is the ratchet), and the word budget (the unit's
outline, or the requirement in `COURSE.md`). Skip a gate whose input the unit
doesn't have — a homework has no citations to check — rather than inventing
the input. The discipline (payload → engine → gates, immutables, evidence
rules) is the same everywhere.

## 1. Payload (scratchpad, one-shot)

A JSON file mapping each target file to `[old, new]` pairs:

```json
{
  "units/03-paper-final/chapters/05-case.qmd": [
    ["exact existing text …", "replacement text …"]
  ]
}
```

- **Anchors are verbatim and unique.** Copy `old` from the file (grep it out;
  never retype CJK from memory). If a phrase recurs, extend the anchor until
  it is unique — including an adjacent `[@key]` citation is the usual trick.
- **One batch = one payload**, kept in the session scratchpad. Payloads are
  disposable; they are *not* committed (the git diff is the record).
- Payload paths are relative to the course root, where `./fw` runs.

## 2. Engine

```
./fw apply-edits payload.json --check   # validate only
./fw apply-edits payload.json           # validate all, then write all
```

Guarantees: each anchor matches exactly once (0 → drifted, >1 → ambiguous;
either aborts); nothing is written unless every pair in every file validates;
UTF-8 in/out. A failed batch therefore never leaves the corpus half-edited.

**When a batch is rejected, repair the payload and re-run the whole batch.**
Don't split out the pairs that validated and apply them on their own: pairs
travel together because they are usually one change seen in several places (a
term renamed in two chapters, a claim and its mirror in the summary chapter),
and applying half of it by hand recreates exactly the half-edited corpus the
engine refuses to produce. For a drifted anchor, re-copy it from the file; for
an ambiguous one, extend it (usually with the adjacent `[@key]`) when the
author has said which occurrence they mean, and ask when they haven't —
different occurrences sit under different citations, so the choice changes
what a source is made to say. The file stays untouched while you wait.

The readability gate reads `<unit>/chapters/*.qmd` plus the work's entry file
(`index.qmd`, `paper.qmd`, `homework.qmd`, or `preparation.qmd`).

## 3. Immutables (do not edit, route around)

- Text inside 「」 direct quotes and 《》 titles — verbatim constraints
  (house-style `content-integrity` rules; a quoted official term keeps the
  source's own lexicon even where fix-terms would otherwise correct it).
- `[@key, locator]` citations — never change a key or locator as a side
  effect of rewording. New claims need new verified locators (below).
- Hypothesis or research-question wording and operationalization language —
  fixed where the unit first states them; every other chapter quotes them
  rather than paraphrasing, because a paraphrase that drifts is a different
  hypothesis by the time an examiner compares chapters.

## 4. Gates (run after every batch, in this order)

1. `./fw lint-readability <unit> --all` — **ratchet: no new
      sentence may score above the pre-edit corpus max.** Dominant failure mode
   in fresh prose: long pre-modifiers before 的+noun (P1) and ≥28-char
   no-pause runs (P3). Fix by splitting sentences or adding 、/，pauses.
2. `./fw check-zh-variants <unit>`
   — 簡繁與異體碼位的**源頭**檢查（簡體字＋内/爲/録/値 型異體＋Unicode 相容
   區）。scope 是寫作源檔（chapters/*.qmd 與頂層 *.qmd）；refs/ 逐字轉錄不掃。
   刻意示範簡體字形的行，行尾加 `<!-- zh-source-ok -->` 豁免；無網路時
   `python3` 直跑仍可做異體／相容碼位層。
3. `./fw count-zh <file>` — stay inside the unit's word budget (its outline,
   or the limit in `COURSE.md`). 嚴禁湊字數: padding to reach a count is worse
   than being under it.
4. `./fw check-citations <unit>` — must stay green.
5. `./fw check-bib <unit>` only if citations were touched.
6. **No per-batch PDF builds.** One `./fw build` at the end of the
   workstream, before the closing commit.

## 5. Evidence rules for new prose

- Summary and framework chapters (introduction, theory, design, comparison,
  conclusion — whichever the unit has) may only restate
  claims already established in body chapters, reusing identical
  `[@key, locator]` citations (claim-mirroring — keeps `support:backed`
  audit verdicts valid).
- A genuinely new claim from an already-backed fulltext is allowed in body
  chapters, but each quote must be grep-verified against the
  source's `refs/<key>.md` transcript (in the unit, or in `library/` once
  promoted), the locator mapped via the `[Page N start]` markers, and a `support`
  entry carrying this unit's name appended to the source's
  `refs/audit/<key>.jsonl`, recording what was verified.
- Party or conflicted sources keep their framing markers (指控／認定／官方所稱／
  據某機構／依媒體轉述), so a reader can always tell an allegation from a
  finding.
