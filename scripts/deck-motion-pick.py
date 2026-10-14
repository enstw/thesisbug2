#!/usr/bin/env python3
"""Pick a motion variation (the 動態 column) for every storyboard row, with Jev or by hand.

    ./fw deck-motion-pick <talk>                 build the request, show what it would ask and the estimate; send nothing
    ./fw deck-motion-pick <talk> --ack           send it (the user acknowledged this paid call), write the picks into storyboard.md
    ./fw deck-motion-pick <talk> --answers a.json  apply answers from a file (a cached run, or picks written by hand) instead of calling
    ./fw deck-motion-pick <talk> ... --dry-run   print the picks, leave storyboard.md alone

Each storyboard row with a layout code becomes one Choice question over the
variations that `deck-compile` can apply to that layout (`_deck_motion.py`;
documented in deck-plan/reference/motion-catalog.md). The questions share one
state: the goal, the limits this script applies afterwards, the talk's
premises and every slide in order, each with its facts — position, section,
title length, lead sentence, item count, number (and whether the author marked
it the deck's key figure with a premise bullet 「關鍵數字：5,380」), minutes,
source point, neighbours. The options describe effects only (what the
audience sees, what the effect needs, when it fails); nothing tells Jev which
page type takes which code, because such hints are answer keys, and two of
them applied to one page turned the first live run's finale into a
0.53/0.38 coin-flip. Jev judges from the facts.

Afterwards the script applies what independent questions cannot: a close
race (top two within 0.15) falls back to the more restrained of the two and
says so; a diffuse answer (confidence < 0.60) is only reported, because with
eight to ten options a clear margin matters and a low confidence alone does
not (jev-decide § Why margin); one scramble per deck, at most two zooms, no
push after a transition — each downgrade is reported.

The call goes through the jev-decide runner (`JEV_DECIDE`, or a discovered
`jev-decide/scripts/jev_decide.mts`), which does the ack gate, the cache and
the cost estimate; this script never contacts the service itself. Without a
runner it still writes the request file, so an author can answer the
questions by hand and feed the answers back with --answers.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _deck_catalog import parse_slot_payload  # noqa: E402
from _deck_motion import VARIATIONS, more_restrained, options_for  # noqa: E402
from _paths import resolve_talk  # noqa: E402

# What Jev is told about the deck: the goal and the limits this script enforces afterwards. Facts only —
# no "a cover takes M-CHARS" hints; each page is described by its facts next to the options' effect
# descriptions, and Jev judges.
GOAL = "為這場簡報的每一頁選一個動態變化（活潑模式：講者每按一次，畫面多出現一拍），讓台下跟著講到的地方看，又不花俏。"
CONSTRAINTS = [
    "台下約十秒要看懂一頁；每多一拍，講者就多按一次。",
    "全場限制，送出後由程式套用：M-SCRAMBLE 全場只保留一次；M-ZOOM 最多兩次；連續兩頁不會都用轉場（M-PUSH、M-ZOOM）。",
    "每頁只選一個代碼。",
]
MIN_MARGIN, MIN_CONFIDENCE = 0.15, 0.60   # jev-decide's defaults: a margin below the first is a close race; a confidence below the second is only noted
KEY_NUMBER_RE = re.compile(r"^關鍵數字\s*[:：]\s*(.+)$")
SENTENCE_SLOTS = ("onesentence", "lead", "sub", "claim", "question", "statement")


def _rows(text: str) -> tuple[list[str], list[list[str]], list[str]]:
    """(premise bullets, table rows as column lists, header columns) of a storyboard."""
    premises, rows, headers = [], [], []
    in_table = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("- ") and not in_table:
            premises.append(s[2:].strip())
        if not s.startswith("|"):
            continue
        cols = [c.strip() for c in s.strip("|").split("|")]
        if cols and cols[0] == "#":
            headers = cols
            in_table = True
            continue
        if in_table and cols and cols[0].isdigit():
            rows.append(cols)
    return premises, rows, headers


def key_numbers(premises: list[str]) -> list[str]:
    """The figures a premise bullet 「關鍵數字：5,380、2,300 萬」 marks as the deck's key numbers."""
    out = []
    for p in premises:
        m = KEY_NUMBER_RE.match(re.sub(r"\*\*", "", p))
        if m:
            out += [x.strip() for x in re.split(r"[、,，;；]\s*", m.group(1)) if x.strip()]
    return out


def _cell(row: list[str], headers: list[str], name: str) -> str:
    try:
        i = headers.index(name)
    except ValueError:
        return ""
    return row[i] if i < len(row) else ""


