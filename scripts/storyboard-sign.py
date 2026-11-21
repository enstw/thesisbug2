#!/usr/bin/env python3
"""Record the author's sign-off of what a storyboard says.

    ./fw storyboard-sign [<talk>]           write or refresh the 內容簽核 bullet in 前提
    ./fw storyboard-sign [<talk>] --check   exit 1 when the content no longer matches it

A talk is planned in two stages: the storyboard stage decides what each slide says,
and the design stage chooses or adds a layout for it without changing a word. The
sign-off is the line between them. It stores a fingerprint of the content (the
premises, and every column of every row except 版型 and 動態, reading the text of
畫面內容 rather than its slot names), and `./fw deck-compile` refuses a storyboard whose
content no longer matches, so a design pass that trims a row to fit a layout is caught.

Run it only after the author has read the storyboard (`./fw storyboard-review`) and
agreed, and again after each later change the author agrees to. It prints the density
the content was written at, because the author is told that choice at every sign-off.
Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _deck_content import (SIGN_KEY, SIGN_LINE, content_digest, density, sign_problem,  # noqa: E402
                           signed_digest, type_floor)
from _deck_outline import extract_storyboard_rows, with_premise  # noqa: E402
from _paths import course_root, find_talk, rel, resolve_unit  # noqa: E402

NOTE = "（./fw storyboard-sign 寫入；之後內容有改動，要作者同意後重新簽核）"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", nargs="?", help="a talk, or a unit whose storyboard.md sits at its root")
    ap.add_argument("--check", action="store_true", help="verify the recorded sign-off without writing")
    args = ap.parse_args()

    root = course_root()
    found = find_talk(args.target)
    talk = found[1] if found else resolve_unit(args.target)
    storyboard = talk / "storyboard.md"
    if not storyboard.is_file():
        sys.exit(f"no storyboard.md in {rel(talk, root)}")
    text = storyboard.read_text(encoding="utf-8")
    name = rel(storyboard, root)

    if args.check:
        if signed_digest(text) is None:
            print(f"{name}: not signed off yet (./fw storyboard-sign after the author agrees)")
            return 1
        problem = sign_problem(text)
        if problem:
            print(f"{name}: {problem}")
            return 1
        print(f"{name}: content matches its sign-off")
        return 0

    rows = extract_storyboard_rows(text)
    if not rows:
        sys.exit(f"{name} has no slide rows to sign off")
    line = f"- {SIGN_KEY}：{dt.date.today().isoformat()} · {content_digest(text)}{NOTE}"
    if signed_digest(text) is None:
        text = with_premise(text, line)
    else:
        text = SIGN_LINE.sub(lambda _: line, text, count=1)
    storyboard.write_text(text, encoding="utf-8")
    level, stated = density(text)
    print(f"{name}: signed off {len(rows)} rows")
    print(f"  密度：{level}" + ("" if stated else "（前提沒寫，採預設；請在前提寫下「密度：」與理由，讓作者看得到）"))
    print(f"  字級下限：{type_floor(text)}px")
    return 0


if __name__ == "__main__":
    sys.exit(main())
