---
name: cite-check
description: >
  Citation consistency gate for Quarto/Pandoc academic work (.qmd + .bib). Use
  for /check_cite, before a build or submission, or when the user asks to check
  citations / 引用格式 / 引用檢查 / 檢查引用. Runs ./fw check-citations (broken,
  unused, incomplete, duplicate keys; APA-zh split bib) instead of a hand-rolled
  grep, enforces [@key] format and p. / para. locators, and strips NotebookLM
  [loc] residue. Whether a source actually supports a claim is source-kit, not
  this.
---

# cite-check — citation hygiene gate

The mechanical citation gate for `.qmd` manuscripts. It checks that citations are
**well-formed and consistent** — it does *not* check that a source backs its
claim. That semantic check is **source-kit** § Source review; this skill is the
form check, and `house-style` `reference/content-integrity.md` rule 3 ("citations
stay attached to their claims") is the standard it enforces.

**Extend `./fw check-citations` (below) rather than hand-rolling a
grep/awk/python script to diff `[@key]`s against the `.bib`** — it already does it,
including the APA-zh split-bib case, and exits non-zero to fail the build.

## Format rules

- Use the **Quarto/Pandoc standard**: `[@citation_key]`.
- **Forbidden:** NotebookLM-generated `[loc]`, `Location`, or `Source X` labels.
  Strip any that survived a paste from NotebookLM.

## Locators (定位標示)

When a citation supports a specific point or datum, mark the position precisely:

- **PDF / book source** → `p. <page>` (e.g. `[@smith_2024, p. 15]`).
- **Web / HTML source** → `para. <paragraph>` (e.g. `[@cnn_report, para. 3]`).

## Run the consistency check

```bash
./fw check-citations <unit>        # exits non-zero if broken or incomplete
```

It checks all `<unit>/**/*.qmd` against both tiers — `<unit>/references.bib`
and `library/references.bib` — and reports four things (APA-zh units use the
same single bib; entries carry `langid` and the build groups 中文／西文):

| Class | Meaning | Fails build? |
| :--- | :--- | :--- |
| **Broken** | cited `[@key]` with no matching bib entry | yes |
| **Unused** | bib entry never cited | no (warning) |
| **Incomplete** | bib entry missing `author` / `title` / `year` | yes |
| **Duplicate** | same key in two places in the course repo — two units, or a unit and `library/` — so one source has two diverging audit histories; fix with `./fw refs promote <key>` | yes |

## What it does NOT do

It confirms citation keys resolve to bib entries; it does **not** confirm the
source actually supports the claim, nor that locators point at the right page.
Run this **last**, as a consistency pass — the substantive review (cross-reading
each claim against `<unit>/refs/<key>.md`) is **source-kit** § Source review. A
green `check-citations.py` over unverified sources is a false sense of safety.

Backs the `/check_cite` macro.
