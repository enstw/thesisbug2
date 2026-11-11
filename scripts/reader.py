#!/usr/bin/env python3
"""reader — render a source transcript as a page made for reading.

    ./fw reader <key>                     find refs/<key>.md in the units or library/
    ./fw reader <path/to/key.md>          any transcript in the same format
    ./fw reader <key> --out <file.html>   write somewhere other than _output/<key>.html

The transcript stays the source of truth: the page is regenerated from it, never
edited, so a correction made to refs/<key>.md reaches the page on the next run.
What the transcript format carries and the page shows:

  **[Page N start]** markers   a page chip at the break, shifted by the
                                frontmatter's marker_offset (printed pages)
  a paragraph cut by a break    rejoined, the chip left where the cut fell
  > <sup>N</sup> … blockquotes  page-bottom footnotes, moved to the end with a
  [^N] / [^N]: …                hover/tap preview; （註 N 續） continues note N
  leading <!-- … --> comments   the "about this text" panel

Raw HTML in the transcript is escaped (apart from <sup> footnote refs), because a
transcript is OCR of someone else's document and must not run in the page.
Standard library only.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRAMEWORK = HERE.parent
TEMPLATE = FRAMEWORK / ".agents" / "skills" / "reader" / "assets" / "page.html"
HOUSE_FONTS = FRAMEWORK / ".agents" / "skills" / "house-style" / "assets" / "fonts"
FONT_FILES = ("ENSFont.woff2", "ENSFont-Bold.woff2")

PAGE_RE = re.compile(
    r"^\s*(?:\*\*)?\[(?:Page\s+(\d+)\s+end)?(?:,\s*)?(?:Page\s+(\d+)\s+start)?\](?:\*\*)?\s*$")
SUP_DEF_RE = re.compile(r"^<sup>([^<]{1,8})</sup>\s*(.*)$")
CONT_RE = re.compile(r"^[（(]註\s*([^\s）)]{1,8})\s*續[）)]\s*(.*)$")
MD_DEF_RE = re.compile(r"^\[\^([^\]]{1,16})\]:\s*(.*)$")
LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
HR_RE = re.compile(r"^\s*(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$")
CJK = re.compile(r"[　-〿㐀-鿿豈-﫿＀-￯]")
TERMINAL = set("。！？」』）．.!?:：;；…\"”’")

# Private-use code points mark page breaks and footnote refs inside paragraph
# text, so they survive escaping and the inline Markdown pass untouched.
TOK_OPEN, TOK_CLOSE = "", ""
TOK_RE = re.compile(f"{TOK_OPEN}(PG|FN):([^{TOK_CLOSE}]*){TOK_CLOSE}")


def pg_tok(n: int) -> str:
    return f"{TOK_OPEN}PG:{n}{TOK_CLOSE}"


def fn_tok(label: str) -> str:
    return f"{TOK_OPEN}FN:{label}{TOK_CLOSE}"


@dataclass
class Note:
    label: str
    page: int | None
    text: str
    nid: str = ""
    refs: list[str] = field(default_factory=list)


@dataclass
class Doc:
    blocks: list[tuple]           # ('pg', n) ('h', lvl, text) ('p', text) ('quote', [items])
                                  # ('list', [lines]) ('table', [lines]) ('code', text) ('hr',)
    notes: list[Note]
    provenance: list[str]
    meta: dict[str, str]


# ---------------------------------------------------------------- parsing

def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    meta = {}
    for line in text[4:end].splitlines():
        m = re.match(r"\s*([A-Za-z_][\w-]*)\s*:\s*(.*?)\s*(?:#.*)?$", line)
        if m:
            meta[m.group(1)] = m.group(2).strip().strip("\"'")
    return meta, text[end + 4:].lstrip("\n")


def join_lines(a: str, b: str) -> str:
    """Join two pieces of one paragraph the way the language wants."""
    if not a:
        return b
    if not b:
        return a
    if re.search(r"[A-Za-z]-$", a) and b[:1].islower():
        return a[:-1] + b          # a word hyphenated across the break
    if CJK.match(a[-1]) or CJK.match(b[0]):
        return a + b
    return a + " " + b


def inline_refs(s: str) -> str:
    s = re.sub(r"<sup>([^<]{1,8})</sup>", lambda m: fn_tok(m.group(1).strip()), s)
    return re.sub(r"\[\^([^\]]{1,16})\]", lambda m: fn_tok(m.group(1)), s)


def parse(text: str) -> Doc:
    text = text.lstrip("﻿").replace("\r\n", "\n")
    meta, text = split_frontmatter(text)
    provenance = [re.sub(r"\n\s+", "\n", c.strip()) for c in re.findall(r"<!--(.*?)-->", text, re.S)]
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    offset = int(meta.get("marker_offset", "0") or 0)

    blocks: list[tuple] = []
    notes: list[Note] = []
    page: int | None = None
    para: list[str] = []
    quote: list[str] = []
    group: list[str] = []
    group_kind = ""
    in_code = False
    code: list[str] = []
    md_note: Note | None = None

    def end_para():
        nonlocal para
        if para:
            s = ""
            for ln in para:
                s = join_lines(s, ln.strip())
            blocks.append(("p", inline_refs(s)))
            para = []

    def end_group():
        nonlocal group, group_kind
        if group:
            blocks.append((group_kind, [inline_refs(g) for g in group]))
            group, group_kind = [], ""

    def end_quote():
        nonlocal quote
        if not quote:
            return
        items, cur = [], ""
        for q in quote:
            if q:
                cur = join_lines(cur, q)
            elif cur:
                items.append(cur)
                cur = ""
        if cur:
            items.append(cur)
        quote = []
        if not items:
            return
        if not (SUP_DEF_RE.match(items[0]) or CONT_RE.match(items[0])):
            blocks.append(("quote", [inline_refs(i) for i in items]))
            return
        last_def: Note | None = None
        for it in items:
            m = SUP_DEF_RE.match(it)
            if m:
                last_def = Note(m.group(1).strip(), page, m.group(2))
                notes.append(last_def)
                continue
            m = CONT_RE.match(it)
            if m:
                prev = next((n for n in reversed(notes) if n.label == m.group(1)), None)
                if prev:
                    prev.text = join_lines(prev.text, m.group(2))
                    last_def = prev
                    continue
                it = m.group(2)
            if last_def:
                last_def.text = join_lines(last_def.text, it)

    def end_all():
        end_para()
        end_group()
        end_quote()

    for raw in text.split("\n"):
        line = raw.rstrip()
        if in_code:
            if line.strip().startswith("```"):
                blocks.append(("code", "\n".join(code)))
                in_code, code = False, []
            else:
                code.append(raw)
            continue
        if line.strip().startswith("```"):
            end_all()
            in_code = True
            continue
        m = PAGE_RE.match(line)
        if m and (m.group(1) or m.group(2)):
            end_all()
            if m.group(2):
                page = int(m.group(2)) + offset
                blocks.append(("pg", page))
            continue
        if line.lstrip().startswith(">"):
            end_para()
            end_group()
            quote.append(line.lstrip()[1:].strip())
            continue
        end_quote()
        if not line.strip():
            end_para()
            end_group()
            continue
        m = MD_DEF_RE.match(line)
        if m:
            end_para()
            end_group()
            md_note = Note(m.group(1), page, m.group(2))
            notes.append(md_note)
            continue
        if md_note and raw.startswith(("    ", "\t")):
            md_note.text = join_lines(md_note.text, line.strip())  # indented [^N]: continuation
            continue
        md_note = None
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m:
            end_para()
            end_group()
            blocks.append(("h", len(m.group(1)), inline_refs(m.group(2))))
            continue
        if HR_RE.match(line):
            end_para()
            end_group()
            blocks.append(("hr",))
            continue
        kind = "table" if line.lstrip().startswith("|") else "list" if LIST_RE.match(line) else ""
        if kind or (group_kind == "list" and raw.startswith((" ", "\t"))):
            end_para()
            if kind and kind != group_kind:
                end_group()
                group_kind = kind
            if kind == "list" or kind == "table" or not group:
                group.append(line)
            else:
                group[-1] = join_lines(group[-1], line.strip())
            continue
        end_group()
        para.append(line)
    if in_code:
        blocks.append(("code", "\n".join(code)))
    end_all()
    return Doc(rejoin(blocks), notes, provenance, meta)


def ends_sentence(s: str) -> bool:
    s = TOK_RE.sub(lambda m: "" if m.group(1) == "FN" else m.group(0), s).rstrip()
    return not s or s[-1] in TERMINAL


def rejoin(blocks: list[tuple]) -> list[tuple]:
    """Glue a paragraph that a page break cut in two, keeping the break as a chip."""
    out: list[tuple] = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        if (b[0] == "pg" and out and out[-1][0] == "p" and i + 1 < len(blocks)
                and blocks[i + 1][0] == "p" and not ends_sentence(out[-1][1])):
            prev, nxt = out[-1][1], blocks[i + 1][1]
            glued = join_lines(prev, nxt)
            cut = len(prev) if glued.startswith(prev) else len(prev) - 1  # a dropped hyphen
            out[-1] = ("p", glued[:cut] + pg_tok(b[1]) + glued[cut:])
            i += 2
            continue
        out.append(b)
        i += 1
    return out


# ---------------------------------------------------------------- rendering

def md_inline(s: str) -> str:
    """Escape, then apply the small Markdown inline set transcripts use."""
    saved: list[str] = []

    def keep(fragment: str) -> str:
        saved.append(fragment)
        return f"{len(saved) - 1}"

    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", lambda m: keep(f"<code>{m.group(1)}</code>"), s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
               lambda m: keep(f'<a href="{m.group(2).replace(chr(34), "%22")}" rel="noopener">{m.group(1)}</a>'), s)
    s = re.sub(r"https?://[^\s<>（）「」，。、；]+[^\s<>（）「」，。、；.,;:)]",
               lambda m: keep(f'<a href="{m.group(0).replace(chr(34), "%22")}" rel="noopener">{m.group(0)}</a>'), s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<em>\1</em>", s)
    return re.sub("(\\d+)", lambda m: saved[int(m.group(1))], s)


class Renderer:
    def __init__(self, doc: Doc):
        self.doc = doc
        self.page: int | None = None
        self.nref = 0
        self.used: set[int] = set()
        for i, n in enumerate(doc.notes):
            n.nid = f"n{i + 1}"

    def resolve(self, label: str) -> Note | None:
        """Footnote numbers may restart per page or chapter, so match a ref to the
        first unused note with its label on this page or later, then to any."""
        cands = [(i, n) for i, n in enumerate(self.doc.notes) if n.label == label]
        for i, n in cands:
            if i not in self.used and (self.page is None or n.page is None or n.page >= self.page):
                self.used.add(i)
                return n
        for i, n in cands:
            if i not in self.used:
                self.used.add(i)
                return n
        return cands[0][1] if cands else None

    def inline(self, s: str, live: bool = True) -> str:
        out = []
        pos = 0
        for m in TOK_RE.finditer(s):
            out.append(md_inline(s[pos:m.start()]))
            kind, val = m.group(1), m.group(2)
            if kind == "PG":
                self.page = int(val)
                out.append(f'<span class="pg" id="p{val}" title="原書頁 {val}">p.&#8239;{val}</span>')
            elif not live:
                out.append(f"<sup>{html.escape(val)}</sup>")
            else:
                note = self.resolve(val)
                if note is None:
                    out.append(f"<sup>{html.escape(val)}</sup>")
                else:
                    self.nref += 1
                    rid = f"r{self.nref}"
                    note.refs.append(rid)
                    out.append(f'<a class="fn" href="#{note.nid}" id="{rid}" data-fn="{note.nid}" '
                               f'aria-label="註 {html.escape(val)}">{html.escape(val)}</a>')
            pos = m.end()
        out.append(md_inline(s[pos:]))
        return "".join(out)

    def table(self, rows: list[str]) -> str:
        cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
        body = [r for r in cells if not all(re.fullmatch(r":?-{2,}:?", c) for c in r if c)]
        if not body:
            return ""
        head, rest = (body[0], body[1:]) if len(cells) > 1 and cells[1] and all(
            re.fullmatch(r":?-{2,}:?", c) for c in cells[1] if c) else (None, body)
        h = "<thead><tr>" + "".join(f"<th>{self.inline(c)}</th>" for c in head) + "</tr></thead>" if head else ""
        b = "".join("<tr>" + "".join(f"<td>{self.inline(c)}</td>" for c in r) + "</tr>" for r in rest)
        return f'<div class="tablewrap"><table>{h}<tbody>{b}</tbody></table></div>'

    def lst(self, lines: list[str]) -> str:
        ordered = bool(re.match(r"^\s*\d+[.)]", lines[0]))
        items = "".join(f"<li>{self.inline(LIST_RE.sub('', ln, count=1))}</li>" for ln in lines)
        return f"<ol>{items}</ol>" if ordered else f"<ul>{items}</ul>"

    def body(self, skip_first_h1: bool) -> tuple[str, list[tuple[int, str, str]]]:
        parts, toc, nh = [], [], 0
        skipped = not skip_first_h1
        for b in self.doc.blocks:
            kind = b[0]
            if kind == "pg":
                self.page = b[1]
                parts.append(f'<div class="pgbreak" id="p{b[1]}"><span>p.&#8239;{b[1]}</span></div>')
            elif kind == "h":
                if b[1] == 1 and not skipped:
                    skipped = True
                    continue
                nh += 1
                lvl = min(max(b[1], 2), 6)
                inner = self.inline(b[2])
                if lvl <= 4:
                    toc.append((lvl, f"s{nh}", re.sub(r"<[^>]+>", "", inner)))
                parts.append(f'<h{lvl} id="s{nh}">{inner}</h{lvl}>')
            elif kind == "p":
                parts.append(f"<p>{self.inline(b[1])}</p>")
            elif kind == "quote":
                parts.append("<blockquote>" + "".join(f"<p>{self.inline(i)}</p>" for i in b[1]) + "</blockquote>")
            elif kind == "list":
                parts.append(self.lst(b[1]))
            elif kind == "table":
                parts.append(self.table(b[1]))
            elif kind == "code":
                parts.append(f"<pre><code>{html.escape(b[1])}</code></pre>")
            elif kind == "hr":
                parts.append("<hr>")
        return "\n".join(parts), toc

    def notes(self) -> str:
        out = []
        for n in self.doc.notes:
            back = f' <a class="back" href="#{n.refs[0]}" aria-label="回到正文">↩</a>' if n.refs else ""
            pg = f'<span class="fnpg">p.&#8239;{n.page}</span>' if n.page is not None else ""
            out.append(f'<li id="{n.nid}" data-label="{html.escape(n.label)}">{pg}'
                       f"{self.inline(n.text, live=False)}{back}</li>")
        return "\n".join(out)


# ---------------------------------------------------------------- bib + paths

def bib_fields(bib: Path, key: str) -> dict[str, str]:
    """The fields of one entry, brace-aware; {} when the key is absent."""
    try:
        text = bib.read_text(encoding="utf-8")
    except OSError:
        return {}
    m = re.search(r"@\w+\s*\{\s*" + re.escape(key) + r"\s*,", text)
    if not m:
        return {}
    i, depth, start = m.end(), 1, m.end()
    while i < len(text) and depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    body = text[start:i - 1]
    fields = {}
    for fm in re.finditer(r"(\w+)\s*=\s*", body):
        j = fm.end()
        if j < len(body) and body[j] == "{":
            d, k = 0, j
            while k < len(body):
                d += {"{": 1, "}": -1}.get(body[k], 0)
                k += 1
                if d == 0:
                    break
            val = body[j + 1:k - 1]
        elif j < len(body) and body[j] == '"':
            k = body.find('"', j + 1)
            val = body[j + 1:k]
        else:
            val = re.match(r"[^,\n]*", body[j:]).group(0)
        fields.setdefault(fm.group(1).lower(), re.sub(r"[{}]", "", " ".join(val.split())))
    return fields


def cite_line(f: dict[str, str]) -> str:
    if not f:
        return ""
    pages = f.get("pages", "").replace("--", "–")
    zh = f.get("langid", "").startswith("chinese") or bool(CJK.search(f.get("title", "")))
    if zh:
        parts = [f"{f.get('author', '')}（{f.get('year', 'n.d.')}）"]
        if f.get("booktitle"):
            ed = f"{f['editor']}主編，" if f.get("editor") else ""
            parts.append(f"收錄於{ed}《{f['booktitle']}》")
        elif f.get("journal"):
            vol = f.get("volume", "") + (f"（{f['number']}）" if f.get("number") else "")
            parts.append(f"《{f['journal']}》{vol}")
        elif f.get("publisher"):
            parts.append(f.get("publisher"))
        if pages:
            parts.append(f"頁 {pages}")
        return "，".join(p for p in parts if p) + "。"
    parts = [f"{f.get('author', '')} ({f.get('year', 'n.d.')})"]
    if f.get("booktitle"):
        ed = f"{f['editor']} (Ed.), " if f.get("editor") else ""
        parts.append(f"in {ed}{f['booktitle']}")
    elif f.get("journal"):
        vol = f.get("volume", "") + (f"({f['number']})" if f.get("number") else "")
        parts.append(f"{f['journal']} {vol}".strip())
    elif f.get("publisher"):
        parts.append(f["publisher"])
    if pages:
        parts.append(f"pp. {pages}")
    return ", ".join(p for p in parts if p) + "."


def find_transcript(arg: str) -> Path:
    p = Path(arg)
    if p.suffix == ".md" and p.is_file():
        return p.resolve()
    from _paths import course_root, list_units
    root = course_root()
    found = [u / "refs" / f"{arg}.md" for u in list_units(root)] + [root / "library" / "refs" / f"{arg}.md"]
    found = [f for f in found if f.is_file()]
    if not found:
        sys.exit(f"no transcript for '{arg}': looked for refs/{arg}.md in every unit and library/")
    if len(found) > 1:
        sys.exit("more than one transcript for this key (run ./fw refs where "
                 f"{arg}): " + ", ".join(str(f) for f in found))
    return found[0]


def bib_for(md: Path) -> dict[str, str]:
    key = md.stem.removesuffix(".tc")
    refs_dir = md.parent
    candidates = [refs_dir.parent / "references.bib"]
    try:
        from _paths import course_root
        candidates.append(course_root() / "library" / "references.bib")
    except SystemExit:
        pass
    for bib in candidates:
        f = bib_fields(bib, key)
        if f:
            return f
    return {}


def font_base(out: Path) -> str | None:
    """Where the page finds the house font, relative to the page.

    A presentation unit already ships asset/ENSFont*.woff2; otherwise the fonts
    are copied once into _output/fonts/, which is gitignored, so 13 MB of font
    never lands in the course repo. With neither, the page uses system fonts."""
    if all((out.parent / "asset" / f).is_file() for f in FONT_FILES):
        return "asset/"
    if not all((HOUSE_FONTS / f).is_file() for f in FONT_FILES):
        return None
    try:
        from _paths import course_root
        dest = course_root() / "_output" / "fonts"
    except SystemExit:
        dest = out.parent / "fonts"
    dest.mkdir(parents=True, exist_ok=True)
    for f in FONT_FILES:
        if not (dest / f).is_file() or (dest / f).stat().st_size != (HOUSE_FONTS / f).stat().st_size:
            shutil.copyfile(HOUSE_FONTS / f, dest / f)
    return os.path.relpath(dest, out.parent).replace(os.sep, "/") + "/"


def render_page(md: Path, out: Path, template: str) -> dict[str, int]:
    doc = parse(md.read_text(encoding="utf-8"))
    fields = bib_for(md)
    h1 = next((b[2] for b in doc.blocks if b[0] == "h" and b[1] == 1), None)
    r = Renderer(doc)
    title_html = r.inline(h1, live=False) if h1 else html.escape(fields.get("title") or md.stem)
    title_text = re.sub(r"<[^>]+>", "", title_html)
    body, toc = r.body(skip_first_h1=h1 is not None)
    notes = r.notes()
    cjk = len(CJK.findall(body))
    base = font_base(out)
    fonts = "" if base is None else "\n".join(
        f"@font-face {{ font-family: 'ENS Font'; src: url('{base}{f}') format('woff2'); "
        f"font-weight: {w}; font-display: swap; }}" for f, w in zip(FONT_FILES, ("100 500", "600 900")))
    toc_html = "\n".join(f'<li class="l{lvl}"><a href="#{hid}">{html.escape(t)}</a></li>' for lvl, hid, t in toc)
    prov = "".join(f"<p>{html.escape(p)}</p>" for p in doc.provenance if p)
    pages = [b[1] for b in doc.blocks if b[0] == "pg"]
    subs = {
        "LANG": "zh-Hant" if cjk > len(body) * 0.05 else "en",
        "TITLE": html.escape(title_text),
        "TITLE_HTML": title_html,
        "KEY": html.escape(md.stem),
        "CITE": html.escape(cite_line(fields)),
        "PROVENANCE": f'<details class="provenance"><summary>關於這份文本</summary>{prov}</details>' if prov else "",
        "FONTS": fonts,
        "FIRST_PAGE": f"p. {pages[0]}" if pages else "",
        "TOC": toc_html,
        "TOC_CLASS": "" if len(toc) > 1 else " empty",
        "BODY": body,
        "NOTES": f'<section class="notes" aria-label="註釋"><h2>註釋</h2><ol>{notes}</ol></section>' if notes else "",
    }
    page = re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: subs.get(m.group(1), m.group(0)), template)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    joined = sum(b[1].count(f"{TOK_OPEN}PG:") for b in doc.blocks if b[0] == "p")
    return {"pages": len(pages) + joined, "joined": joined, "notes": len(doc.notes),
            "unreferenced": sum(1 for n in doc.notes if not n.refs), "headings": len(toc)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Render a source transcript as a reading page.")
    ap.add_argument("source", help="citation key, or a path to a transcript .md")
    ap.add_argument("--out", help="output .html (default: <course>/_output/<key>.html)")
    args = ap.parse_args()
    sys.path.insert(0, str(HERE))
    md = find_transcript(args.source)
    if args.out:
        out = Path(args.out).resolve()
    else:
        try:
            from _paths import course_root
            out = course_root() / "_output" / f"{md.stem}.html"
        except SystemExit:
            out = md.with_suffix(".html")
    s = render_page(md, out, TEMPLATE.read_text(encoding="utf-8"))
    print(f"{out}\n  pages {s['pages']} · paragraphs rejoined across a break {s['joined']} · "
          f"notes {s['notes']} · headings {s['headings']}")
    if s["unreferenced"]:
        print(f"  {s['unreferenced']} note(s) have no ref in the text — check the transcript's <sup> marks",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
