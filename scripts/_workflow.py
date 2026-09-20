"""Versioned JSON items and rebuildable status views; standard library only.

An accepted mutation commits one item's revision history with a single rename.
Markdown views are derived: failure to refresh them never rolls back or hides
an accepted revision, and check/render detect and repair an interrupted refresh.
"""

from __future__ import annotations

import contextlib
import copy
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid

from _paths import workflow_paths

SCHEMA = 1
KINDS = ("task", "decision", "context")
TASK_STATES = ("open", "in_progress", "blocked", "done")
LABELS = {"open": "待辦", "in_progress": "進行中", "blocked": "受阻", "done": "完成",
          "active": "有效", "retired": "已撤回"}
FIELDS = {
    "task": {"title": 160, "details": 4000, "status": 20, "blocker": 320, "evidence": 2000},
    "decision": {"title": 160, "rule": 4000, "reason": 1000, "scope": 320, "status": 20},
    "context": {"progress": 1800, "requirements": 2700},
}
DEFAULT_CONTEXT = {"progress": "- 階段：未開始", "requirements": "- 課程要求：待確認"}


class WorkflowError(ValueError):
    pass


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def read_json(path: Path) -> dict:
    if path.is_symlink():
        raise WorkflowError(f"refusing symlink: {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"{path.name}: expected a JSON object")
    return value


def atomic_write(path: Path, text: str) -> None:
    """Replace one local file; the temp file stays on the same filesystem."""
    if path.is_symlink():
        raise WorkflowError(f"refusing symlink: {path.name}")
    fd, name = tempfile.mkstemp(prefix=".workflow-tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def validate_state(kind: str, state: dict) -> None:
    if not isinstance(state, dict) or set(state) != set(FIELDS[kind]):
        raise WorkflowError(f"{kind}: expected fields {', '.join(FIELDS[kind])}")
    for key, maximum in FIELDS[kind].items():
        value = state[key]
        if not isinstance(value, str) or len(value) > maximum:
            raise WorkflowError(f"{key}: expected text of at most {maximum} characters")
        if any(ord(c) < 32 and c not in "\n\t" for c in value):
            raise WorkflowError(f"{key}: control characters are not allowed")
    if kind == "context":
        # The summaries have the same budgets as their rendered status files;
        # history must not be imported into their free-text section by accident.
        for key, maximum in (("progress", 2500), ("requirements", 4000)):
            if len(state[key].encode("utf-8")) > maximum:
                raise WorkflowError(f"{key}: exceeds {maximum} bytes; keep current facts only")
            for line in state[key].splitlines():
                if len(line) > 320 or re.match(r"^\s*[-*]\s*(?:\[[xX]\]|\[?(?:19|20)\d\d-\d\d-\d\d)", line):
                    raise WorkflowError(f"{key}: completed/dated entries and narrative lines belong in history")
        return
    if not state["title"].strip() or "\n" in state["title"] or "\t" in state["title"]:
        raise WorkflowError("title must be a nonempty single line")
    if kind == "task":
        if state["status"] not in TASK_STATES:
            raise WorkflowError("unknown task status")
        if (state["status"] == "blocked") != bool(state["blocker"].strip()):
            raise WorkflowError("only blocked tasks must carry a blocker")
    else:
        if state["status"] not in ("active", "retired") or not state["rule"].strip() or not state["reason"].strip():
            raise WorkflowError("decisions need a rule, a reason, and active/retired status")


def initial_state(kind: str, values: dict) -> dict:
    if not isinstance(values, dict) or set(values) - set(FIELDS[kind]):
        raise WorkflowError(f"unknown {kind} fields")
    state = {k: "" for k in FIELDS[kind]}
    if kind != "context":
        state["status"] = "open" if kind == "task" else "active"
    state.update(values)
    validate_state(kind, state)
    return state


def revision(item_id: str, parent: str | None, state: dict, operation: str, reason: str) -> dict:
    rev = {"item_id": item_id, "parent": parent, "at": dt.datetime.now(dt.timezone.utc).isoformat(),
           "operation": operation, "reason": reason, "state": copy.deepcopy(state)}
    return {"id": digest(rev), **rev}


def new_item(kind: str, state: dict, item_id: str | None = None) -> dict:
    ident = item_id or str(uuid.uuid4())
    try:
        if str(uuid.UUID(ident)) != ident:
            raise ValueError()
    except (ValueError, AttributeError) as exc:
        raise WorkflowError("ID must be a canonical UUID") from exc
    validate_state(kind, state)
    return {"schema_version": SCHEMA, "kind": kind, "id": ident,
            "revisions": [revision(ident, None, state, "add", state.get("reason", ""))]}


def validate_item(item: dict, kind: str) -> None:
    if set(item) != {"schema_version", "kind", "id", "revisions"} or item["schema_version"] != SCHEMA or item["kind"] != kind:
        raise WorkflowError("unsupported item schema or kind")
    try:
        if str(uuid.UUID(item["id"])) != item["id"]:
            raise ValueError()
    except (ValueError, AttributeError, TypeError) as exc:
        raise WorkflowError("invalid item UUID") from exc
    if not isinstance(item["revisions"], list) or not item["revisions"]:
        raise WorkflowError("empty revision history")
    parent = None
    for rev in item["revisions"]:
        if not isinstance(rev, dict) or set(rev) != {"id", "item_id", "parent", "at", "operation", "reason", "state"}:
            raise WorkflowError("invalid revision fields")
        if rev["parent"] != parent or rev["item_id"] != item["id"]:
            raise WorkflowError("conflicting revision history; resolve the divergence before continuing")
        if rev["id"] != digest({k: v for k, v in rev.items() if k != "id"}):
            raise WorkflowError("revision content changed; recover it from Git before continuing")
        if not all(isinstance(rev[k], str) for k in ("at", "operation", "reason")):
            raise WorkflowError("invalid revision metadata")
        validate_state(kind, rev["state"])
        parent = rev["id"]


def current(item: dict) -> dict:
    return item["revisions"][-1]["state"]


def latest(item: dict) -> str:
    return item["revisions"][-1]["id"]


def compact(value: str, limit: int = 100) -> str:
    text = " ".join(value.split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def view_text(value: str, width: int) -> str:
    """Bound the escaped output too, so generated lines satisfy the status gate."""
    out = ""
    escapes = {"&": "&amp;", "<": "&lt;", ">": "&gt;", "`": "&#96;"}
    for char in " ".join(value.split()):
        part = escapes.get(char, char)
        if len(out) + len(part) > width - 1:
            return out + "…"
        out += part
    return out


class Store:
    def __init__(self, unit: Path):
        self.unit = unit
        self.paths = workflow_paths(unit)

    def require(self) -> None:
        if self.paths["data"].is_symlink():
            raise WorkflowError("workflow store must not be a symlink")
        if not self.paths["data"].exists():
            raise WorkflowError(f"workflow not initialized; preview with ./fw workflow {self.unit.name} init")
        manifest = read_json(self.paths["manifest"])
        if manifest != {"schema_version": SCHEMA}:
            raise WorkflowError("unsupported workflow store version")

    @contextlib.contextmanager
    def locked(self):
        self.require()
        fd = os.open(self.paths["lock"], os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "a") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            yield

    def all(self, kind: str) -> list[dict]:
        self.require()
        directory = self.paths[kind]
        if directory.is_symlink():
            raise WorkflowError("item directory must not be a symlink")
        paths = [directory] if kind == "context" else sorted(directory.glob("*.json"))
        if kind != "context" and not directory.is_dir():
            raise WorkflowError(f"missing {kind} directory")
        items = []
        for path in paths:
            item = read_json(path)
            validate_item(item, kind)
            if kind != "context" and path.stem != item["id"]:
                raise WorkflowError("item ID does not match its filename")
            items.append(item)
        return items

    def find(self, kind: str, ident: str) -> dict:
        if not re.fullmatch(r"[a-f0-9-]{8,36}", ident):
            raise WorkflowError("use a UUID or an unambiguous prefix of at least 8 characters")
        matches = [i for i in self.all(kind) if i["id"].startswith(ident)]
        if len(matches) != 1:
            raise WorkflowError(f"ID matches {len(matches)} items; use the full UUID")
        return matches[0]

    def save(self, item: dict) -> None:
        kind = item["kind"]
        validate_item(item, kind)
        path = self.paths[kind] if kind == "context" else self.paths[kind] / (item["id"] + ".json")
        atomic_write(path, json_text(item))

    def add(self, kind: str, values: dict, ident: str | None = None) -> tuple[dict, bool]:
        state = initial_state(kind, values)
        item = new_item(kind, state, ident)
        if ident:
            existing = [i for i in self.all(kind) if i["id"] == ident]
            if existing:
                if len(existing[0]["revisions"]) == 1 and current(existing[0]) == state:
                    return existing[0], False
                raise WorkflowError("ID already exists with different state")
        self.save(item)
        return item, True

    def change(self, kind: str, ident: str, expect: str, operation: str, values: dict, reason: str = "") -> tuple[dict, bool]:
        item = self.find(kind, ident)
        if not re.fullmatch(r"[a-f0-9]{12,64}", expect) or not latest(item).startswith(expect):
            raise WorkflowError("stale revision; show the item again before changing it")
        state = copy.deepcopy(current(item))
        if kind == "task":
            status = state["status"]
            allowed = {"start": {"open", "in_progress", "blocked"}, "block": {"open", "in_progress", "blocked"},
                       "done": set(TASK_STATES), "reopen": {"done", "open"}, "update": set(TASK_STATES)}
            if operation not in allowed or status not in allowed[operation]:
                raise WorkflowError(f"cannot {operation} a {status} task")
            if operation != "update":
                state["status"] = {"start": "in_progress", "block": "blocked", "done": "done", "reopen": "open"}[operation]
                state["blocker"] = ""
                if operation == "reopen":
                    state["evidence"] = ""
        elif kind == "decision":
            if current(item)["status"] != "active" and operation != "retire":
                raise WorkflowError("a retired decision cannot be revised; add a new decision")
            if not reason.strip():
                raise WorkflowError("decision changes require --reason")
            if operation == "retire":
                state["status"] = "retired"
            state["reason"] = reason.strip()
        state.update(values)
        validate_state(kind, state)
        if state == current(item):
            return item, False
        item["revisions"].append(revision(item["id"], latest(item), state, operation, reason))
        self.save(item)
        return item, True

    def views(self) -> dict[str, str]:
        context = current(self.all("context")[0])
        outputs = {}
        for kind, key, heading, intro, budget in (
            ("task", "progress", "進度", context["progress"], 6000),
            ("decision", "decisions", "現行決策", context["requirements"], 9000),
        ):
            active = [i for i in self.all(kind) if current(i)["status"] not in ("done", "retired")]
            active.sort(key=lambda i: (0 if current(i)["status"] == "blocked" else 1, i["id"]))
            cli = "todo" if kind == "task" else "decision"
            text = f"# {heading}\n\n<!-- Generated by fw workflow; edit through its commands. -->\n\n{intro.strip()}\n\n## {'待辦' if kind == 'task' else '有效決策'}\n\n"
            footer = f"\n共 {len(active)} 項；查詢：`./fw {cli} {self.unit.name} list`。\n"
            shown = 0
            for item in active:
                s = current(item)
                # Escape markup so task text cannot add sections or HTML to a view.
                title = view_text(s["title"], 90)
                extra = s["blocker"] if kind == "task" else s["rule"]
                extra = view_text(extra, 100)
                line = f"- `{item['id'][:12]}` [{LABELS[s['status']]}] {title}" + (f" — {extra}" if extra else "") + "\n"
                if shown == 12 or len((text + line + footer).encode("utf-8")) > budget:
                    break
                text += line
                shown += 1
            if not active:
                text += "- 無\n"
            outputs[key] = text + footer
        return outputs

    def drift(self) -> list[str]:
        return [self.paths[k].name for k, text in self.views().items()
                if self.paths[k].is_symlink() or not self.paths[k].is_file()
                or self.paths[k].read_text(encoding="utf-8") != text]

    def render(self) -> None:
        for key, text in self.views().items():
            path = self.paths[key]
            if path.is_symlink():
                raise WorkflowError(f"refusing symlink: {path.name}")
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                atomic_write(path, text)

    def migration(self, plan: dict | None) -> dict:
        """Preview inputs and preserve originals; never infer decisions from prose."""
        originals = {}
        shared = Path(__file__).resolve().parent.parent / "assets/scaffold"
        needs_plan = False
        for key in ("progress", "decisions"):
            path = self.paths[key]
            if path.is_symlink():
                raise WorkflowError(f"refusing symlink: {path.name}")
            text = path.read_text(encoding="utf-8") if path.exists() else None
            originals[path.name] = text
            if text and text.strip() != (shared / path.name).read_text(encoding="utf-8").strip():
                needs_plan = True
        if plan is None:
            if needs_plan:
                raise WorkflowError("existing status text requires --from PLAN.json with context, tasks, decisions; originals will be archived verbatim")
            plan = {"context": DEFAULT_CONTEXT, "tasks": [], "decisions": []}
        if set(plan) != {"context", "tasks", "decisions"} or not isinstance(plan["tasks"], list) or not isinstance(plan["decisions"], list):
            raise WorkflowError("migration plan needs context, tasks[], decisions[]")
        validate_state("context", plan["context"])
        clean = {"context": plan["context"], "tasks": [], "decisions": []}
        for plural, kind in (("tasks", "task"), ("decisions", "decision")):
            clean[plural] = [initial_state(kind, value) for value in plan[plural]]
        return {"plan": clean, "originals": originals, "fingerprint": digest({"plan": clean, "originals": originals})}

    def initialize(self, preview: dict) -> None:
        """Publish a complete store atomically; render can recover a view failure."""
        if self.paths["data"].exists() or self.paths["data"].is_symlink():
            raise WorkflowError("workflow already exists; use check/render")
        if self.migration(preview["plan"])["fingerprint"] != preview["fingerprint"]:
            raise WorkflowError("migration inputs changed; preview again")
        stage = Path(tempfile.mkdtemp(prefix=".workflow-tmp-", dir=self.unit))
        try:
            (stage / ".gitignore").write_text(".lock\n.workflow-tmp-*\n", encoding="utf-8")
            (stage / "store.json").write_text(json_text({"schema_version": SCHEMA}), encoding="utf-8")
            (stage / "migration.json").write_text(json_text(preview), encoding="utf-8")
            for kind, plural in (("task", "tasks"), ("decision", "decisions")):
                (stage / plural).mkdir()
                (stage / plural / ".gitkeep").touch()
                for state in preview["plan"][plural]:
                    item = new_item(kind, state)
                    (stage / plural / (item["id"] + ".json")).write_text(json_text(item), encoding="utf-8")
            item = new_item("context", preview["plan"]["context"])
            (stage / "context.json").write_text(json_text(item), encoding="utf-8")
            os.rename(stage, self.paths["data"])
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def store_problems(unit: Path) -> list[str]:
    """Used by the existing gate without opting legacy units into migration."""
    store = Store(unit)
    if not store.paths["data"].exists() and not store.paths["data"].is_symlink():
        return []
    try:
        with store.locked():
            return [f"{name}: generated view is stale; run ./fw workflow {unit.name} render" for name in store.drift()]
    except (WorkflowError, OSError, UnicodeError) as exc:
        return [str(exc)]
