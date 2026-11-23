#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.14"
# dependencies = ["ckip-transformers", "torch"]
# ///
"""Corpus word frequency: which of the manuscript's words are rare in Taiwanese written Chinese.

    ./fw word-freq scan [<unit>] [--glossary <file>] [--out <file>] [--min-uses N] [--max-per-million X]
    ./fw word-freq lookup <word> ...

The reference is the NAER COCT written corpus (國教院 COCT 書面語語料庫,
2014–2024, about 300 million words), whose full frequency list is
downloaded once into the user cache. `scan` segments every manuscript
paragraph with CKIP, the segmenter family the corpus was tagged with, so a
manuscript word and a corpus word are cut the same way, and lists the words
the manuscript uses at least `--min-uses` times that the corpus has fewer than
`--max-per-million` of. It leaves out a source's own words (the spans
read-check recognises as quotation), titles in 《》〈〉, the glossary's approved
terms and their parts, proper nouns and numerals, and the words the author
has already approved as the field's vocabulary. `lookup` prints the count and
rate of each word given and needs no segmenter.

The author's decisions live in `<unit>/word-frequency.md`: a table under a
heading starting `## 作者不用的詞` (first column the word, second its
replacement) and one line of 、-separated words under a heading starting
`## 學門用語` (a line holding a 。 is prose and is skipped). `scan` lists
where each word the author dropped still occurs, and skips the approved field
words. A general corpus under-represents every field's vocabulary, so the
list always opens with field terms; the author sorts them once, and what
remains is what the manuscript coined.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _paths import rel, resolve_unit  # noqa: E402

_spec = importlib.util.spec_from_file_location("read_check", HERE / "read-check.py")
read_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(read_check)

CORPUS = "yl_2014_2024"
CORPUS_NAME = "國教院 COCT 書面語語料庫2026"
FREQ_URL = f"https://bcoct.naer.edu.tw/cqpweb/{CORPUS}/freqlist.php?" + urllib.parse.urlencode({
    "flAtt": "word", "flOrder": "desc", "flFilterString": "", "flFilterType": "begin",
    "flTable": "::entire_corpus", "menuChoice": "downloadFreqList", "tableDownloadMode": "1",
})
WORDLIST = "word-frequency.md"
SKIP_POS = {"Nb", "FW", "Neu", "Nf", "Nd"}
TITLES = re.compile(r"《[^《》]*》|〈[^〈〉]*〉")


def cache_file() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "thesisbug2" / "coct" / f"{CORPUS}.txt"


def parse_freq(text: str) -> tuple[dict[str, int], int]:
    """Counts by word from a CQPweb frequency-list download, and the number
    of word tokens (punctuation and symbols excluded). Words are NFKC-folded
    and merged, because the COCT 2026 text stores some characters as Kangxi
    radicals (自 as U+2F83, seen 2026-11-23), which would hide 自己 from a
    lookup typed with the ordinary character."""
    counts: dict[str, int] = {}
    punct = 0
    for line in text.splitlines():
        p = line.split("\t")
        if len(p) != 3 or not p[0].strip().isdigit():
            continue
        c = int(p[2].replace(",", ""))
        w = unicodedata.normalize("NFKC", p[1])
        counts[w] = counts.get(w, 0) + c
        if all(unicodedata.category(ch)[0] in "PSZ" for ch in w):
            punct += c
    return counts, sum(counts.values()) - punct


def load_freq() -> tuple[dict[str, int], int]:
    path = cache_file()
    if not path.exists():
        print(f"downloading the {CORPUS_NAME} frequency list (about 55 MB, once) -> {path}", file=sys.stderr)
        path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(FREQ_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=600) as r:
            data = r.read()
        if not data.startswith(b"Frequency list"):
            sys.exit("the corpus site did not return a frequency list; open the URL in a browser to check:\n" + FREQ_URL)
        path.write_bytes(data)
    return parse_freq(path.read_text(encoding="utf-8"))


def section_lines(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("## " + heading):
            out = []
            for l in lines[i + 1:]:
                if l.startswith("## "):
                    break
                out.append(l)
            return out
    return []


def author_lists(text: str) -> tuple[list[tuple[str, str]], set[str]]:
    """(dropped word, replacement) pairs and the approved field words from the
    author's word-frequency file."""
    dropped = []
    for l in section_lines(text, "作者不用的詞"):
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if l.lstrip().startswith("|") and len(cells) >= 2 and cells[0] and not set(cells[0]) <= set(":- ") \
                and cells[0] not in ("不用", "詞"):
            dropped.append((cells[0], cells[1]))
    approved: set[str] = set()
    for l in section_lines(text, "學門用語"):
        l = l.strip()
        if l and not l.startswith("（") and "。" not in l:
            approved |= {w.strip() for w in l.split("、") if w.strip()}
    return dropped, approved


def own_text(para: dict) -> str:
    """The paragraph with a source's own words and titles blanked, keeping
    offsets: their wording is not the author's to change."""
    text = para["text"]
    for s, e in para.get("quotes", []):
        text = text[:s] + "　" * (e - s) + text[e:]
    text = TITLES.sub(lambda m: "　" * len(m.group(0)), text)
    return text.replace("[註]", "　　　")


def glossary_parts(terms: list[dict]) -> set[str]:
    """Every substring of an approved name: the segmenter cuts 數位美元霸權
    into parts, and a part is covered by the entry. A word that contains an
    approved name plus more is a new compound and is not covered."""
    parts = set()
    for t in terms:
        for n in t["names"]:
            parts |= {n[i:j] for i in range(len(n)) for j in range(i + 2, len(n) + 1)}
    return parts


