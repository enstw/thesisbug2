"""Offline workflow invariants, with no real courses, accounts, or agent CLIs."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from _workflow import (DEFAULT_CONTEXT, Store, WorkflowError, atomic_write, current,
                       digest, json_text, latest, store_problems, validate_item)
from _workflow_cli import refresh_result


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="workflow-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.unit = self.root / "units/01-homework-hw"
        self.unit.mkdir(parents=True)
        (self.unit / "WORK.json").write_text('{"type":"homework"}', encoding="utf-8")
        self.env = {**os.environ, "FW_COURSE_ROOT": str(self.root)}
        self.store = Store(self.unit)
        self.store.initialize(self.store.migration(None))
        self.store.render()

    def args(self, *args):
        return [sys.executable, str(REPO / "scripts/fw"), *args]

    def cli(self, *args, ok=True):
        result = subprocess.run(self.args(*args), cwd=self.root, env=self.env,
                                text=True, capture_output=True, timeout=20)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def data(self, *args):
        return json.loads(self.cli(*args, "--json").stdout)

    def add(self, title="查核來源"):
        return self.data("todo", "hw", "add", title)

    def test_task_lifecycle_stale_write_and_noop(self):
        added = self.add()
        ident, rev = added["id"], added["revision"]
        started = self.data("todo", "hw", "start", ident[:12], "--expect", rev)
        stale = self.cli("todo", "hw", "done", ident, "--expect", rev, "--json", ok=False)
        self.assertEqual(stale.returncode, 1)
        self.assertIn("stale revision", stale.stdout)
        blocked = self.data("todo", "hw", "block", ident, "等全文", "--expect", started["revision"])
        self.assertEqual(blocked["state"]["status"], "blocked")
        completed = self.data("todo", "hw", "done", ident, "--expect", blocked["revision"], "--evidence", "已核對原文")
        self.assertEqual(self.data("todo", "hw", "list")["total"], 0)
        self.assertNotIn("查核來源", self.store.paths["progress"].read_text(encoding="utf-8"))
        before = self.store.find("task", ident)
        same = self.data("todo", "hw", "done", ident, "--expect", completed["revision"])
        self.assertFalse(same["changed"])
        self.assertEqual(before, self.store.find("task", ident))
        opened = self.data("todo", "hw", "reopen", ident, "--expect", completed["revision"])
        self.assertEqual(opened["state"]["status"], "open")
        self.assertEqual(opened["state"]["evidence"], "")
        self.cli("workflow", "hw", "handoff")

    def test_decisions_keep_uncommitted_versions_and_retire(self):
        added = self.data("decision", "hw", "add", "引用規範", "--rule", "使用 APA", "--reason", "課程要求")
        revised = self.data("decision", "hw", "revise", added["id"], "--expect", added["revision"],
                            "--rule", "使用 Chicago", "--reason", "教師更新要求")
        old = self.data("decision", "hw", "show", added["id"], "--revision", added["revision"])
        self.assertEqual(old["state"]["rule"], "使用 APA")
        self.assertEqual(self.data("decision", "hw", "history", added["id"])["total"], 2)
        self.assertNotIn("使用 APA", self.store.paths["decisions"].read_text(encoding="utf-8"))
        self.data("decision", "hw", "retire", added["id"], "--expect", revised["revision"], "--reason", "課程已結束")
        self.assertEqual(self.data("decision", "hw", "list")["total"], 0)
        self.assertEqual(self.data("decision", "hw", "list", "--status", "retired")["total"], 1)
        self.assertFalse((self.root / ".git").exists())  # Revision retention does not depend on commit.

    def test_concurrent_commands_accept_only_one_revision(self):
        item = self.add()
        commands = [("todo", "hw", "update", item["id"], "--expect", item["revision"], "--title", title, "--json")
                    for title in ("版本甲", "版本乙")]
        jobs = [subprocess.Popen(self.args(*args), cwd=self.root, env=self.env,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for args in commands]
        results = [p.communicate(timeout=20) for p in jobs]
        self.assertEqual(sorted(p.returncode for p in jobs), [0, 1], results)
        self.assertEqual(len(self.store.find("task", item["id"])["revisions"]), 2)
        self.assertEqual(store_problems(self.unit), [])

    def test_atomic_failure_preserves_file_and_cleans_temp(self):
        path = self.unit / "existing.txt"
        path.write_text("keep", encoding="utf-8")
        with patch("_workflow.os.replace", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                atomic_write(path, "replace")
        self.assertEqual(path.read_text(), "keep")
        self.assertEqual(list(self.unit.glob(".workflow-tmp-*")), [])

    def test_saved_item_survives_failed_view_refresh(self):
        item = self.add()
        with self.store.locked():
            changed, _ = self.store.change("task", item["id"], item["revision"], "done", {})
            with patch.object(self.store, "render", side_effect=OSError("disk full")):
                result, code = refresh_result(self.store, changed, True)
        self.assertEqual(code, 3)
        self.assertTrue(result["saved"])
        self.assertEqual(current(self.store.find("task", item["id"]))["status"], "done")
        self.assertTrue(store_problems(self.unit))
        self.cli("workflow", "hw", "render")
        self.assertEqual(store_problems(self.unit), [])

    def test_repeated_handoff_and_render_do_not_create_history(self):
        self.add()
        before = {str(p): p.read_bytes() for p in self.store.paths["data"].rglob("*.json")}
        mtimes = {k: self.store.paths[k].stat().st_mtime_ns for k in ("progress", "decisions")}
        for _ in range(2):
            self.cli("workflow", "hw", "handoff")
            self.cli("workflow", "hw", "render")
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.store.paths["data"].rglob("*.json")})
        self.assertEqual(mtimes, {k: self.store.paths[k].stat().st_mtime_ns for k in mtimes})
        self.assertFalse((self.unit / "CHANGELOG.md").exists())

    def test_bounded_queries_and_views_with_many_long_entries(self):
        with self.store.locked():
            for n in range(35):
                self.store.add("task", {"title": f"共同關鍵詞 {n:03d} " + "標題" * 60, "details": "歷程" * 1500})
            self.store.render()
        page = self.data("todo", "hw", "list", "--find", "共同關鍵詞")
        self.assertEqual(page["total"], 35)
        self.assertEqual(len(page["items"]), 20)
        self.assertNotIn("details", json_text(page))
        self.assertLess(len(json_text(page).encode("utf-8")), 15000)
        self.assertIn("01-homework-hw", page["next_command"])
        self.assertLessEqual(self.store.paths["progress"].stat().st_size, 6000)
        self.cli("check-progress", "hw")
        for invalid in ("0", "-1", "101"):
            self.assertEqual(self.cli("todo", "hw", "list", "--limit", invalid, ok=False).returncode, 2)

    def test_generated_view_edit_is_detected_and_not_overwritten_by_add(self):
        self.store.paths["progress"].write_text("# 作者尚未保存的新狀態\n", encoding="utf-8")
        result = self.cli("todo", "hw", "add", "另一件事", "--json", ok=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.store.all("task"), [])
        self.assertIn("作者", self.store.paths["progress"].read_text(encoding="utf-8"))
        self.assertNotEqual(self.cli("check-progress", "hw", ok=False).returncode, 0)

    def test_revision_fork_and_mutated_history_are_rejected(self):
        added = self.add()
        item = self.store.find("task", added["id"])
        state = current(item).copy()
        state["title"] = "改名"
        from _workflow import revision
        fork = copy.deepcopy(item)
        fork["revisions"].append(revision(item["id"], latest(item), state, "update", ""))
        fork["revisions"].append(revision(item["id"], latest(item), state, "update", ""))
        with self.assertRaisesRegex(WorkflowError, "conflicting revision history"):
            validate_item(fork, "task")
        item["revisions"][0]["state"]["title"] = "竄改"
        with self.assertRaisesRegex(WorkflowError, "revision content changed"):
            validate_item(item, "task")

    def test_migration_preview_preserves_originals_and_rejects_stale_input(self):
        other = self.root / "units/02-paper-final"
        other.mkdir()
        (other / "WORK.json").write_text("{}", encoding="utf-8")
        original = "# 進度\n- [ ] 未完成事項\n- 2026-01-01 舊進度\n"
        (other / "PROGRESS.md").write_text(original, encoding="utf-8")
        store = Store(other)
        with self.assertRaisesRegex(WorkflowError, "--from"):
            store.migration(None)
        plan = {"context": DEFAULT_CONTEXT, "tasks": [{"title": "未完成事項"}], "decisions": []}
        preview = store.migration(plan)
        self.assertFalse(store.paths["data"].exists())
        (other / "PROGRESS.md").write_text(original + "新資訊\n", encoding="utf-8")
        with self.assertRaisesRegex(WorkflowError, "changed"):
            store.initialize(preview)
        self.assertFalse(store.paths["data"].exists())
        preview = store.migration(plan)
        store.initialize(preview)
        store.render()
        archive = json.loads(store.paths["archive"].read_text(encoding="utf-8"))
        self.assertEqual(archive["originals"]["PROGRESS.md"], original + "新資訊\n")
        self.assertEqual(len(store.all("task")), 1)

    def test_migration_cli_requires_preview_fingerprint(self):
        other = self.root / "units/02-homework-empty"
        other.mkdir()
        (other / "WORK.json").write_text("{}", encoding="utf-8")
        preview = self.data("workflow", "empty", "init")
        self.assertFalse((other / ".workflow").exists())
        self.assertEqual(self.cli("workflow", "empty", "init", "--apply", ok=False).returncode, 1)
        self.data("workflow", "empty", "init", "--apply", "--expect", preview["fingerprint"])
        self.cli("workflow", "empty", "check")

    def test_presentation_build_runs_status_gate(self):
        (self.unit / "WORK.json").write_text('{"type":"presentation"}', encoding="utf-8")
        (self.unit / "deck.html").write_text("<!doctype html><title>Fixture</title>", encoding="utf-8")
        self.cli("build", "hw")
        self.store.paths["progress"].write_text("# 進度\n- [x] 歷史\n", encoding="utf-8")
        blocked = self.cli("build", "hw", ok=False)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("Build blocked", blocked.stderr)

    def test_add_retry_with_same_id_is_idempotent(self):
        added = self.add()
        again = self.data("todo", "hw", "add", "查核來源", "--id", added["id"])
        self.assertFalse(again["changed"])
        self.assertEqual(again["revision"], added["revision"])
        different = self.cli("todo", "hw", "add", "不同內容", "--id", added["id"], ok=False)
        self.assertNotEqual(different.returncode, 0)

    def test_render_escapes_within_budget_and_refuses_symlink(self):
        self.add("<`&>" * 40)
        self.cli("check-progress", "hw")
        view = self.store.paths["progress"]
        other = self.root / "outside.md"
        original = view.read_bytes()
        other.write_bytes(original)
        view.unlink()
        view.symlink_to(other)
        result = self.cli("workflow", "hw", "render", ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr)
        self.assertEqual(other.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
