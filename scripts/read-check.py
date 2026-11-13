#!/usr/bin/env python3
"""Paragraph-by-paragraph prompts for isolated readers, and a report of what they picked.

    ./fw read-check prompts [<unit>] --out <dir> [--files a.qmd ...] [--sample N] [--seed S]
                                     [--min N] [--reader "<who reads this>"] [--glossary <file>]
    ./fw read-check collect <dir> [--glossary <file>]

`prompts` writes one prompt file per manuscript paragraph: the paragraph as a
reader sees it (citations shown as [註], emphasis marks removed) and the
instruction to pick the fragments that are hard to read. One paragraph per
file is the point: a reader who is given the neighbouring paragraphs learns
the manuscript's private terms from them and stops noticing them, which is
how those terms spread in the first place (read-check skill). With
`--glossary`, every prompt also carries the manuscript's reviewed definitions,
because the manuscript's real reader has read them before reaching any
paragraph.

The command starts no model. The agent hands each prompt to an isolated
reader and saves that reader's answer, as it came, under
`<dir>/picks/<reader-name>/<paragraph-id>.*`. `collect` then keeps only the
fragments that occur verbatim in their paragraph, counts how often each one
occurs in the whole manuscript, and writes `<dir>/report.md` and
`<dir>/picks.json`. With a glossary (the one the readers were given, or
`collect --glossary`), the report says which picked fragments are terms the
author has approved: only those may stay as special terms, and the rest are to
be said in the field's ordinary vocabulary.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import course_root, manuscript_files, rel, resolve_unit  # noqa: E402

CJK = re.compile(r"[一-鿿]")
NOT_A_PARAGRAPH = ("#", "|", ":::", "![", "{{<", ">", ": ", "$$", "```", "~~~", "<")
SKIP_FILES = {"outline.qmd", "references.qmd"}
DEFAULT_READER = "這篇論文所屬領域的教授"

PROMPT = """你是{reader}。下面是一篇論文裡的一段文字，{have}，沒有論文其他部分。

把你讀起來吃力的片段挑出來：要停下來重讀、要猜意思，或不確定是不是通行說法的詞句。指向論文其他章節的代號與交叉引用（例如 H1、第三章）不算。

只挑，不做別的：不必說明原因，不必猜它的意思，不要建議怎麼改。

只根據下面貼的文字回答；不要開啟、搜尋或修改任何檔案，不要執行任何指令。

只輸出一個 JSON 陣列，不要其他文字。每個元素是原文裡一字不差的連續片段，只框難讀的那幾個字，不要框整句；沒有就輸出 []。
{glossary}
段落（[註] 是被遮掉的引註，不必理會）：

{text}
"""

HAVE_PARAGRAPH = "你手上只有這一段"
HAVE_GLOSSARY = "你手上只有這一段，以及論文前面的名詞定義"
GLOSSARY_BLOCK = """
這篇論文在前面的章節定義了下列用語，請當作你已經讀過這些定義。段落裡出現這些用語時不必挑；在這些用語上加字組成的新詞沒有定義過，讀來吃力就照樣挑。名詞定義只是背景，不要從裡面挑片段。

