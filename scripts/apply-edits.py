#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exact-match batch editor — the safe-edit engine.

Applies (old, new) replacement pairs to prose files with three guarantees:
  1. exact match  — each `old` string must appear EXACTLY once in its target
     file (0 = anchor drifted, >1 = ambiguous edit); anything else aborts
  2. all-or-nothing — every pair in every file is validated BEFORE any file
     is written, so a failed anchor never leaves the corpus half-edited
  3. utf-8 in/out — CJK-safe regardless of the platform's locale defaults

Payload format (JSON file, or `-` for stdin):
  {
    "units/03-paper-final/chapters/05-case.qmd": [
      ["old text …", "new text …"],
      ["another anchor", "its replacement"]
    ],
    "units/03-paper-final/outline.qmd": [ ... ]
  }
Paths are resolved relative to the current working directory (the course root).
An `old` equal to `new` is rejected (no-op pairs indicate a payload bug).

Usage:
  ./fw apply-edits payload.json          # validate + apply
  ./fw apply-edits payload.json --check  # validate only, write nothing
  ... | ./fw apply-edits -               # payload on stdin

Convention: payloads are one-shot and live in the session scratchpad (they
describe a single edit batch, not reusable logic); this engine is the part
that belongs in the repo. After applying, run the usual gates
(lint-readability, count-zh, check-citations).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_payload(src: str) -> dict[str, list[list[str]]]:
    raw = sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not payload:
        sys.exit("payload must be a non-empty object of {file: [[old, new], ...]}")
    return payload


def validate(payload: dict[str, list[list[str]]]) -> dict[Path, str]:
    """Check every pair against its file; return {path: edited_text} or abort."""
    staged: dict[Path, str] = {}
    errors: list[str] = []
    for file_str, pairs in payload.items():
        path = Path(file_str)
        if not path.is_file():
            errors.append(f"{file_str}: file not found")
            continue
        text = path.read_text(encoding="utf-8")
        for i, pair in enumerate(pairs):
            if not (isinstance(pair, list) and len(pair) == 2):
                errors.append(f"{file_str}[{i}]: pair must be [old, new]")
                continue
            old, new = pair
            if old == new:
                errors.append(f"{file_str}[{i}]: old == new (no-op pair)")
                continue
            n = text.count(old)
            if n != 1:
                errors.append(f"{file_str}[{i}]: expected 1 match, found {n}: {old[:50]!r}")
                continue
            text = text.replace(old, new)
        staged[path] = text
    if errors:
        for e in errors:
            print(f"ERROR  {e}", file=sys.stderr)
        sys.exit(f"aborted: {len(errors)} error(s), nothing written")
    return staged


def main():
    parser = argparse.ArgumentParser(description="Apply exact-match edit pairs (all-or-nothing)")
    parser.add_argument("payload", help="JSON payload file, or - for stdin")
    parser.add_argument("--check", action="store_true", help="validate only, write nothing")
    args = parser.parse_args()

    payload = load_payload(args.payload)
    staged = validate(payload)
    total = sum(len(v) for v in payload.values())
    if args.check:
        print(f"OK  {total} pair(s) across {len(staged)} file(s) — check only, nothing written")
        return
    for path, text in staged.items():
        path.write_text(text, encoding="utf-8")
        print(f"applied  {len(payload[str(path)])} pair(s) -> {path}")
    print(f"done  {total} pair(s) across {len(staged)} file(s)")


if __name__ == "__main__":
    main()
