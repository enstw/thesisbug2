#!/usr/bin/env python3
"""Find thesis topics with the owner, a few dimension pairs at a time.

    ./fw topic-enumerate init [<unit>]                       write topic-enum/anchor.md to fill in
    ./fw topic-enumerate params                              print the 39 dimensions
    ./fw topic-enumerate start [<unit>] [--materials GLOB…]  open a run and list the materials already here
    ./fw topic-enumerate serve [<unit>]                      the owner's page, on 127.0.0.1
    ./fw topic-enumerate next [<unit>]                       print the prompts ready to send; waits for the owner
    ./fw topic-enumerate take [<unit>]                       check the answers that have arrived and record them
    ./fw topic-enumerate choose [<unit>] <action> [<topic>]  what a button on the page does
    ./fw topic-enumerate shortlist [<unit>]                  the topics in the owner's drawer, as Markdown

The owner works through three pages: the anchor (field and phenomenon), the
materials (those already in the course, plus news an agent collects within a
scope the owner confirms), and the search. There, the 39 TRIZ parameters, read
as social-science dimensions, give 741 pairs in a shuffled order. Each button the owner presses on the page writes prompts for
unseen pairs; `next` hands them to the agent, readers answer them in parallel,
and `take` refuses an answer that skips a pair or cites a passage the materials
lack. A draw that finds nothing is repeated until a topic turns up. The owner
collects topics, extends them, or returns to the categories. Method:
topic-scout reference/enumeration.md.
"""

from __future__ import annotations

import argparse
import datetime
import fcntl
import hashlib
import json
import os
import random
import re
import secrets
import sys
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _paths import course_root, rel, resolve_unit, topic_enum_paths  # noqa: E402

ASSETS = HERE.parent / ".agents" / "skills" / "topic-scout" / "assets"
PARAMS = ASSETS / "triz-parameters.json"
PAIRS_TEMPLATE = ASSETS / "enum-prompt.md"
REFINE_TEMPLATE = ASSETS / "refine-prompt.md"
SCOPE_TEMPLATE = ASSETS / "scope-prompt.md"
COLLECT_TEMPLATE = ASSETS / "collect-prompt.md"
PAGE = ASSETS / "explorer.html"

SHOWN_HEADS = ("領域", "現象")
WITHHELD_HEADS = ("可得資料", "指導與限制")
HEADS = (*SHOWN_HEADS, *WITHHELD_HEADS)
PLACEHOLDER = "〔"
FOCUS, OTHER = "甲", "乙"
TEXT_FIELDS = ("question", "scope", "data", "why")
PAIR_KINDS = ("explore", "deepen")
SETUP_KINDS = ("scope", "collect")
ACTIONS = ("explore", "deepen", "vary", "split", "keep", "drop", "finish")
SETUP_ACTIONS = ("anchor", "back", "use", "scope", "collect", "begin")
EVERY_ACTION = (*SETUP_ACTIONS, *ACTIONS)
COLLECT_COUNT, COLLECT_CHARS = 15, 2000
FOUND = "題目"
WARN_CHARS = 80_000
EXIT_WAITING, EXIT_FINISHED = 3, 5

ANCHOR_SKELETON = """# 選題定錨

<!-- 「領域」與「現象」會原文放進每一份 prompt，讀的人只看得到這兩節和材料，
     所以要寫到不認識這個題目的人也看得懂。「可得資料」與「指導與限制」留給
     之後的篩選，不會給讀的人看。填完後刪掉所有〔〕。 -->

## 領域

〔學門與次領域〕

## 現象

〔想研究的具體現象：誰、在哪裡、什麼時候、發生了什麼。越具體，題目越落地。〕

## 可得資料

〔拿得到的資料、場域或受訪者〕

## 指導與限制

〔指導教授專長、修業年限、篇幅〕
"""


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def load_params() -> dict:
    data = json.loads(PARAMS.read_text(encoding="utf-8"))
    data["by_n"] = {p["n"]: p for p in data["parameters"]}
    return data


def pair_id(a: int, b: int) -> str:
    return f"{min(a, b):02d}x{max(a, b):02d}"


def pair_of(pid: str) -> tuple[int, int]:
    a, b = pid.split("x")
    return int(a), int(b)


def all_pairs(count: int) -> list[str]:
    return [pair_id(a, b) for a in range(1, count + 1) for b in range(a + 1, count + 1)]


def dimension(p: dict) -> str:
    return f"{p['analogy']}（例如：{p['examples']}）"


def fill(template: Path, fields: dict[str, str]) -> str:
    text = template.read_text(encoding="utf-8")
    token = re.compile(r"\{\{([A-Z_]+)\}\}")
    unknown = sorted(set(token.findall(text)) - set(fields))
    if unknown:
        sys.exit(f"{template.name} uses tokens this command does not fill: {', '.join(unknown)}")
    return token.sub(lambda m: fields[m.group(1)], text)


def anchor_sections(path: Path) -> dict[str, str]:
    """The four sections of anchor.md as written so far; blanks where nothing is."""
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    sections: dict[str, str] = {}
    head = None
    for line in re.sub(r"<!--.*?-->", "", text, flags=re.S).splitlines():
        m = re.match(r"##\s+(.+?)\s*$", line)
        if m:
            head = m.group(1)
            sections[head] = ""
        elif head:
            sections[head] += line + "\n"
    return {h: sections.get(h, "").strip() for h in HEADS}


def anchor_problems(fields: dict[str, str]) -> list[str]:
    return [f"「{h}」還沒填" for h in HEADS if not fields.get(h) or PLACEHOLDER in fields[h]]