{entries}
"""


def blank_keeping_lines(text: str, pattern: str) -> str:
    """Remove matches but keep their newlines, so line numbers stay true."""
    return re.sub(pattern, lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)


def reader_text(block: str) -> str:
    """One paragraph as the reader of the finished document sees it."""
    t = re.sub(r"\^\[[^\]]*\]", "[註]", block)       # inline footnote
    t = re.sub(r"\[\^[^\]]+\]", "[註]", t)           # footnote reference
    t = re.sub(r"\[[^\[\]]*@[^\[\]]*\]", "[註]", t)  # [@key, p. 3] and [見 @a; @b]
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])", r"\1", t)
    # A source line break inside a paragraph is not a break on the page; CJK
    # text joins without a space, Latin words need one.
    t = re.sub(r"(?<=[^\x00-\x7f])\s*\n\s*|\s*\n\s*(?=[^\x00-\x7f])", "", t)
    return re.sub(r"\s*\n\s*", " ", t).strip()


def paragraphs(source: str) -> list[tuple[int, str]]:
    """(1-based line, reader text) for every prose paragraph in a .qmd source."""
    text = blank_keeping_lines(source, r"\A---\n.*?\n---[ \t]*(?=\n)")
    text = blank_keeping_lines(text, r"<!--.*?-->")
    text = blank_keeping_lines(text, r"(?m)^(```|~~~).*?^\1[ \t]*$")
    out: list[tuple[int, str]] = []
    start, block = 0, []
    for no, line in enumerate([*text.split("\n"), ""], 1):
        if line.strip():
            if not block:
                start = no
            block.append(line.strip())
            continue
        if block and not block[0].startswith(NOT_A_PARAGRAPH):
            shown = reader_text("\n".join(block))
            if shown:
                out.append((start, shown))
        block = []
    return out


def glossary_terms(source: str) -> list[dict]:
    """Entries of a definitions section or glossary file: every block that
    opens with a bold term followed by a colon, e.g. `**結構性權力（structural
    power）**：…`. A slash between two names (受許可／無許可) lists both. `head`
    is the lead-in as written and `definition` the rest of the block as a
    reader of the finished document sees it; the block ends at a blank line or
    at the next entry."""
    text = re.sub(r"<!--.*?-->", "", source, flags=re.S)
    found = list(re.finditer(r"(?m)^[ \t]*(?:[-*+] |\d+\. )?\*\*([^*\n]+)\*\*[ \t]*[：:]", text))
    terms = []
    for i, m in enumerate(found):
        head = m.group(1).strip()
        name, _, gloss = re.match(r"([^（(]*)[（(]?([^）)]*)", head).group(1, 0, 2)
        names = [n.strip() for n in re.split(r"[／/]", name) if n.strip()]
        if not names:
            continue
        end = found[i + 1].start() if i + 1 < len(found) else len(text)
        body = re.split(r"\n[ \t]*\n", text[m.end():end], maxsplit=1)[0]
        terms.append({"term": name.strip(), "names": names, "gloss": gloss.strip(),
                      "head": head, "definition": reader_text(body)})
    return terms


def read_glossary(unit: Path, name: str) -> list[dict]:
    """Entries of the glossary file `name`, looked up as given, in the unit,
    then among its chapters."""
    gfile = next((c for c in (Path(name), unit / name, unit / "chapters" / name) if c.is_file()), None)
    if not gfile:
        sys.exit(f"no such glossary file: {name}")
    terms = glossary_terms(gfile.read_text(encoding="utf-8"))
    if not terms:
        sys.exit(f"no entries in {rel(gfile)}: an entry is a block opening with **term**：")
    return terms


def unit_paragraphs(unit: Path, only: list[str] | None = None) -> list[dict]:
    files = [f for f in manuscript_files(unit) if f.name not in SKIP_FILES]
    if only:
        wanted = {Path(o).name for o in only}
        missing = wanted - {f.name for f in files}
        if missing:
            sys.exit(f"not a manuscript file of {rel(unit)}: {', '.join(sorted(missing))}")
        files = [f for f in files if f.name in wanted]
    if not files:
        sys.exit(f"no manuscript .qmd in {rel(unit)} (looked for chapters/*.qmd and *.qmd)")
    return [{"file": rel(f), "line": line, "text": shown}
            for f in files for line, shown in paragraphs(f.read_text(encoding="utf-8"))]


def sample(paras: list[dict], n: int, seed: int) -> list[dict]:
    """n paragraphs, at least one from every file while n allows, so a sample
    of a thesis is not all drawn from its longest chapter."""
    rng = random.Random(seed)
    by_file: dict[str, list[dict]] = defaultdict(list)
    for p in paras:
        by_file[p["file"]].append(p)
    picked = [rng.choice(v) for v in by_file.values()]
    if len(picked) > n:
        picked = rng.sample(picked, n)
    rest = [p for p in paras if p not in picked]
    picked += rng.sample(rest, min(n - len(picked), len(rest)))
    order = {id(p): i for i, p in enumerate(paras)}
    return sorted(picked, key=lambda p: order[id(p)])


def cmd_prompts(args: argparse.Namespace) -> None:
    unit = resolve_unit(args.unit)
    paras = [p for p in unit_paragraphs(unit, args.files) if len(CJK.findall(p["text"])) >= args.min]
    if not paras:
        sys.exit(f"no paragraph of at least {args.min} Chinese characters in {rel(unit)}")
    total = len(paras)
    if args.sample and args.sample < total:
        paras = sample(paras, args.sample, args.seed)
    glossary = read_glossary(unit, args.glossary) if args.glossary else []
    shown = GLOSSARY_BLOCK.format(entries="\n".join(
        f"- {g['head']}：{g['definition']}" for g in glossary)) if glossary else ""
    out = Path(args.out)
    (out / "prompts").mkdir(parents=True, exist_ok=True)
    for stale in (out / "prompts").glob("p*.md"):
        stale.unlink()
    for i, p in enumerate(paras, 1):
        p["id"] = f"p{i:04d}"
        (out / "prompts" / f"{p['id']}.md").write_text(
            PROMPT.format(reader=args.reader, text=p["text"], glossary=shown,
                          have=HAVE_GLOSSARY if glossary else HAVE_PARAGRAPH), encoding="utf-8")
    # What the readers were given is part of the record: a pick of a defined
    # term means something different when the reader had its definition.
    meta = {"unit": rel(unit), "reader": args.reader, "glossary": glossary, "paragraphs": paras}
    (out / "paras.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(paras)} of {total} paragraphs -> {rel(out)}/prompts/ (one prompt per file"
          + (f", each with the {len(glossary)} glossary entries)" if glossary else ")"))
    print(f"save each reader's answers as {rel(out)}/picks/<reader-name>/<id>.json, "
          f"then: ./fw read-check collect {rel(out)}")


def first_string_array(raw: str) -> list[str] | None:
    """The first JSON array of strings in a reader's saved answer. Answers are
    saved as they came, so they may carry a runner's banner or a code fence."""
    dec = json.JSONDecoder()
    for m in re.finditer(r"\[", raw):
        try:
            val, _ = dec.raw_decode(raw[m.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(val, list) and all(isinstance(x, str) for x in val):
            return val
    return None


def cmd_collect(args: argparse.Namespace) -> None:
    out = Path(args.dir)
    meta_file = out / "paras.json"
    if not meta_file.is_file():
        sys.exit(f"no paras.json in {out} — run `./fw read-check prompts` first")
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    paras = {p["id"]: p for p in meta["paragraphs"]}
    given: list[dict] = meta.get("glossary") or []
    glossary = read_glossary(course_root() / meta["unit"], args.glossary) if args.glossary else given
    readers = sorted(d.name for d in (out / "picks").iterdir() if d.is_dir()) if (out / "picks").is_dir() else []
    if not readers:
        sys.exit(f"no reader answers under {out}/picks/<reader-name>/")

    spans: dict[str, dict[tuple[int, int], set[str]]] = {pid: defaultdict(set) for pid in paras}
    stats = {}
    for r in readers:
        answered, kept, dropped, unparsed = 0, 0, [], []
        for pid, p in paras.items():
            files = sorted((out / "picks" / r).glob(f"{pid}.*"))
            if not files:
                continue
            picks = first_string_array(files[0].read_text(encoding="utf-8", errors="replace"))
            if picks is None:
                unparsed.append(pid)
                continue
            answered += 1
            for frag in picks:
                at = p["text"].find(frag) if frag else -1
                if at < 0:
                    dropped.append((pid, frag))
                    continue
                spans[pid][(at, at + len(frag))].add(r)
                kept += 1
        stats[r] = (answered, kept, dropped, unparsed)

    # How far a picked fragment has spread is counted over the whole
    # manuscript, not over the paragraphs that happened to be sampled.
    corpus = unit_paragraphs(course_root() / meta["unit"])
    by_text: dict[str, dict] = {}
    for pid, found in spans.items():
        for (s, e), who in found.items():
            frag = paras[pid]["text"][s:e]
            row = by_text.setdefault(frag, {"paras": set(), "readers": set()})
            row["paras"].add(pid)
            row["readers"] |= who
    for frag, row in by_text.items():
        hits = [c for c in corpus if frag in c["text"]]
        row["count"] = sum(c["text"].count(frag) for c in hits)
        row["files"] = len({c["file"] for c in hits})
        # A fragment is covered when it is an approved name or a piece of one;
        # a longer compound built on an approved name is a new term.
        row["approved"] = next((g["term"] for g in glossary if any(frag in n for n in g["names"])), "")

    merged = {pid: [{"s": s, "e": e, "text": paras[pid]["text"][s:e], "readers": sorted(who)}
                    for (s, e), who in sorted(found.items())] for pid, found in spans.items()}
    (out / "picks.json").write_text(json.dumps(merged, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    lines = [f"# 段落冷讀：讀者挑出的難讀片段（{meta['unit']}）", "",
             "<!-- 由 ./fw read-check collect 產生，不要手改。片段是讀者的原話，只保留在段落裡逐字找得到的；",
             "     這是給作者裁定的工作清單，不是閘門：留、換成白話、或在第一次出現時定義，由作者決定。 -->", "",
             f"- 段落：{len(paras)} 段；讀者設定：{meta['reader']}",
             (f"- 讀者拿到的名詞定義：{len(given)} 條（{'、'.join(g['term'] for g in given)}）" if given
              else "- 讀者沒有拿到名詞定義"),
             "", "| 讀者 | 已答段數 | 片段 | 不在原文（已丟棄） | 無法解析 |", "| :--- | ---: | ---: | ---: | ---: |"]
    for r, (answered, kept, dropped, unparsed) in stats.items():
        lines.append(f"| {r} | {answered} | {kept} | {len(dropped)} | {len(unparsed)} |")
    for r, (_a, _k, _d, unparsed) in stats.items():
        if unparsed:
            lines.append(f"\n{r} 無法解析的答案：{'、'.join(unparsed)}（不是 JSON 字串陣列，請重問）")

    spread = sorted(by_text.items(), key=lambda kv: (-len(kv[1]["readers"]), -kv[1]["count"], kv[0]))
    lines += ["", "## 片段在全文的擴散", "",
              "同一個片段在全文出現越多次、越多檔案，越可能是稿子自己養出來的詞；先看這張表。"]
    if glossary:
        lines.append("「詞彙表」欄空白的片段不是作者核可的詞：改用該領域的一般用語，或由作者決定把它加進詞彙表。")
    lines += ["", "| 片段 | 詞彙表 | 挑它的讀者 | 被挑的段數 | 全文出現次數 | 出現的檔案數 |",
              "| :--- | :--- | :--- | ---: | ---: | ---: |"]
    for frag, row in spread:
        if len(row["readers"]) > 1 or len(row["paras"]) > 1 or row["count"] > 1:
            lines.append(f"| {frag} | {row['approved']} | {'、'.join(sorted(row['readers']))} | {len(row['paras'])} "
                         f"| {row['count']} | {row['files']} |")
    if glossary:
        lines += ["", "## 詞彙表條目", "",
                  ("讀者讀過定義仍然挑出的條目，先檢查定義本身好不好懂，再檢查這個詞是不是該領域真的在用。" if given else
                   "讀者仍然挑出的條目，先檢查它第一次出現的地方有沒有定義，再檢查這個詞是不是該領域真的在用。"), "",
                  "| 條目 | 原文或別名 | 全文出現次數 | 讀者挑出 |", "| :--- | :--- | ---: | :--- |"]
        for g in glossary:
            n = sum(c["text"].count(name) for c in corpus for name in g["names"])
            who = sorted({r for frag, row in by_text.items() if row["approved"] == g["term"] for r in row["readers"]})
            lines.append(f"| {g['term']} | {g['gloss']} | {n} | {'、'.join(who)} |")

    lines += ["", "## 逐段", ""]
    def share(pid: str) -> float:
        covered = set()
        for s, e in spans[pid]:
            covered |= set(range(s, e))
        return len(covered) / max(len(paras[pid]["text"]), 1)
    for pid in sorted(paras, key=lambda x: -share(x)):
        if not spans[pid]:
            continue
        p = paras[pid]
        lines.append(f"- **{pid}** `{p['file']}:{p['line']}`（被挑字數 {share(pid):.0%}）："
                     + "；".join(f"{x['text']}〔{'、'.join(x['readers'])}〕" for x in merged[pid]))
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    kept = sum(k for _a, k, _d, _u in stats.values())
    print(f"{len(readers)} readers, {kept} fragments kept -> {rel(out)}/report.md, {rel(out)}/picks.json")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prompts", help="write one prompt per paragraph")
    p.add_argument("unit", nargs="?", help="unit directory (default: nearest WORK.json)")
    p.add_argument("--out", required=True, help="directory for prompts/ and paras.json")
    p.add_argument("--files", nargs="+", help="only these manuscript files (by name)")
    p.add_argument("--sample", type=int, help="draw this many paragraphs instead of all")
    p.add_argument("--seed", type=int, default=1, help="seed for --sample (default 1)")
    p.add_argument("--min", type=int, default=40, help="skip paragraphs under this many Chinese characters (default 40)")
    p.add_argument("--reader", default=DEFAULT_READER, help="who the reader is, in the manuscript's language")
    p.add_argument("--glossary", help="the author-reviewed definitions section or glossary file; its entries "
                                      "and definitions go into every prompt")
    p.set_defaults(func=cmd_prompts)
    c = sub.add_parser("collect", help="verify the readers' picks and write the report")
    c.add_argument("dir", help="the directory given to `prompts --out`")
    c.add_argument("--glossary", help="the manuscript's definitions section or glossary file; entries are blocks "
                                      "opening with **term**： (default: the one the readers were given)")
    c.set_defaults(func=cmd_collect)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