def _trim(s: str, n: int) -> str:
    s = re.sub(r"<br\s*/?>", "；", s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _slots(content: str) -> dict:
    try:
        return parse_slot_payload(content or "")
    except Exception:   # a legacy row's free text is not micro-syntax; facts then say "無"
        return {}


def page_facts(i: int, slides: list[dict], keys: list[str]) -> dict[str, str]:
    """What is true of one page, computed from the storyboard, so Jev need not guess it from prose."""
    s, n = slides[i], len(slides)
    slots = s["slots"]
    title = next((slots[k] for k in ("title", "heading") if isinstance(slots.get(k), str) and slots[k]), "")
    sentence = next((k for k in SENTENCE_SLOTS if isinstance(slots.get(k), str) and slots[k]), None)
    groups = {k: len(v) for k, v in slots.items() if isinstance(v, list) and v}
    num = slots.get("num") if isinstance(slots.get("num"), str) else ""
    section = s["shape"].startswith("14")
    after_section = i > 0 and slides[i - 1]["shape"].startswith("14")
    point, prev_point = s["point"], slides[i - 1]["point"] if i > 0 else ""
    real = point and point != "—"
    return {
        "位置": f"第 {s['n']} 頁，共 {n} 頁" + ("，第一頁" if i == 0 else "") + ("，最後一頁" if i == n - 1 else ""),
        "分節": "分節頁（章節、封面或結尾）" if section else ("分節後的第一頁" if after_section else "內文頁"),
        "標題": f"{len(title)} 字「{title}」" if title else "無",
        "導語": f"{sentence} {len(slots[sentence])} 字" if sentence else "無",
        "項目": "、".join(f"{k} {v} 組" for k, v in groups.items()) or "無",
        "數字": (f"大數字 {num}" + ("，作者標為全場關鍵數字" if any(k and k in num for k in keys) else "")) if num else "無",
        "講述": s["minutes"] or "未填",
        "論點": (f"與前一頁同一來源論點（{point}）" if real and point == prev_point else
                 f"來源論點 {point}" + ("，與前一頁不同" if i > 0 and prev_point else "") if real else "無來源論點"),
    }


def _neighbour(slides: list[dict], i: int) -> str:
    if not 0 <= i < len(slides):
        return "無"
    s = slides[i]
    return f"{s['layout'] or '（無版型代碼）'}（{s['shape']}，{s['point'] or '—'}）"


def build_request(talk: Path) -> dict:
    """One Jev raw request: shared state + one Choice per layout row (ids s<row#>)."""
    text = (talk / "storyboard.md").read_text(encoding="utf-8")
    premises, rows, headers = _rows(text)
    keys = key_numbers(premises)
    slides = []
    for r in rows:
        content = _cell(r, headers, "畫面內容")
        slides.append({
            "n": r[0], "layout": _cell(r, headers, "版型"), "shape": _cell(r, headers, "內容形狀"),
            "point": _cell(r, headers, "來源論點"), "minutes": _cell(r, headers, "講"),
            "content": _trim(content, 220), "spoken": _trim(_cell(r, headers, "口說重點"), 120),
            "slots": _slots(content),
        })
    for i in range(len(slides)):
        slides[i]["facts"] = page_facts(i, slides, keys)
    state = {
        "goal": GOAL,
        "constraints": CONSTRAINTS,
        "premises": premises,
        "slides": [{k: v for k, v in s.items() if k != "slots"} for s in slides],
    }
    questions = {}
    for i, s in enumerate(slides):
        opts = options_for(s["layout"]) if re.match(r"L-[A-Z0-9-]+$", s["layout"]) else {}
        if not opts:
            continue
        facts = "；".join(f"{k}：{v}" for k, v in s["facts"].items())
        questions[f"s{s['n']}"] = {
            "type": "choice",
            "instructions": (f"第 {s['n']} 頁。版型 {s['layout']}，內容形狀「{s['shape']}」。事實：{facts}。"
                             f"前一頁：{_neighbour(slides, i - 1)}；後一頁：{_neighbour(slides, i + 1)}。"
                             f"畫面內容：{s['content']}。口說重點：{s['spoken']}。"
                             f"依 state 的 goal 與 constraints，為這一頁選一個最合適的動態；每個選項都寫了台下看到什麼、好處與代價（含它需要什麼才成立），要權衡。"),
            "criteria": {code: {"what": v["what"], "pros": v["pros"], "cons": v["cons"]} for code, v in opts.items()},
        }
    return {"state": state, "questions": questions, "meta": {"talk": str(talk), "tool": "deck-motion-pick"}}


def _dist(answer) -> tuple[list[tuple[str, float]], float]:
    """((code, probability) best first, confidence) from one Jev answer, whatever its exact shape."""
    if isinstance(answer, str):
        return [(answer, 0.0)], 0.0
    if not isinstance(answer, dict):
        return [], 0.0
    probs = {str(k): float(v) for k, v in (answer.get("probabilities") or {}).items()}
    pick = answer.get("choice") or answer.get("answer") or answer.get("value")
    if pick and str(pick) not in probs:
        probs[str(pick)] = float(answer.get("confidence", 0.0) or 0.0)
    ranked = sorted(probs.items(), key=lambda kv: -kv[1])
    if pick:   # the service's own pick stays first whatever the rounding
        ranked.sort(key=lambda kv: kv[0] != str(pick))
    conf = answer.get("confidence")
    return ranked, float(conf if conf is not None else (ranked[0][1] if ranked else 0.0))


def _choice(answer) -> tuple[str, float]:
    """(picked code, probability) from one Jev answer."""
    ranked, _ = _dist(answer)
    return (ranked[0][0], ranked[0][1]) if ranked else ("", 0.0)


def picks_from_answers(talk: Path, answers: dict) -> tuple[dict[str, str], list[str]]:
    """Row number → code, after the tie-break and the deck-wide rules; notes say what changed and why."""
    text = (talk / "storyboard.md").read_text(encoding="utf-8")
    _, rows, headers = _rows(text)
    picks: dict[str, tuple[str, float]] = {}
    notes: list[str] = []
    for r in rows:
        a = answers.get(f"s{r[0]}")
        if a is None:
            continue
        ranked, conf = _dist(a)
        ranked = [(c, p) for c, p in ranked if c in VARIATIONS]
        if not ranked:
            continue
        code, p = ranked[0]
        if len(ranked) > 1:   # a close race between the top two: the more restrained wins, and the author hears about it
            second, p2 = ranked[1]
            margin = p - p2
            why = f"{code} {p:.2f} 對 {second} {p2:.2f}，差距 {margin:.2f}、信心 {conf:.2f}"
            if margin < MIN_MARGIN:
                chosen = more_restrained(code, second)
                notes.append(f"第 {r[0]} 頁：{why}，拉鋸，取較克制的 {chosen}" if chosen != code else f"第 {r[0]} 頁：{why}，拉鋸，第一名已是較克制的")
                code = chosen
            elif conf < MIN_CONFIDENCE:
                notes.append(f"第 {r[0]} 頁：{why}，信心偏低但差距夠，照選；要改就自己填")
        picks[r[0]] = (code, p)
    ordered = [r[0] for r in rows if r[0] in picks]
    # one scramble per deck: keep the most probable
    scr = [n for n in ordered if picks[n][0] == "M-SCRAMBLE"]
    if len(scr) > 1:
        keep = max(scr, key=lambda n: picks[n][1])
        for n in scr:
            if n != keep:
                picks[n] = ("M-COUNT", picks[n][1]); notes.append(f"第 {n} 頁：M-SCRAMBLE 全場只留一次（第 {keep} 頁），改成 M-COUNT")
    # at most two zooms
    zooms = [n for n in ordered if picks[n][0] == "M-ZOOM"]
    if len(zooms) > 2:
        keep = set(sorted(zooms, key=lambda n: -picks[n][1])[:2])
        for n in zooms:
            if n not in keep:
                picks[n] = ("M-STEP", picks[n][1]); notes.append(f"第 {n} 頁：M-ZOOM 全場最多兩次，改成 M-STEP")
    # no push right after a push (or a zoom)
    prev = None
    for n in ordered:
        if picks[n][0] == "M-PUSH" and prev in ("M-PUSH", "M-ZOOM"):
            picks[n] = ("M-STEP", picks[n][1]); notes.append(f"第 {n} 頁：前一頁已經是轉場，改成 M-STEP")
        prev = picks[n][0]
    return {n: c for n, (c, _) in picks.items()}, notes


def write_column(talk: Path, picks: dict[str, str]) -> None:
    """Insert or update the 動態 column (after 版型) in storyboard.md; other cells untouched."""
    path = talk / "storyboard.md"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    out, headers, col = [], None, None
    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            out.append(line); continue
        nl = line[len(line.rstrip("\r\n")):]
        cols = [c.strip() for c in s.strip("|").split("|")]
        if cols and cols[0] == "#":
            headers = cols
            if "動態" in cols:
                col = cols.index("動態")
            else:
                col = cols.index("版型") + 1 if "版型" in cols else len(cols)
                cols.insert(col, "動態")
                headers = cols
        elif headers is not None and cols and cols[0].startswith(":--"):
            if len(cols) < len(headers):
                cols.insert(col, ":---")
        elif headers is not None and cols and cols[0].isdigit():
            while len(cols) < len(headers) - (0 if len(cols) >= len(headers) else 1):
                cols.append("")
            if len(cols) < len(headers):
                cols.insert(col, picks.get(cols[0], "—"))
            elif cols[0] in picks:
                cols[col] = picks[cols[0]]
        else:
            out.append(line); continue
        out.append("| " + " | ".join(cols) + " |" + nl)
    path.write_text("".join(out), encoding="utf-8")


def find_runner() -> Path | None:
    env = os.environ.get("JEV_DECIDE")
    if env and Path(env).is_file():
        return Path(env)
    home = Path.home()
    for cand in (home / ".claude/skills/jev-decide/scripts/jev_decide.mts", home / ".agents/skills/jev-decide/scripts/jev_decide.mts",
                 Path.cwd() / ".agents/skills/jev-decide/scripts/jev_decide.mts"):
        if cand.is_file():
            return cand
    return None


def _parse_json_output(stdout: str):
    for start in (stdout.find("{"), stdout.find("[")):
        if start < 0:
            continue
        try:
            return json.loads(stdout[start:])
        except json.JSONDecodeError:
            continue
    raise SystemExit("runner printed no JSON answers:\n" + stdout[-800:])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("talk", nargs="?", help="the talk (defaults to the current one)")
    ap.add_argument("--ack", action="store_true", help="the user acknowledged this paid Jev call; send it")
    ap.add_argument("--answers", help="apply answers from this JSON file ({\"s<row>\": {choice, probabilities, confidence}}) instead of calling")
    ap.add_argument("--dry-run", action="store_true", help="print the picks, do not write storyboard.md")
    ap.add_argument("--out", help="where to write the request JSON (default: a temp file)")
    ap.add_argument("--runner", help="path to jev_decide.mts (default: $JEV_DECIDE or a discovered skill copy)")
    args = ap.parse_args()

    _unit, talk = resolve_talk(args.talk)
    if not (talk / "storyboard.md").is_file():
        sys.exit(f"no storyboard.md in {talk}")
    req = build_request(talk)
    if not req["questions"]:
        sys.exit("no row uses a layout catalog code (L-…), so there is nothing to pick; the 動態 column is still yours to fill by hand")
    out = Path(args.out) if args.out else Path(tempfile.gettempdir()) / f"deck-motion-pick-{talk.name}.json"
    out.write_text(json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"request: {out}  ({len(req['questions'])} 題，每題 {min(len(q['criteria']) for q in req['questions'].values())}–{max(len(q['criteria']) for q in req['questions'].values())} 個選項)")

    answers = None
    if args.answers:
        data = json.loads(Path(args.answers).read_text(encoding="utf-8"))
        answers = data.get("answers", data) if isinstance(data, dict) else data
    else:
        runner = Path(args.runner) if args.runner else find_runner()
        node = shutil.which("node")
        if not runner or not node:
            print("jev-decide runner (or node) not found: answer the questions in the request file by hand and pass them back with --answers")
            return 0
        if not args.ack:
            est = subprocess.run([node, str(runner), "--estimate", "--raw", str(out)], capture_output=True, text=True)
            print((est.stdout or est.stderr).strip())
            print("nothing was sent. 確認要送出（付費）就加 --ack 再跑一次。")
            return 0
        res = subprocess.run([node, str(runner), "--raw", "--ack", str(out)], capture_output=True, text=True)
        if res.returncode not in (0, 10):
            sys.exit(f"runner exit {res.returncode}:\n{(res.stderr or res.stdout).strip()[-1200:]}")
        data = _parse_json_output(res.stdout)
        answers = data.get("answers", data) if isinstance(data, dict) else data

    picks, notes = picks_from_answers(talk, answers)
    for n, code in picks.items():
        p = dict(_dist(answers.get(f"s{n}"))[0]).get(code, 0.0)
        print(f"  第 {n} 頁  {code:<11} {VARIATIONS[code]['name']}" + (f"  ({p:.2f})" if p else ""))
    for note in notes:
        print("  · " + note)
    if args.dry_run:
        print("dry run: storyboard.md not written")
        return 0
    write_column(talk, picks)
    print(f"wrote the 動態 column of {talk / 'storyboard.md'}; next: ./fw deck-compile {talk}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
