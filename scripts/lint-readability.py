#!/usr/bin/env python3
"""Readability linter for over-condensed academic Chinese (過度精練偵測).

Flags the compression patterns that make prose hard to read, so a rewrite
pass can work from a ranked worklist instead of rereading 100k characters:

  P1 長前置定語   ≥12 CJK chars between a pause and a 「的＋名詞」 head —
                  the reader must hold the whole modifier before the noun.
  P2 名物化       「的」+ nominalized verb head (持有/維護/行使/回收…) —
                  the action is frozen into a noun; no live predicate.
  P3 無停頓長跑   ≥28 CJK chars with no pause punctuation at all.
  P4 超長句       sentence ≥110 CJK chars (dense multi-clause packing).
  P5 破折號嵌套   ≥2 「——」 insertions in one sentence (parenthetical stack).
  P6 量詞省略     numeral + counted noun without classifier (六節點-type).

Each flagged sentence gets a severity score = weighted pattern hits; output
is worst-first. Text inside 「」 quotes and 《》 titles is exempt (verbatim
constraint), as are headers, tables, comments, and code fences.

Usage:
  ./fw lint-readability [<unit>] [--top N] [--all]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import manuscript_files, resolve_unit  # noqa: E402

CJK = r"[一-鿿]"
PAUSE = "，、；：（）()——"
NOMINAL_HEADS = "持有|維護|行使|回收|轉寫|採納|擴張|依賴|接回|徵用|凍結|流通|兌換|發放|販售|收攏|加固|複現|對質|申論|判定"
COUNTED_NOUNS = "節點|機制|軸線|層次|環節|案例|網絡|通道|路徑|管道|文件|條款|測試|支柱|視角|預測|限制|原則|維度"


def strip_nonprose(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"^#{1,6} .*$", "", text, flags=re.M)
    text = re.sub(r"^\|.*\|$", "", text, flags=re.M)
    text = re.sub(r"^: .*$", "", text, flags=re.M)
    text = re.sub(r"\[@[^\]]+\]", "", text)          # citations don't count
    text = re.sub(r"「[^」]*」", "「」", text)          # quotes are verbatim-exempt
    text = re.sub(r"《[^》]*》", "《》", text)          # titles are verbatim-exempt
    return text


def sentences(text: str):
    for para in text.splitlines():
        para = para.strip()
        if not para:
            continue
        for s in re.split(r"(?<=[。！？])", para):
            s = s.strip()
            if len(re.findall(CJK, s)) >= 10:
                yield s


def analyze(s: str) -> dict:
    hits = {}
    runs = [len(re.findall(CJK, seg)) for seg in re.split(f"[{PAUSE}。]", s)]
    for seg in re.split(f"[{PAUSE}。]", s):
        for m in re.finditer(rf"({CJK}+)的(?={CJK})", seg):
            if len(m.group(1)) >= 12:
                hits.setdefault("P1長前置定語", []).append(m.group(1) + "的")
    for m in re.finditer(rf"的({NOMINAL_HEADS})(?![一-鿿])", s):
        hits.setdefault("P2名物化", []).append("的" + m.group(1))
    if runs and max(runs) >= 28:
        hits["P3無停頓"] = [f"最長 {max(runs)} 字無停頓"]
    n = len(re.findall(CJK, s))
    if n >= 110:
        hits["P4超長句"] = [f"{n} 字"]
    dashes = s.count("——")
    if dashes >= 3:
        hits["P5破折號嵌套"] = [f"—— ×{dashes}"]
    for m in re.finditer(rf"[二三四五六七八九]({COUNTED_NOUNS})", s):
        hits.setdefault("P6量詞省略", []).append(m.group(0))
    return hits


WEIGHT = {"P1長前置定語": 3, "P2名物化": 2, "P3無停頓": 2, "P4超長句": 1,
          "P5破折號嵌套": 1, "P6量詞省略": 1}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("unit", nargs="?", help="unit directory (default: nearest WORK.json)")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--all", action="store_true", help="list every flagged sentence")
    args = ap.parse_args()

    unit = resolve_unit(args.unit)
    # Outlines and the references stub are notes, not prose to be read aloud;
    # linting them would set the ratchet from text nobody hands in.
    skip = {"outline.qmd", "references.qmd"}
    files = [f for f in manuscript_files(unit) if f.name not in skip]
    if not files:
        sys.exit(f"no manuscript .qmd in {unit} (looked for chapters/*.qmd and *.qmd)")
    flagged, total = [], 0
    for f in files:
        for s in sentences(strip_nonprose(f.read_text(encoding="utf-8"))):
            total += 1
            hits = analyze(s)
            if hits:
                score = sum(WEIGHT[k] * len(v) for k, v in hits.items())
                flagged.append((score, f.name, s, hits))

    flagged.sort(key=lambda x: -x[0])
    print(f"READABILITY LINT — {total} sentences · {len(flagged)} flagged "
          f"({len(flagged)/max(total,1):.0%})")
    from collections import Counter
    pat = Counter(k for *_, hits in flagged for k in hits)
    for k, n in pat.most_common():
        print(f"  {k}: {n} 句")
    show = flagged if args.all else flagged[: args.top]
    print(f"\nWORST {'ALL' if args.all else f'TOP {args.top}'} (score · file · patterns):")
    for score, name, s, hits in show:
        tags = "; ".join(f"{k}[{'、'.join(v[:2])}]" for k, v in hits.items())
        print(f"\n  [{score}] {name} — {tags}")
        print(f"      {s[:120]}{'…' if len(s) > 120 else ''}")


if __name__ == "__main__":
    main()