RESULTATIVE = "為到給成"


def corpus_count(w: str, counts: dict[str, int]) -> int:
    """A word's corpus count. CKIP joins a verb to a following 為／到／給／成
    (定性為, 移轉到) more often in the manuscript than the corpus list records
    the pair as one word; such a word is as ordinary as its verb, so it takes
    the verb's count when that is higher."""
    c = counts.get(w, 0)
    if len(w) >= 3 and w[-1] in RESULTATIVE:
        c = max(c, counts.get(w[:-1], 0))
    return c


def has_cjk(w: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in w)


def tally(paras: list[dict], segmented: list[list[str]], tags: list[list[str]], skip: set[str]):
    uses, where, pos, first = Counter(), defaultdict(set), defaultdict(Counter), {}
    for p, words, tgs in zip(paras, segmented, tags):
        for w, t in zip(words, tgs):
            w = unicodedata.normalize("NFKC", w.strip())
            if len(w) < 2 or not has_cjk(w) or w in skip:
                continue
            uses[w] += 1
            pos[w][t] += 1
            where[w].add(Path(p["file"]).stem.split("-")[0])
            first.setdefault(w, (p["file"], p["line"]))
    return uses, where, pos, first


def cmd_lookup(args: argparse.Namespace) -> None:
    counts, total = load_freq()
    print(f"{CORPUS_NAME}: {total:,} words")
    for w in args.words:
        c = counts.get(unicodedata.normalize("NFKC", w), 0)
        print(f"{w}\t{c:,}\t{c / total * 1e6:.2f} per million")


def cmd_scan(args: argparse.Namespace) -> None:
    unit = resolve_unit(args.unit)
    wl = unit / WORDLIST
    dropped, approved = author_lists(wl.read_text(encoding="utf-8")) if wl.exists() else ([], set())
    terms = read_check.read_glossary(unit, args.glossary) if args.glossary else []
    paras = read_check.unit_paragraphs(unit, sources=read_check.Sources(unit))
    texts = [own_text(p) for p in paras]

    from ckip_transformers.nlp import CkipPosTagger, CkipWordSegmenter
    segmented = CkipWordSegmenter(model="bert-base")(texts, batch_size=16, show_progress=False)
    tags = CkipPosTagger(model="bert-base")(segmented, batch_size=16, show_progress=False)

    counts, total = load_freq()
    uses, where, pos, first = tally(paras, segmented, tags, glossary_parts(terms) | approved)
    rows = []
    for w, n in uses.items():
        if n < args.min_uses or pos[w].most_common(1)[0][0] in SKIP_POS:
            continue
        c = corpus_count(w, counts)
        rate = c / total * 1e6
        if rate < args.max_per_million:
            rows.append((n, w, c, rate))
    rows.sort(key=lambda r: (-r[0], r[3]))

    out = Path(args.out) if args.out else unit / "gpt-review" / f"{dt.date.today():%Y-%m-%d}-word-freq.md"
    lines = [f"# 詞頻掃描：{rel(unit)}", "",
             f"由 `./fw word-freq scan` 產生，不要手改。參照 {CORPUS_NAME}，{total:,} 詞（不含標點）。", ""]
    hits = [(d, r, p, p["text"].count(d)) for d, r in dropped for p in paras if d in own_text(p)]
    lines += ["## 作者不用的詞仍出現處", ""]
    lines += [f"- {d}→{r}：`{p['file']}:{p['line']}`（{k} 處）" for d, r, p, k in hits] or ["（無）"]
    lines += ["", f"## 稿中 ≥{args.min_uses} 次、語料庫每百萬詞 <{args.max_per_million:g} 的詞", "",
              "引文、書名、詞彙表用語與其組成部分、專有名詞、數量詞與已核可的學門用語不列。"
              "先把學門用語列進 `word-frequency.md` 的「學門用語」，剩下的多半是稿子自己造的詞；"
              "判讀時拿它和平實說法的詞頻比倍數（`./fw word-freq lookup`），不看絕對門檻。", "",
              "| 詞 | 稿中次數 | 章 | 語料庫筆數 | 每百萬 | 首見 |", "| :--- | ---: | :--- | ---: | ---: | :--- |"]
    for n, w, c, rate in rows:
        f, line = first[w]
        lines.append(f"| {w} | {n} | {','.join(sorted(where[w]))} | {c:,} | {rate:.2f} | `{f}:{line}` |")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows)} rare words, {len(hits)} dropped-word paragraphs -> {rel(out)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="list the manuscript's words that are rare in the corpus")
    s.add_argument("unit", nargs="?", help="unit directory (default: nearest WORK.json)")
    s.add_argument("--glossary", help="definitions section or glossary file (read-check format); its terms are not listed")
    s.add_argument("--out", help="report path (default: <unit>/gpt-review/<date>-word-freq.md)")
    s.add_argument("--min-uses", type=int, default=2, help="list words used at least this often (default 2)")
    s.add_argument("--max-per-million", type=float, default=2.0, help="list words rarer than this (default 2)")
    s.set_defaults(func=cmd_scan)
    lk = sub.add_parser("lookup", help="corpus count and rate of each word")
    lk.add_argument("words", nargs="+")
    lk.set_defaults(func=cmd_lookup)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
