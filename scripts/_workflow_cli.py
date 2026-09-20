"""Shared CLI for workflow, todo, and decision; all writes use the same store."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

from _paths import resolve_unit
from _workflow import (DEFAULT_CONTEXT, LABELS, TASK_STATES, Store, WorkflowError,
                       compact, current, json_text, latest, read_json)


def limit(value: str) -> int:
    n = int(value)
    if not 1 <= n <= 100:
        raise argparse.ArgumentTypeError("limit must be between 1 and 100")
    return n


def offset(value: str) -> int:
    n = int(value)
    if n < 0:
        raise argparse.ArgumentTypeError("offset must be nonnegative")
    return n


def page_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--limit", type=limit, default=20)
    p.add_argument("--offset", type=offset, default=0)


def edit_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("id")
    p.add_argument("--expect", required=True, help="revision from list/show (at least 12 characters)")


def parser(command: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"fw {command}", description="JSON workflow; commands run from the course root.")
    p.add_argument("unit", help="unit name, short name, or path")
    subs = p.add_subparsers(dest="action", required=True)
    if command == "workflow":
        init = subs.add_parser("init", help="preview migration; --apply writes the approved input")
        init.add_argument("--from", dest="plan", type=Path)
        init.add_argument("--apply", action="store_true")
        init.add_argument("--expect", help="fingerprint from preview; required with --apply")
        for name in ("check", "render", "handoff"):
            subs.add_parser(name)
        context = subs.add_parser("context", help="show or update the current summary and external requirements")
        context.add_argument("--progress")
        context.add_argument("--requirements")
        context.add_argument("--expect")
    else:
        listing = subs.add_parser("list")
        listing.add_argument("--status", choices=(*TASK_STATES, "all") if command == "todo" else ("active", "retired", "all"))
        listing.add_argument("--find", nargs="+", default=[])
        page_options(listing)
        show = subs.add_parser("show")
        show.add_argument("id")
        show.add_argument("--revision", help="show one historical revision by hash/prefix")
        history = subs.add_parser("history")
        history.add_argument("id")
        page_options(history)
        add = subs.add_parser("add")
        add.add_argument("title")
        add.add_argument("--id", help="caller-supplied UUID for retry-safe creation")
        if command == "todo":
            add.add_argument("--details", default="")
            update = subs.add_parser("update")
            edit_options(update)
            update.add_argument("--title")
            update.add_argument("--details")
            for action in ("start", "block", "done", "reopen"):
                sub = subs.add_parser(action)
                edit_options(sub)
                if action == "block":
                    sub.add_argument("reason")
                if action == "done":
                    sub.add_argument("--evidence")
        else:
            add.add_argument("--rule", required=True)
            add.add_argument("--reason", required=True)
            add.add_argument("--scope", default="")
            revise = subs.add_parser("revise")
            edit_options(revise)
            revise.add_argument("--title")
            revise.add_argument("--rule")
            revise.add_argument("--scope")
            revise.add_argument("--reason", required=True)
            retire = subs.add_parser("retire")
            edit_options(retire)
            retire.add_argument("--reason", required=True)
    for sub in subs.choices.values():
        sub.add_argument("--json", action="store_true", help="machine-readable, bounded output")
    return p


def emit(value: dict, as_json: bool) -> None:
    if as_json:
        print(json_text(value), end="")
        return
    if "items" in value:
        for item in value["items"]:
            s = item.get("state", item)
            print(f"{item['id']}  {LABELS.get(s.get('status'), s.get('status', ''))}  {s.get('title', '')}")
            if item.get("revision"):
                print(f"  revision: {item['revision']}")
            if item.get("summary"):
                print(f"  {item['summary']}")
            if item.get("at"):
                print(f"  {item['at']}  {item['operation']}  {item.get('reason', '')}")
        print(f"{len(value['items'])} of {value['total']}; offset {value['offset']}")
        if "counts" in value:
            print("  ".join(f"{LABELS[k]}: {v}" for k, v in value["counts"].items()))
        if value.get("next_command"):
            print(value["next_command"])
    elif "state" in value:
        print(f"{value.get('id', '')}  revision: {value['revision']}")
        for key, text in value["state"].items():
            if text:
                print(f"{key}: {text}")
        if "changed" in value:
            print("changed" if value["changed"] else "unchanged")
    else:
        print(json_text(value), end="")
    if value.get("error") and "state" in value:
        print(value["error"], file=sys.stderr)
        print(value.get("recovery", ""), file=sys.stderr)


def summary(item: dict) -> dict:
    state = current(item)
    return {"id": item["id"], "revision": latest(item), "title": compact(state["title"], 100),
            "status": state["status"], "summary": compact(state.get("blocker") or state.get("rule", ""), 120)}


def detail(item: dict, rev: dict | None = None) -> dict:
    rev = rev or item["revisions"][-1]
    return {"id": item["id"], "kind": item["kind"], "revision": rev["id"], "state": rev["state"]}


def refresh_result(store: Store, item: dict, changed: bool) -> tuple[dict, int]:
    result = {**detail(item), "changed": changed, "saved": True}
    try:
        store.render()
    except (OSError, WorkflowError) as exc:
        # The item has already been accepted. Expose its ID/revision so callers
        # repair the view instead of retrying an add and creating a duplicate.
        result.update(error=f"state saved, view refresh failed: {exc}",
                      recovery=f"./fw workflow {store.unit.name} render")
        return result, 3
    return result, 0


def run_items(store: Store, command: str, a: argparse.Namespace) -> tuple[dict, int]:
    kind = "task" if command == "todo" else "decision"
    if a.action == "list":
        items = store.all(kind)
        if a.status and a.status != "all":
            items = [i for i in items if current(i)["status"] == a.status]
        elif not a.status:
            items = [i for i in items if current(i)["status"] not in ("done", "retired")]
        items = [i for i in items if all(k.casefold() in " ".join(current(i).values()).casefold() for k in a.find)]
        items.sort(key=lambda i: i["id"])
        result = {"items": [summary(i) for i in items[a.offset:a.offset + a.limit]],
                  "total": len(items), "offset": a.offset, "limit": a.limit}
        if a.offset + a.limit < len(items):
            import shlex
            args = ["./fw", command, store.unit.name, "list", "--offset", str(a.offset + a.limit), "--limit", str(a.limit)]
            if a.status:
                args += ["--status", a.status]
            if a.find:
                args += ["--find", *a.find]
            if a.json:
                args += ["--json"]
            result["next_command"] = shlex.join(args)
        return result, 0
    if a.action in ("show", "history"):
        item = store.find(kind, a.id)
        if a.action == "show":
            if not a.revision:
                return detail(item), 0
            matches = [r for r in item["revisions"] if len(a.revision) >= 12 and r["id"].startswith(a.revision)]
            if len(matches) != 1:
                raise WorkflowError("revision not found or ambiguous")
            return detail(item, matches[0]), 0
        revs = list(reversed(item["revisions"]))
        rows = [{"id": r["id"], "at": r["at"], "operation": r["operation"],
                 "title": compact(r["state"]["title"], 80), "reason": compact(r["reason"], 120),
                 "status": r["state"]["status"]} for r in revs[a.offset:a.offset + a.limit]]
        result = {"item_id": item["id"], "items": rows, "total": len(revs), "offset": a.offset, "limit": a.limit}
        if a.offset + a.limit < len(revs):
            result["next_command"] = f"./fw {command} {store.unit.name} history {item['id']} --offset {a.offset + a.limit} --limit {a.limit}"
        return result, 0
    if store.drift():
        raise WorkflowError("generated status text differs; reconcile it with workflow context or explicitly run workflow render before changing items")
    if a.action == "add":
        values = {"title": a.title}
        values.update({"details": a.details} if kind == "task" else {"rule": a.rule, "reason": a.reason, "scope": a.scope})
        item, changed = store.add(kind, values, a.id)
    else:
        keys = ("title", "details", "evidence") if kind == "task" else ("title", "rule", "scope")
        values = {k: getattr(a, k) for k in keys if getattr(a, k, None) is not None}
        if a.action == "block":
            values["blocker"] = a.reason
        if a.action == "update" and not values:
            raise WorkflowError("update needs --title or --details")
        item, changed = store.change(kind, a.id, a.expect, a.action, values, getattr(a, "reason", ""))
    return refresh_result(store, item, changed)


def main(command: str) -> int:
    a = parser(command).parse_args()
    try:
        unit = resolve_unit(a.unit)
        store = Store(unit)
        if command == "workflow" and a.action == "init":
            if store.paths["data"].exists():
                raise WorkflowError("workflow already exists; use check/render")
            plan = read_json(a.plan) if a.plan else None
            preview = store.migration(plan)
            if not a.apply:
                emit({"fingerprint": preview["fingerprint"], "plan": preview["plan"],
                      "archive": list(preview["originals"]), "applied": False}, a.json)
                return 0
            if a.expect != preview["fingerprint"]:
                raise WorkflowError("--apply requires the matching --expect fingerprint from init preview")
            store.initialize(preview)
            with store.locked():
                item = store.all("context")[0]
                result, code = refresh_result(store, item, True)
        elif command == "workflow" and a.action == "handoff":
            # check-progress takes its own store lock; run it outside ours.
            gate = subprocess.run([sys.executable, str(Path(__file__).with_name("check-progress.py")), str(unit)],
                                  capture_output=True, text=True)
            if gate.returncode:
                emit({"ok": False, "problems": (gate.stdout + gate.stderr).splitlines()}, a.json)
                return 1
            with store.locked():
                items = [i for i in store.all("task") if current(i)["status"] != "done"]
                counts = {s: sum(current(i)["status"] == s for i in items) for s in TASK_STATES if s != "done"}
                result = {"ok": True, "counts": counts, "items": [summary(i) for i in items[:20]],
                          "total": len(items), "offset": 0, "limit": 20}
                if len(items) > 20:
                    result["next_command"] = f"./fw todo {unit.name} list --offset 20"
                code = 0
        else:
            with store.locked():
                if command != "workflow":
                    result, code = run_items(store, command, a)
                elif a.action == "check":
                    drift = store.drift()
                    result, code = {"ok": not drift, "stale_views": drift}, int(bool(drift))
                elif a.action == "render":
                    store.render()
                    result, code = {"ok": True}, 0
                else:
                    item = store.all("context")[0]
                    values = {k: getattr(a, k) for k in DEFAULT_CONTEXT if getattr(a, k) is not None}
                    if values:
                        if not a.expect:
                            raise WorkflowError("context update requires --expect from context output")
                        item, changed = store.change("context", item["id"], a.expect, "update", values)
                        result, code = refresh_result(store, item, changed)
                    else:
                        result, code = detail(item), 0
        emit(result, a.json)
        return code
    except (WorkflowError, OSError, UnicodeError) as exc:
        if a.json:
            emit({"ok": False, "error": str(exc)}, True)
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1