def anchor_text(fields: dict[str, str]) -> str:
    return "\n\n".join(f"**{h}**\n\n{fields[h]}" for h in SHOWN_HEADS)


def course_field() -> str:
    course = course_root() / "COURSE.md"
    found = re.search(r"^\|\s*Field\s*\|\s*(.+?)\s*\|\s*$", course.read_text(encoding="utf-8"), re.M) \
        if course.is_file() else None
    return found.group(1) if found else ""


def content_lines(text: str) -> tuple[list[str], dict[str, str]]:
    """A material's lines with capture notes and front matter blanked, and the front matter."""
    # Transcripts written by the fetch tools open with an HTML comment about the capture and
    # then trafilatura's front matter (course refs/, seen 2026-11-14); neither is the source's text.
    lines = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S).splitlines()
    meta: dict[str, str] = {}
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is not None and lines[first].strip() == "---":
        for i in range(first + 1, len(lines)):
            if lines[i].strip() == "---":
                for line in lines[first + 1:i]:
                    key, sep, value = line.partition(":")
                    if sep:
                        meta[key.strip()] = value.strip().strip("\"'")
                lines[first:i + 1] = [""] * (i + 1 - first)
                break
    return lines, meta


def material_record(path: Path, number: int, origin: str) -> dict:
    text = path.read_text(encoding="utf-8")
    lines, meta = content_lines(text)
    heading = re.search(r"^#+\s+(.+?)\s*$", "\n".join(lines), re.M)
    return {"id": f"M{number:02d}", "file": rel(path),
            "title": meta.get("title") or (heading.group(1) if heading else path.stem),
            "source": meta.get("source") or meta.get("sitename") or meta.get("hostname") or "",
            "date": meta.get("date", ""), "url": meta.get("url", ""),
            "chars": len(text), "use": True, "origin": origin}


def material_files(unit: Path, patterns: list[str] | None, default_dir: Path) -> list[Path]:
    root = course_root().resolve()
    found: list[Path] = []
    if patterns:
        for pat in patterns:
            hits = sorted(p for base in (unit, root) for p in base.glob(pat) if p.is_file())
            if not hits:
                sys.exit(f"--materials {pat!r} matches no file under {rel(unit)} or the course root")
            found += hits
    elif default_dir.is_dir():
        found = sorted(p for p in default_dir.rglob("*") if p.suffix in (".md", ".txt") and p.is_file())
    out: list[Path] = []
    for p in found:
        p = p.resolve()
        if not p.is_relative_to(root):
            sys.exit(f"material outside the course repo: {p}")
        if p not in out:
            out.append(p)
    return out


def split_passages(text: str) -> list[tuple[int, str, bool]]:
    """(first line, block, is_heading) for each blank-line-separated block."""
    lines, _ = content_lines(text)
    blocks: list[tuple[int, str, bool]] = []
    buf: list[str] = []
    first = 0
    for i in range(len(lines) + 1):
        line = lines[i] if i < len(lines) else ""
        if line.strip():
            if not buf:
                first = i + 1
            buf.append(line.rstrip())
            continue
        if buf:
            blocks.append((first, "\n".join(buf), all(b.lstrip().startswith("#") for b in buf)))
            buf = []
    return blocks


def read_materials(materials: list[dict]) -> tuple[list[dict], str]:
    """Numbered passages and the text shown in a prompt."""
    root = course_root()
    passages: list[dict] = []
    shown: list[str] = []
    for m in materials:
        shown.append(f"### 材料 {int(m['id'][1:])}：{m['title']}")
        count = 0
        for line, block, heading in split_passages((root / m["file"]).read_text(encoding="utf-8")):
            if heading:
                shown += ["〈" + b.lstrip("# \t") + "〉" for b in block.splitlines()]
                continue
            count += 1
            pid = f"{m['id']}-P{count:03d}"
            passages.append({"id": pid, "file": m["file"], "line": line, "text": block})
            shown.append(f"[{pid}] {block}")
    return passages, "\n\n".join(shown)


