#!/usr/bin/env python3
"""Pick a motion variation (the 動態 column) for every storyboard row, with Jev or by hand.

    ./fw deck-motion-pick <talk>                 build the request, show what it would ask and the estimate; send nothing
    ./fw deck-motion-pick <talk> --ack           send it (the user acknowledged this paid call), write the picks into storyboard.md
    ./fw deck-motion-pick <talk> --answers a.json  apply answers from a file (a cached run, or picks written by hand) instead of calling
    ./fw deck-motion-pick <talk> ... --dry-run   print the picks, leave storyboard.md alone

Each storyboard row with a layout code becomes one Choice question over the
variations that `deck-compile` can apply to that layout (`_deck_motion.py`;
documented in deck-plan/reference/motion-catalog.md). The questions share one
state: the talk's premises, the rules of restraint and every slide in order,
so a pick can see its neighbours. Deck-wide rules Jev cannot enforce across
independent questions are applied afterwards and reported (one scramble per
deck, at most two zooms, no push after push).

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
from _deck_motion import VARIATIONS, options_for  # noqa: E402
from _paths import resolve_talk  # noqa: E402

RULES = [
    "每頁只選一個代碼。",
    "連續兩頁不要同一種轉場（M-PUSH、M-ZOOM）；主題換了就不要推。",
    "M-SCRAMBLE 全場最多一次，留給唯一的關鍵數字；其他數字頁用 M-COUNT。",
    "M-ZOOM 全場最多兩次，只在這頁真的是上一頁某處的細節時用。",
    "分節頁、引文頁、一句話的頁傾向 M-NONE 或 M-LINES；封面與結論可用 M-CHARS。",
    "卡片、流程、階層、時間軸傾向 M-POP 或 M-STEP；導語重要的頁可用 M-TYPE。",
    "台下約十秒要看懂一頁；拍越多講者按越多次，不確定就選較克制的。",
]


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


def _cell(row: list[str], headers: list[str], name: str) -> str:
    try:
        i = headers.index(name)
    except ValueError:
        return ""
    return row[i] if i < len(row) else ""


def _trim(s: str, n: int) -> str:
    s = re.sub(r"<br\s*/?>", "；", s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def build_request(talk: Path) -> dict:
    """One Jev raw request: shared state + one Choice per layout row (ids s<row#>)."""
    text = (talk / "storyboard.md").read_text(encoding="utf-8")
    premises, rows, headers = _rows(text)
    slides = []
    for r in rows:
        slides.append({
            "n": r[0], "layout": _cell(r, headers, "版型"), "shape": _cell(r, headers, "內容形狀"),
            "content": _trim(_cell(r, headers, "畫面內容"), 220), "spoken": _trim(_cell(r, headers, "口說重點"), 120),
        })
    state = {
        "goal": "為這場簡報的每一頁選一個動態變化（活潑模式：講者每按一次 → 出現一拍），讓台下跟著講到的地方看，又不花俏。",
        "premises": premises,
        "rules": RULES,
        "slides": slides,
    }
    questions = {}
    for i, s in enumerate(slides):
        opts = options_for(s["layout"]) if re.match(r"L-[A-Z0-9-]+$", s["layout"]) else {}
        if not opts:
            continue
        prev_ = slides[i - 1]["layout"] if i > 0 else "（無，這是第一頁）"
        next_ = slides[i + 1]["layout"] if i + 1 < len(slides) else "（無，這是最後一頁）"
        questions[f"s{s['n']}"] = {
            "type": "choice",
            "instructions": (f"第 {s['n']} 頁，版型 {s['layout']}，內容形狀「{s['shape']}」。畫面內容：{s['content']}。口說重點：{s['spoken']}。"
                             f"前一頁的版型是 {prev_}，後一頁是 {next_}。依 state.rules，為這一頁選一個最合適的動態代碼；每個選項都列了做法、好處與代價，要權衡。"),
            "criteria": {code: {"what": v["what"], "pros": v["pros"], "cons": v["cons"]} for code, v in opts.items()},
        }
    return {"state": state, "questions": questions, "meta": {"talk": str(talk), "tool": "deck-motion-pick"}}


def _choice(answer) -> tuple[str, float]:
    """(picked code, probability) from one Jev answer, whatever its exact shape."""
    if isinstance(answer, str):
        return answer, 0.0
    if not isinstance(answer, dict):
        return "", 0.0
    probs = answer.get("probabilities") or {}
    pick = answer.get("choice") or answer.get("answer") or answer.get("value") or (max(probs, key=probs.get) if probs else "")
    return str(pick), float(probs.get(pick, answer.get("confidence", 0.0)) or 0.0)


def picks_from_answers(talk: Path, answers: dict) -> tuple[dict[str, str], list[str]]:
    """Row number → code, after the deck-wide rules; notes say what was downgraded and why."""
    text = (talk / "storyboard.md").read_text(encoding="utf-8")
    _, rows, headers = _rows(text)
    picks: dict[str, tuple[str, float]] = {}
    for r in rows:
        a = answers.get(f"s{r[0]}")
        if a is None:
            continue
        code, p = _choice(a)
        if code in VARIATIONS:
            picks[r[0]] = (code, p)
    notes: list[str] = []
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
        a = answers.get(f"s{n}")
        _, p = _choice(a)
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
