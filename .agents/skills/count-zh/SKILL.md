---
name: count-zh
description: >
  Counts Chinese characters (字數) in a file with ./fw count-zh. Use when
  the user asks for 字數 / word count / character count, or when Chinese-language
  writing must be checked against a length limit. Counts CJK ideographs only,
  which is what a 字數 limit means; wc -w and len() mis-count Chinese, so use this
  instead of a hand-rolled count.
---

# count-zh — Chinese character (字數) count

The framework ships `./fw count-zh` (run from the course root). This skill is the entry point for "how many words / 字數" requests on Chinese-language work; the script is the implementation. **Run — and extend — `./fw count-zh` rather than counting 字數 by hand, with `wc`, or with `len()`; each gives the wrong number for Chinese (see below).**

## Why a dedicated tool

Chinese text has no spaces between words, so the usual reflexes are wrong:

- `wc -w` counts whitespace-delimited tokens → drastically **undercounts** Chinese.
- `len(text)` / a raw character count → **overcounts** (includes punctuation, English, digits, whitespace, markup).

`count-zh.py` counts **CJK Unified Ideographs only** (`[一-鿿]`), excluding punctuation, English letters, digits, and whitespace — which is what a 字數 limit on an assignment or journal actually means.

## Usage

```bash
./fw count-zh <file>        # prints the integer 字數 to stdout
```

- Count a draft: `./fw count-zh <unit>/homework.qmd`
- Check against a limit: run it, compare to the assignment's 字數 requirement, and report the gap.

## Notes

- It counts the **raw file**. Markdown/LaTeX/Quarto markup keywords are English, so they add no CJK and don't inflate the count — but Chinese inside YAML front matter (e.g. a Chinese `title:`) **does** count. For a strict body-only number, point it at the prose, not a generated wrapper.
- One file at a time. For a multi-chapter thesis, sum the per-file counts.