@contextmanager
def locked(paths: dict[str, Path]):
    """Exclusive access to a run's ledger, which the page, `next` and `take` all write."""
    if not paths["state"].is_file():
        sys.exit(f"no run at {rel(paths['run'])} — open one with: ./fw topic-enumerate start")
    with open(paths["lock"], "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        state = json.loads(paths["state"].read_text(encoding="utf-8"))
        before = dump(state)
        yield state
        after = dump(state)
        if after != before:
            tmp = paths["state"].with_suffix(".tmp")
            tmp.write_text(after, encoding="utf-8")
            os.replace(tmp, paths["state"])


def outstanding(state: dict) -> list[dict]:
    return [t for t in state["tasks"] if t["status"] != "done"]


def topic_by_id(state: dict, tid) -> dict | None:
    return next((t for t in state["topics"] if t["id"] == tid), None)


def unseen(state: dict, params: dict, group: str | None = None, focus: int | None = None) -> list[tuple[int, int]]:
    """Pairs neither read nor out with a reader, in the run's shuffled order."""
    by_n = params["by_n"]
    held = {pair_id(a, b) for t in outstanding(state) if t["kind"] in PAIR_KINDS for a, b in t["items"]}
    out = []
    for pid in state["order"]:
        if pid in state["visited"] or pid in held:
            continue
        a, b = pair_of(pid)
        if group and group not in (by_n[a]["group"], by_n[b]["group"]):
            continue
        if focus and focus not in (a, b):
            continue
        out.append((a, b))
    return out


def choice_problem(state: dict, params: dict, choice: dict) -> str | None:
    """Why the owner's choice cannot be taken now, in words the page shows."""
    action = choice.get("action")
    topic = topic_by_id(state, choice.get("topic"))
    if action in ("keep", "drop", "deepen", "vary", "split") and not topic:
        return "找不到這個題目"
    if action in ("keep", "drop", "finish"):
        return None
    if action not in ACTIONS:
        return "不認得這個動作"
    if state["stage"] != "explore":
        return "還沒開始選題"
    if state["finished"]:
        return "這一輪已經結束"
    if len(outstanding(state)) >= state["limit"]:
        return f"已經有 {len(outstanding(state))} 份在進行，等它們回來再按"
    if action == "explore":
        group = choice.get("group")
        if group and group not in {p["group"] for p in params["parameters"]}:
            return "沒有這個類別"
        return None if unseen(state, params, group=group) else "這個範圍的配對都看過或正在看了"
    if action == "deepen":
        if choice.get("dimension") not in (topic["improves"], topic["worsens"]):
            return "這個面向不屬於這個題目"
        return None if unseen(state, params, focus=choice["dimension"]) else "這個面向的配對都看過或正在看了"
    if action in topic["done"]:
        return "這個題目已經做過了"
    if action == "vary" and topic["kind"] == "vary":
        return "這個題目本身就是變化出來的"
    return None


def apply_choice(paths: dict, state: dict, params: dict, choice: dict) -> str | None:
    """Take the owner's choice: change the drawer, or write the prompts it calls for."""
    if choice.get("action") in SETUP_ACTIONS:
        return apply_setup(paths, state, choice)
    problem = choice_problem(state, params, choice)
    if problem:
        return problem
    action, tid = choice["action"], choice.get("topic")
    if action == "keep":
        if tid not in state["drawer"]:
            state["drawer"].append(tid)
    elif action == "drop":
        if tid in state["drawer"]:
            state["drawer"].remove(tid)
    elif action == "finish":
        state["finished"] = True
    elif action == "explore":
        start_round(paths, state, params, choice.get("group"))
    elif action == "deepen":
        focus = choice["dimension"]
        pairs = [(focus, b if a == focus else a)
                 for a, b in unseen(state, params, focus=focus)[:state["deepen"]]]
        pair_tasks(paths, state, params, "deepen", pairs, topic=tid, focus=focus)
    else:
        topic = topic_by_id(state, tid)
        topic["done"].append(action)
        if action == "vary":
            items = [t["name"] for t in params["types"] if t["name"] != topic["type"]]
        else:
            items = [a["name"] for a in params["axes"]]
        new_task(paths, state, {"kind": action, "items": items, "topic": tid},
                 lambda answer: refine_prompt(paths, state, params, topic, action, items, answer))
    return None


def scope_problems(scope) -> list[str]:
    if not isinstance(scope, dict):
        return ["搜尋範圍的格式不對"]
    out = []
    words = scope.get("keywords")
    if not isinstance(words, list) or not words or not all(isinstance(w, str) and w.strip() for w in words):
        out.append("至少要有一個搜尋詞")
    for key, label in (("from", "起始日期"), ("to", "結束日期")):
        if not isinstance(scope.get(key), str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", scope[key]):
            out.append(f"{label}要寫成 YYYY-MM-DD")
    if not out and scope["from"] > scope["to"]:
        out.append("起始日期晚於結束日期")
    sources = scope.get("sources", [])
    if not isinstance(sources, list) or not all(isinstance(x, str) for x in sources):
        out.append("來源要一行一個")
    return out


def clean_scope(scope: dict) -> dict:
    return {"keywords": [w.strip() for w in scope["keywords"]], "from": scope["from"], "to": scope["to"],
            "sources": [x.strip() for x in scope.get("sources", []) if x.strip()],
            "note": str(scope.get("note") or "").strip()}


def have_lines(state: dict) -> str:
    return "\n".join(f"- {m['title']}" for m in state["materials"]) or "（還沒有）"


def scope_prompt(state: dict, answer: str) -> str:
    example = {"keywords": ["……", "……"], "from": "YYYY-MM-DD", "to": "YYYY-MM-DD",
               "sources": ["……", "……"], "note": "……"}
    return fill(SCOPE_TEMPLATE, {
        "ANCHOR": anchor_text(state["anchor_fields"]), "HAVE": have_lines(state),
        "TODAY": datetime.date.today().isoformat(), "RESPONSE_PATH": answer, "EXAMPLE": dump(example).rstrip()})


def collect_prompt(paths: dict, state: dict, answer: str) -> str:
    scope = state["scope"]
    example = {"items": [{"file": "2026-03-reuters-export-rule.md", "title": "……", "source": "……",
                          "date": "YYYY-MM-DD", "url": "https://……"}],
               "failed": [{"what": "……", "reason": "要付費，只看得到第一段"}]}
    return fill(COLLECT_TEMPLATE, {
        "ANCHOR": anchor_text(state["anchor_fields"]),
        "KEYWORDS": "\n".join(f"  - {w}" for w in scope["keywords"]),
        "FROM": scope["from"], "TO": scope["to"],
        "SOURCES": "\n".join(f"  - {x}" for x in scope["sources"]) or "  - 不限",
        "HAVE": have_lines(state), "COUNT": str(COLLECT_COUNT), "LIMIT": str(COLLECT_CHARS),
        "DIR": rel(paths["materials"]), "RESPONSE_PATH": answer, "EXAMPLE": dump(example).rstrip()})


def apply_setup(paths: dict, state: dict, choice: dict) -> str | None:
    """The owner's choices before the search opens: the anchor, the materials, the start."""
    action = choice["action"]
    if state["stage"] == "explore":
        return "已經開始選題，定錨和材料不能再改；要改請另開一輪"
    busy = outstanding(state)
    if action == "anchor":
        given = choice.get("fields")
        if given is not None and not isinstance(given, dict):
            return "定錨的格式不對"
        fields = {h: str(given.get(h) or "").strip() for h in HEADS} if given else anchor_sections(paths["anchor"])
        problems = anchor_problems(fields)
        if problems:
            return "；".join(problems)
        paths["anchor"].parent.mkdir(parents=True, exist_ok=True)
        paths["anchor"].write_text(
            "# 選題定錨\n\n" + "\n\n".join(f"## {h}\n\n{fields[h]}" for h in HEADS) + "\n", encoding="utf-8")
        state.update(anchor_fields=fields, stage="materials")
    elif action == "back":
        state["stage"] = "anchor"
    elif action == "use":
        found = next((m for m in state["materials"] if m["id"] == choice.get("material")), None)
        if not found:
            return "找不到這份材料"
        found["use"] = bool(choice.get("on"))
    elif action in ("scope", "collect"):
        if state["stage"] != "materials":
            return "先完成定錨"
        if busy:
            return "上一個工作還在進行"
        if action == "scope":
            new_task(paths, state, {"kind": "scope", "items": []}, lambda answer: scope_prompt(state, answer))
        else:
            scope = choice.get("scope") or state["scope"]
            problems = scope_problems(scope) if scope else ["還沒有搜尋範圍"]
            if problems:
                return "；".join(problems)
            state["scope"] = clean_scope(scope)
            new_task(paths, state, {"kind": "collect", "items": []},
                     lambda answer: collect_prompt(paths, state, answer))
    else:
        if busy:
            return "上一個工作還在進行"
        problems = anchor_problems(state["anchor_fields"])
        if problems:
            return "；".join(problems)
        passages, shown = read_materials([m for m in state["materials"] if m["use"]])
        if not passages:
            return "至少要勾選一份有內文的材料，因為每個題目都必須指到材料裡的段落"
        paths["passages"].write_text(dump(passages), encoding="utf-8")
        paths["shown"].write_text(shown, encoding="utf-8")
        state.update(anchor=anchor_text(state["anchor_fields"]), stage="explore")
    return None


def record_setup(paths: dict, state: dict, task: dict, data) -> list[str]:
    """Problems in a scope or collection answer; when there are none, it is recorded."""
    if task["kind"] == "scope":
        problems = scope_problems(data)
        if problems:
            return problems
        state["scope"] = clean_scope(data)
        task.update(status="done", found=0)
        return []
    if not isinstance(data, dict) or not isinstance(data.get("items"), list) \
            or not isinstance(data.get("failed"), list):
        return ['top level must be {"items": [...], "failed": [...]}']
    errors: list[str] = []
    files: list[Path] = []
    for i, item in enumerate(data["items"], 1):
        name = item.get("file") if isinstance(item, dict) else None
        if not isinstance(name, str) or "/" in name or not name.endswith(".md"):
            errors.append(f"item {i}: file must be the name of a .md file in {rel(paths['materials'])}/")
        elif not (paths["materials"] / name).is_file() or not (paths["materials"] / name).read_text(encoding="utf-8").strip():
            errors.append(f"item {i}: {name} is not in {rel(paths['materials'])}/ or is empty")
        else:
            files.append(paths["materials"] / name)
    for i, item in enumerate(data["failed"], 1):
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item[k].strip()
                                                 for k in ("what", "reason")):
            errors.append(f"failed {i}: needs what and reason")
    if errors:
        return errors
    known = {m["file"] for m in state["materials"]}
    added = 0
    for path in files:
        if rel(path) not in known:
            state["materials"].append(material_record(path, len(state["materials"]) + 1, "collected"))
            known.add(rel(path))
            added += 1
    state["failed"] += [{"what": f["what"].strip(), "reason": f["reason"].strip()} for f in data["failed"]]
    task.update(status="done", found=added)
    return []


def none_lines(kinds: list[dict]) -> str:
    return "\n".join(f"   - **{k['name']}**：{k['means']}。" for k in kinds)


def pairs_prompt(paths: dict, state: dict, params: dict, items: list[list[int]], answer: str) -> str:
    by_n = params["by_n"]
    first = json.loads(paths["passages"].read_text(encoding="utf-8"))[0]["id"]
    example = {"rows": [
        {"n": 1, "topics": [{"question": "……", "type": params["types"][0]["name"], "improves": FOCUS,
                             "scope": "……", "data": "……", "why": "……", "passages": [first]}]},
        {"n": 2, "topics": [], "none": params["none_kinds"][0]["name"], "reason": "……"}]}
    return fill(PAIRS_TEMPLATE, {
        "ANCHOR": state["anchor"],
        "COUNT": str(len(items)),
        "PAIRS": "\n".join(f"{i}. {FOCUS}：{dimension(by_n[a])}\n   {OTHER}：{dimension(by_n[b])}"
                           for i, (a, b) in enumerate(items, 1)),
        "TYPES": "\n".join(f"- **{t['name']}**：{t['asks']}" for t in params["types"]),
        "NONE_KINDS": none_lines(params["none_kinds"]),
        "MATERIALS": paths["shown"].read_text(encoding="utf-8"),
        "RESPONSE_PATH": answer,
        "EXAMPLE": dump(example).rstrip(),
    })


def refine_prompt(paths: dict, state: dict, params: dict, topic: dict, kind: str,
                  items: list[str], answer: str) -> str:
    by_n = params["by_n"]
    passages = {p["id"]: p["text"] for p in json.loads(paths["passages"].read_text(encoding="utf-8"))}
    if kind == "vary":
        asks = {t["name"]: t["asks"] for t in params["types"]}
        task = "原題目只是這個矛盾的一種問法。保持同一個矛盾，照下面每一種題型各寫出新的題目；某一種寫不出來就說明理由。"
    else:
        asks = {a["name"]: a["asks"] for a in params["axes"]}
        task = "原題目的範圍可以切得更窄。保持同一個矛盾，照下面每一種切法各寫出範圍更窄的題目；某一種切不出來就說明理由。"
    example = {"rows": [
        {"n": 1, "topics": [{"question": "……", "scope": "……", "data": "……", "why": "……",
                             "passages": [topic["passages"][0]]}]},
        {"n": 2, "topics": [], "none": params["refine_none_kinds"][0]["name"], "reason": "……"}]}
    return fill(REFINE_TEMPLATE, {
        "ANCHOR": state["anchor"],
        "QUESTION": topic["question"], "TYPE": topic["type"], "SCOPE": topic["scope"], "WHY": topic["why"],
        "IMPROVES": dimension(by_n[topic["improves"]]),
        "WORSENS": dimension(by_n[topic["worsens"]]),
        "CITED": "".join(f"\n  [{pid}] {passages[pid]}" for pid in topic["passages"]),
        "TASK": task,
        "ROWS": "\n".join(f"{i}. **{name}**：{asks[name]}" for i, name in enumerate(items, 1)),
        "NONE_KINDS": none_lines(params["refine_none_kinds"]),
        "MATERIALS": paths["shown"].read_text(encoding="utf-8"),
        "RESPONSE_PATH": answer,
        "EXAMPLE": dump(example).rstrip(),
    })


def new_task(paths: dict, state: dict, fields: dict, text_for) -> dict:
    """Write one prompt and record it as ready to send."""
    tid = f"T{len(state['tasks']) + 1:03d}"
    text = text_for(rel(paths["answers"] / f"{tid}.json"))
    for d in (paths["tasks"], paths["answers"]):
        d.mkdir(parents=True, exist_ok=True)
    (paths["tasks"] / f"{tid}.md").write_text(text, encoding="utf-8")
    task = {"id": tid, **fields, "status": "new", "prompt_sha256": sha(text)}
    state["tasks"].append(task)
    return task


def pair_tasks(paths: dict, state: dict, params: dict, kind: str, pairs: list[tuple[int, int]], **fields) -> int:
    """One prompt per `batch` pairs, so several readers work at once."""
    size = state["batch"]
    for i in range(0, len(pairs), size):
        items = [list(p) for p in pairs[i:i + size]]
        new_task(paths, state, {"kind": kind, "items": items, **fields},
                 lambda answer, items=items: pairs_prompt(paths, state, params, items, answer))
    return -(-len(pairs) // size)


def start_round(paths: dict, state: dict, params: dict, group: str | None) -> int:
    """Draw the next unseen pairs of a category for `fan` readers."""
    pairs = unseen(state, params, group=group)[:state["fan"] * state["batch"]]
    if not pairs:
        return 0
    rid = len(state["rounds"]) + 1
    state["rounds"].append({"id": rid, "group": group, "closed": False})
    return pair_tasks(paths, state, params, "explore", pairs, group=group, round=rid)


def close_rounds(paths: dict, state: dict, params: dict) -> None:
    """A draw that found nothing is followed by another, until a topic turns up."""
    for rnd in state["rounds"]:
        tasks = [t for t in state["tasks"] if t.get("round") == rnd["id"]]
        if rnd["closed"] or any(t["status"] != "done" for t in tasks):
            continue
        rnd["closed"] = True
        if not sum(t["found"] for t in tasks) and not state["finished"]:
            again = start_round(paths, state, params, rnd["group"])
            print(f"round {rnd['id']} found nothing; " + (f"drew {again} more prompt(s), run next"
                                                          if again else "nothing left to draw there"))


def check_answer(data, task: dict, params: dict, passage_ids: set[str]) -> tuple[list[str], dict[int, dict]]:
    """Problems in one answer file, and its rows by number."""
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        return ['top level must be {"rows": [...]}'], {}
    pairs = task["kind"] in PAIR_KINDS
    kinds = {k["name"] for k in params["none_kinds" if pairs else "refine_none_kinds"]}
    types = {t["name"] for t in params["types"]}
    expected = len(task["items"])
    errors: list[str] = []
    seen: dict[int, dict] = {}
    for row in data["rows"]:
        n = row.get("n") if isinstance(row, dict) else None
        if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= expected:
            errors.append(f"row n={n!r}: not one of the {expected} it was given")
        elif n in seen:
            errors.append(f"row {n}: answered twice")
        else:
            seen[n] = row
    missing = [str(n) for n in range(1, expected + 1) if n not in seen]
    if missing:
        errors.append("no row for " + ", ".join(missing))
    for n in sorted(seen):
        row = seen[n]
        topics = row.get("topics")
        if not isinstance(topics, list):
            errors.append(f"row {n}: topics must be a list")
            continue
        if not topics:
            if row.get("none") not in kinds:
                errors.append(f"row {n}: no topics, so none must be one of {'／'.join(sorted(kinds))}")
            if not isinstance(row.get("reason"), str) or not row["reason"].strip():
                errors.append(f"row {n}: no topics, so reason must say why")
        for ti, topic in enumerate(topics, 1):
            where = f"row {n} topic {ti}"
            if not isinstance(topic, dict):
                errors.append(f"{where}: must be an object")
                continue
            for field in TEXT_FIELDS:
                if not isinstance(topic.get(field), str) or not topic[field].strip():
                    errors.append(f"{where}: {field} is missing or empty")
            if pairs and topic.get("type") not in types:
                errors.append(f"{where}: type must be one of {'／'.join(sorted(types))}")
            if pairs and topic.get("improves") not in (FOCUS, OTHER):
                errors.append(f"{where}: improves must be {FOCUS} or {OTHER}")
            cited = topic.get("passages")
            if not isinstance(cited, list) or not cited:
                errors.append(f"{where}: passages must list at least one passage number")
            else:
                unknown = [str(c) for c in cited if c not in passage_ids]
                if unknown:
                    errors.append(f"{where}: passages not in the materials: " + ", ".join(unknown))
    return errors, seen


def record(state: dict, task: dict, rows: dict[int, dict]) -> int:
    """Add an accepted answer's topics to the ledger; returns how many."""
    pairs = task["kind"] in PAIR_KINDS
    parent = topic_by_id(state, task.get("topic"))
    found = 0
    for n in sorted(rows):
        row = rows[n]
        if pairs:
            a, b = task["items"][n - 1]
            state["visited"][pair_id(a, b)] = {"task": task["id"],
                                               "result": FOUND if row["topics"] else row["none"]}
        for topic in row["topics"]:
            if pairs:
                improves, worsens = (a, b) if topic["improves"] == FOCUS else (b, a)
                extra = {"type": topic["type"], "axis": None, "parent": None}
            else:
                improves, worsens = parent["improves"], parent["worsens"]
                name = task["items"][n - 1]
                extra = {"type": name if task["kind"] == "vary" else parent["type"],
                         "axis": name if task["kind"] == "split" else None, "parent": parent["id"]}
            found += 1
            state["topics"].append({
                "id": f"Q{len(state['topics']) + 1:03d}", "task": task["id"], "kind": task["kind"],
                "pair": pair_id(improves, worsens), "improves": improves, "worsens": worsens,
                **extra, **{f: topic[f].strip() for f in TEXT_FIELDS},
                "passages": topic["passages"], "done": []})
    task.update(status="done", found=found)
    return found


def cmd_init(args) -> int:
    paths = topic_enum_paths(resolve_unit(args.unit))
    if paths["anchor"].exists():
        print(f"{rel(paths['anchor'])} already exists; not overwritten", file=sys.stderr)
        return 1
    paths["materials"].mkdir(parents=True, exist_ok=True)
    paths["anchor"].write_text(ANCHOR_SKELETON, encoding="utf-8")
    print(f"wrote {rel(paths['anchor'])}\nfill it in, put the materials in {rel(paths['materials'])}/, "
          "then: ./fw topic-enumerate start")
    return 0


def cmd_params(_args) -> int:
    group = None
    for p in load_params()["parameters"]:
        if p["group"] != group:
            group = p["group"]
            print(f"\n{group}")
        print(f"  {p['n']:>2}  {p['analogy']}（{p['triz']}）：{p['examples']}")
    return 0


def cmd_start(args) -> int:
    unit = resolve_unit(args.unit)
    paths = topic_enum_paths(unit, args.run)
    if paths["state"].exists():
        sys.exit(f"{rel(paths['run'])} already exists; continue it with next, or open another with --run <name>. "
                 "A run keeps the anchor and materials it started with, so answers are never checked "
                 "against text they were not written for.")
    params = load_params()
    fields = {h: "" if PLACEHOLDER in v else v for h, v in anchor_sections(paths["anchor"]).items()}
    fields[HEADS[0]] = fields[HEADS[0]] or course_field()
    files = material_files(unit, args.materials, paths["materials"])
    seed = args.seed if args.seed is not None else secrets.randbelow(2 ** 32)
    order = all_pairs(len(params["parameters"]))
    random.Random(seed).shuffle(order)
    paths["run"].mkdir(parents=True, exist_ok=True)
    paths["state"].write_text(dump({
        "version": 1, "run": args.run, "seed": seed, "batch": args.batch, "deepen": args.deepen,
        "fan": args.fan, "limit": args.limit, "stage": "anchor", "anchor_fields": fields, "anchor": "",
        "materials": [material_record(p, i, "local") for i, p in enumerate(files, 1)],
        "scope": None, "failed": [], "order": order, "visited": {},
        "rounds": [], "tasks": [], "topics": [], "drawer": [], "finished": False}), encoding="utf-8")
    print(f"run {args.run}: {len(order)} pairs in shuffled order (seed {seed}), {len(files)} material file(s) listed")
    print("then:  ./fw topic-enumerate serve   (keep it running; give the owner its address)\n"
          "       ./fw topic-enumerate next    (waits until the owner presses a button)")
    return 0


def cmd_next(args) -> int:
    paths = topic_enum_paths(resolve_unit(args.unit), args.run)
    send = ("new", "sent") if args.resend else ("new",)
    deadline = time.monotonic() + args.wait
    while True:
        with locked(paths) as state:
            if state["finished"]:
                print(f"finished: the owner closed the run with {len(state['drawer'])} topic(s) in the drawer\n"
                      "then:     ./fw topic-enumerate shortlist")
                return EXIT_FINISHED
            ready = [t for t in state["tasks"] if t["status"] in send]
            for task in ready:
                task["status"] = "sent"
                print(f"task:   {task['id']} {task['kind']}")
                print(f"prompt: {rel(paths['tasks'] / (task['id'] + '.md'))}")
                print(f"answer: {rel(paths['answers'] / (task['id'] + '.json'))}\n")
            if ready:
                return 0
        if time.monotonic() >= deadline:
            print("waiting: nothing new to send; run next again")
            return EXIT_WAITING
        time.sleep(0.5)


def cmd_take(args) -> int:
    paths = topic_enum_paths(resolve_unit(args.unit), args.run)
    params = load_params()
    rejected = 0
    with locked(paths) as state:
        passage_ids = {p["id"] for p in json.loads(paths["passages"].read_text(encoding="utf-8"))} \
            if paths["passages"].is_file() else set()
        for task in [t for t in state["tasks"] if t["status"] == "sent"]:
            prompt = paths["tasks"] / f"{task['id']}.md"
            answer = paths["answers"] / f"{task['id']}.json"
            if not answer.is_file():
                continue
            if not prompt.is_file() or sha(prompt.read_text(encoding="utf-8")) != task["prompt_sha256"]:
                sys.exit(f"{rel(prompt)} was changed after it was written; the answer cannot be checked against it")
            try:
                data = json.loads(answer.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors, rows = [f"not valid JSON: {exc}"], {}
            else:
                if task["kind"] in SETUP_KINDS:
                    errors, rows = record_setup(paths, state, task, data), None
                else:
                    errors, rows = check_answer(data, task, params, passage_ids)
            if errors:
                rejected += 1
                os.replace(answer, answer.with_suffix(".rejected.json"))
                print(f"{task['id']}: rejected; send {rel(prompt)} again", file=sys.stderr)
                for e in errors:
                    print(f"  {e}", file=sys.stderr)
                continue
            if rows is None:
                print(f"{task['id']}: accepted ({task['kind']})")
            else:
                print(f"{task['id']}: accepted, {record(state, task, rows)} topic(s)")
        close_rounds(paths, state, params)
        out = [t["id"] for t in state["tasks"] if t["status"] == "sent"]
        print(f"{len(state['visited'])}/{len(state['order'])} pairs read, {len(state['topics'])} topic(s); "
              + ("still out: " + " ".join(out) if out else "nothing out"))
    return 1 if rejected else 0


def cmd_choose(args) -> int:
    paths = topic_enum_paths(resolve_unit(args.unit), args.run)
    choice = {"action": args.action, "topic": args.topic, "group": args.group, "dimension": args.dimension,
              "material": args.topic, "on": not args.off}
    with locked(paths) as state:
        problem = apply_choice(paths, state, load_params(), choice)
    if problem:
        print(problem, file=sys.stderr)
        return 1
    return 0


def cmd_shortlist(args) -> int:
    paths = topic_enum_paths(resolve_unit(args.unit), args.run)
    by_n = load_params()["by_n"]
    with locked(paths) as state:
        topics = [topic_by_id(state, tid) for tid in state["drawer"]]
    print(f"# 抽屜裡的候選題目（{len(topics)} 題）\n")
    for t in topics:
        print(f"## {t['id']} {t['question']}\n")
        print(f"- 題型：{t['type']}" + (f"（依{t['axis']}切分）" if t["axis"] else ""))
        print(f"- 矛盾：改善「{by_n[t['improves']]['analogy']}」會惡化「{by_n[t['worsens']]['analogy']}」")
        print(f"- 對象與場域：{t['scope']}")
        print(f"- 需要的資料：{t['data']}")
        print(f"- 理由：{t['why']}")
        print(f"- 依據段落：{'、'.join(t['passages'])}\n")
    return 0


def view(state: dict, params: dict, passages: dict[str, dict]) -> dict:
    """What the page shows, including which buttons can be pressed."""
    out = outstanding(state)
    page = {
        "stage": state["stage"], "finished": state["finished"], "out": len(out),
        "working": sorted({t["kind"] for t in out}), "anchor_fields": state["anchor_fields"],
        "materials": state["materials"], "budget": WARN_CHARS,
        "used_chars": sum(m["chars"] for m in state["materials"] if m["use"]),
        "scope": state["scope"], "failed": state["failed"],
        "log": [{k: t.get(k) for k in ("id", "kind", "group", "topic", "status", "found")}
                | {"count": len(t["items"])} for t in state["tasks"][-12:]][::-1]}
    if state["stage"] != "explore":
        return page
    by_n = params["by_n"]

    def can(**choice) -> bool:
        return choice_problem(state, params, choice) is None

    groups = []
    for name in dict.fromkeys(p["group"] for p in params["parameters"]):
        inside = [pid for pid in state["order"]
                  if name in (by_n[pair_of(pid)[0]]["group"], by_n[pair_of(pid)[1]]["group"])]
        groups.append({"name": name, "total": len(inside),
                       "read": sum(pid in state["visited"] for pid in inside),
                       "ok": can(action="explore", group=name)})
    titles = {m["file"]: m["title"] for m in state["materials"]}
    topics = []
    for t in reversed(state["topics"]):
        topics.append({
            **t, "kept": t["id"] in state["drawer"],
            "improves_name": by_n[t["improves"]]["analogy"], "worsens_name": by_n[t["worsens"]]["analogy"],
            "cited": [{"id": pid, "text": passages[pid]["text"], "file": titles[passages[pid]["file"]]}
                      for pid in t["passages"]],
            "can_vary": can(action="vary", topic=t["id"]), "can_split": can(action="split", topic=t["id"]),
            "deepen": [{"n": n, "name": by_n[n]["analogy"], "ok": can(action="deepen", topic=t["id"], dimension=n)}
                       for n in (t["improves"], t["worsens"])]})
    return page | {
        "anchor": state["anchor"], "read": len(state["visited"]), "total": len(state["order"]),
        "groups": groups, "any_ok": can(action="explore"), "topics": topics, "drawer": state["drawer"]}


def make_server(paths: dict[str, Path], port: int) -> ThreadingHTTPServer:
    params = load_params()
    cache: dict[str, dict] = {}

    def passages() -> dict[str, dict]:
        if not cache and paths["passages"].is_file():
            cache.update((p["id"], p) for p in json.loads(paths["passages"].read_text(encoding="utf-8")))
        return cache

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args) -> None:
            pass

        def send(self, status: int, body: bytes, kind: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, status: int, obj) -> None:
            self.send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                      "application/json; charset=utf-8")

        def local(self) -> bool:
            return (self.headers.get("Host") or "").rsplit(":", 1)[0] in ("127.0.0.1", "localhost")

        def do_GET(self) -> None:
            if not self.local():
                return self.send_json(403, {"error": "local use only"})
            if self.path == "/":
                return self.send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            if self.path == "/state":
                with locked(paths) as state:
                    return self.send_json(200, view(state, params, passages()))
            self.send_json(404, {"error": "not found"})

        def do_POST(self) -> None:
            # Browsers let any site POST to 127.0.0.1 but require a CORS preflight before
            # adding a custom header; this server answers none (Fetch standard, 2026-11).
            if not self.local() or self.headers.get("X-Topic-Enumerate") != "1" or self.path != "/choose":
                return self.send_json(403, {"error": "local use only"})
            try:
                choice = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
            except ValueError:
                choice = None
            if not isinstance(choice, dict):
                return self.send_json(400, {"error": "bad request"})
            with locked(paths) as state:
                problem = apply_choice(paths, state, params, choice)
            self.send_json(409 if problem else 200, {"error": problem} if problem else {"ok": True})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def cmd_serve(args) -> int:
    paths = topic_enum_paths(resolve_unit(args.unit), args.run)
    if not paths["state"].is_file():
        sys.exit(f"no run at {rel(paths['run'])} — open one with: ./fw topic-enumerate start")
    try:
        server = make_server(paths, args.port)
    except OSError as exc:
        sys.exit(f"cannot listen on 127.0.0.1:{args.port} ({exc}); pass --port <number>")
    print(f"the owner's page: http://127.0.0.1:{server.server_address[1]}/   (Ctrl-C stops it)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="fw topic-enumerate", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def command(name: str, func, help_text: str, run: bool = True) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("unit", nargs="?")
        if run:
            p.add_argument("--run", default="r1", help="run name under topic-enum/runs/ (default r1)")
        p.set_defaults(func=func)
        return p

    command("init", cmd_init, "write topic-enum/anchor.md to fill in", run=False)
    sub.add_parser("params", help="print the 39 dimensions").set_defaults(func=cmd_params)
    p = command("start", cmd_start, "shuffle the 741 pairs and open a run")
    p.add_argument("--materials", nargs="+", metavar="GLOB",
                   help="files to read, relative to the unit or the course root "
                        "(default: topic-enum/materials/**/*.md and *.txt)")
    p.add_argument("--seed", type=int, help="shuffle seed (default: random, recorded in the run)")
    p.add_argument("--batch", type=int, default=5, help="pairs per prompt (default 5)")
    p.add_argument("--fan", type=int, default=4, help="prompts per category draw, read in parallel (default 4)")
    p.add_argument("--deepen", type=int, default=10, help="pairs read per deepen, split into prompts (default 10)")
    p.add_argument("--limit", type=int, default=12, help="prompts allowed out at once (default 12)")
    p = command("serve", cmd_serve, "the owner's page, on 127.0.0.1")
    p.add_argument("--port", type=int, default=8741, help="port to listen on (default 8741; 0 picks a free one)")
    p = command("next", cmd_next, "print the prompts ready to send; waits for the owner")
    p.add_argument("--wait", type=float, default=540, help="seconds to wait for the owner (default 540)")
    p.add_argument("--resend", action="store_true", help="also print prompts already sent and not yet answered")
    command("take", cmd_take, "check the answers that have arrived and record them")
    p = sub.add_parser("choose", help="what a button on the page does")
    p.add_argument("words", nargs="+", metavar="[<unit>] <action> [<topic>]",
                   help="action: " + ", ".join(EVERY_ACTION))
    p.add_argument("--off", action="store_true", help="use: leave this material out")
    p.add_argument("--run", default="r1", help="run name under topic-enum/runs/ (default r1)")
    p.add_argument("--group", help="explore: draw only pairs that touch this category")
    p.add_argument("--dimension", type=int, help="deepen: which of the topic's two dimensions to hold")
    p.set_defaults(func=cmd_choose)
    command("shortlist", cmd_shortlist, "the topics in the owner's drawer, as Markdown")

    args = ap.parse_args()
    if args.cmd == "choose":
        words = list(args.words)
        args.unit = None if words[0] in EVERY_ACTION else words.pop(0)
        if not words or words[0] not in EVERY_ACTION or len(words) > 2:
            sys.exit("usage: fw topic-enumerate choose [<unit>] <action> [<topic or material>]; action is one of "
                     + ", ".join(EVERY_ACTION))
        args.action, args.topic = words[0], (words[1] if len(words) == 2 else None)
    if getattr(args, "run", None) and not re.fullmatch(r"[A-Za-z0-9._-]+", args.run):
        sys.exit("--run takes letters, digits, dot, underscore and hyphen only")
    if min(getattr(args, name, 1) for name in ("batch", "fan", "deepen", "limit")) < 1:
        sys.exit("--batch, --fan, --deepen and --limit must be at least 1")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
