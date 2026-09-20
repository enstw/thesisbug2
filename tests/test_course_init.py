"""Offline creation and entry-point checks; run with uv run -m unittest discover -s tests."""

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("course_init", REPO / "scripts/course-init.py")
course_init = importlib.util.module_from_spec(spec)
spec.loader.exec_module(course_init)


class CourseInitTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="thesisbug2-test-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        (bin_dir / "python3").symlink_to(sys.executable)
        git = shutil.which("git")
        self.assertIsNotNone(git)
        (bin_dir / "git").symlink_to(git)
        # Deliberately omit user-installed agents and gh. Git's shell helpers
        # remain available through the system paths; no personal config is read.
        self.env = {
            **os.environ,
            "PATH": str(bin_dir) + os.pathsep + os.defpath,
            "XDG_CONFIG_HOME": str(self.root / "config"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "Framework Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Framework Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }
        for name in ("claude", "codex", "agy", "gh"):
            self.assertIsNone(shutil.which(name, path=self.env["PATH"]), name)
        # Copy the real entry files, without model eval answers or large fonts.
        self.framework = self.root / "framework"
        shutil.copytree(REPO / "assets/course-skeleton", self.framework / "assets/course-skeleton")
        # unit-init needs the shared scaffold and one small type to create a unit from.
        shutil.copytree(REPO / "assets/scaffold", self.framework / "assets/scaffold")
        shutil.copytree(REPO / "assets/templates/homework", self.framework / "assets/templates/homework")
        shutil.copytree(REPO / "scripts", self.framework / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(REPO / "docs", self.framework / "docs")
        for source in (REPO / ".agents/skills").glob("*/SKILL.md"):
            target = self.framework / source.relative_to(REPO)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        self.run_cmd("git", "init", "-q", "-b", "main", cwd=self.framework)
        self.run_cmd("git", "add", ".", cwd=self.framework)
        self.run_cmd("git", "commit", "-qm", "test fixture", cwd=self.framework)
        config = self.root / "config/thesisbug2/config.ini"
        config.parent.mkdir(parents=True)
        config.write_text("[defaults]\nowner = offline-owner\n", encoding="utf-8")

    def run_cmd(self, *args, cwd=None, check=True):
        result = subprocess.run(args, cwd=cwd or self.root, env=self.env,
                                text=True, capture_output=True, timeout=30)
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def arguments(self, *extra):
        return ["--title", "研究方法", "--term", "114-2", "--author", "測試作者",
                "--institution", "測試機構", "--instructor", "測試教師",
                "--field", "研究方法", "--citation", "apa",
                "--base-path", str(self.root / "courses"), "--no-github",
                "--framework-url", str(self.framework), *extra]

    def assert_entry_points(self, course):
        for name in ("CLAUDE.md", "GEMINI.md"):
            self.assertEqual((course / name).read_text(), "See [AGENTS.md](AGENTS.md).\n")
        canonical = course / ".framework/.agents/skills"
        for name in (".agents/skills", ".claude/skills"):
            link = course / name
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), canonical.resolve())
            self.assertTrue((link / "flow-check/SKILL.md").is_file())
            self.assertFalse((link / "self-inject/SKILL.md").exists())
        self.assertTrue((course / ".framework/docs/AGENT-GUIDE.md").is_file())
        self.assertIn("count-zh", self.run_cmd("./fw", "help", cwd=course).stdout)
        unit = course / "units/01-homework-test"
        unit.mkdir(exist_ok=True)
        (unit / "WORK.json").write_text('{"type": "homework"}\n')
        (unit / "homework.qmd").write_text("研究方法\n", encoding="utf-8")
        result = self.run_cmd("./fw", "count-zh", str(unit / "homework.qmd"), cwd=course)
        self.assertIn("4", result.stdout)

    def test_offline_creation_and_recursive_clone_without_agents(self):
        self.run_cmd(sys.executable, str(REPO / "scripts/course-init.py"),
                     "1142-methods", *self.arguments("--yes"))
        course = self.root / "courses/1142-methods"
        self.assertEqual(self.run_cmd("git", "status", "--porcelain", cwd=course).stdout, "")
        self.assert_entry_points(course)
        clone = self.root / "clone"
        self.run_cmd("git", "-c", "protocol.file.allow=always", "clone",
                     "--recurse-submodules", str(course), str(clone))
        self.assert_entry_points(clone)

    def test_interactive_chinese_slug_without_agents(self):
        # Only the slug is missing. A blank first answer must reprompt locally,
        # not call an AI CLI or accept the term code as the entire slug.
        with patch.dict(os.environ, self.env, clear=True), \
             patch.object(sys, "argv", ["course-init", *self.arguments()]), \
             patch.object(sys.stdin, "isatty", return_value=True), \
             patch("builtins.input", side_effect=["", "1142-methods"]) as user_input, \
             contextlib.redirect_stdout(io.StringIO()):
            course_init.main()
        self.assertEqual(user_input.call_count, 2)
        self.assert_entry_points(self.root / "courses/1142-methods")

    def test_update_commits_only_pin_and_preserves_staged_coursework(self):
        self.run_cmd(sys.executable, str(REPO / "scripts/course-init.py"),
                     "1142-methods", *self.arguments("--yes"))
        course = self.root / "courses/1142-methods"
        self.run_cmd("git", "checkout", "--detach", cwd=course / ".framework")
        notes = course / "notes/staged.md"
        notes.write_text("staged draft\n")
        self.run_cmd("git", "add", "notes/staged.md", cwd=course)
        notes.write_text("staged draft\nunstaged revision\n")
        (self.framework / "new-version.txt").write_text("new framework revision\n")
        self.run_cmd("git", "add", "new-version.txt", cwd=self.framework)
        self.run_cmd("git", "commit", "-qm", "new framework revision", cwd=self.framework)
        expected = self.run_cmd("git", "rev-parse", "HEAD", cwd=self.framework).stdout.strip()

        self.run_cmd("./fw", "update", cwd=course)

        self.assertEqual(self.run_cmd("git", "rev-parse", "HEAD", cwd=course / ".framework").stdout.strip(), expected)
        self.assertIn(expected, self.run_cmd("git", "ls-tree", "HEAD", ".framework", cwd=course).stdout)
        self.assertEqual(self.run_cmd("git", "diff-tree", "--no-commit-id", "--name-only",
                                     "-r", "HEAD", cwd=course).stdout.strip(), ".framework")
        self.assertEqual(self.run_cmd("git", "show", ":notes/staged.md", cwd=course).stdout, "staged draft\n")
        self.assertEqual(notes.read_text(), "staged draft\nunstaged revision\n")

    def test_update_leaves_pin_alone_when_course_ignores_submodule(self):
        self.run_cmd(sys.executable, str(REPO / "scripts/course-init.py"),
                     "1142-methods", *self.arguments("--yes"))
        course = self.root / "courses/1142-methods"
        self.run_cmd("git", "checkout", "--detach", cwd=course / ".framework")
        self.run_cmd("git", "config", "-f", ".gitmodules", "submodule..framework.ignore", "all", cwd=course)
        self.run_cmd("git", "commit", "-qam", "stop tracking the framework pin", cwd=course)
        head = self.run_cmd("git", "rev-parse", "HEAD", cwd=course).stdout.strip()
        (self.framework / "new-version.txt").write_text("new framework revision\n")
        self.run_cmd("git", "add", "new-version.txt", cwd=self.framework)
        self.run_cmd("git", "commit", "-qm", "new framework revision", cwd=self.framework)
        expected = self.run_cmd("git", "rev-parse", "HEAD", cwd=self.framework).stdout.strip()

        result = self.run_cmd("./fw", "update", cwd=course)

        self.assertIn("pin not committed", result.stdout)
        self.assertEqual(self.run_cmd("git", "rev-parse", "HEAD", cwd=course / ".framework").stdout.strip(), expected)
        self.assertEqual(self.run_cmd("git", "rev-parse", "HEAD", cwd=course).stdout.strip(), head)
        self.assertEqual(self.run_cmd("git", "status", "--porcelain", cwd=course).stdout.strip(), "")

    def test_status_files_gate_blocks_a_log_and_sweep_clears_it(self):
        self.run_cmd(sys.executable, str(REPO / "scripts/course-init.py"),
                     "1142-methods", *self.arguments("--yes"))
        course = self.root / "courses/1142-methods"
        self.run_cmd("./fw", "unit-init", "--type", "homework", "--name", "hw", "--title", "測試",
                     "--no-build", cwd=course)
        unit = course / "units/01-homework-hw"
        for name in ("PROGRESS.md", "DECISIONS.md", "CHANGELOG.md"):
            self.assertTrue((unit / name).is_file(), name)
        self.run_cmd("./fw", "check-progress", "hw", cwd=course)          # a fresh scaffold passes

        progress = unit / "PROGRESS.md"
        progress.write_text(progress.read_text(encoding="utf-8")
                            + "- [x] 第一章初稿\n- 2026-01-02 - **寫了很多**：" + "敘事" * 200 + "\n",
                            encoding="utf-8")
        blocked = self.run_cmd("./fw", "check-progress", "hw", cwd=course, check=False)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("finished item", blocked.stdout)
        self.assertIn("dated entry", blocked.stdout)

        self.run_cmd("./fw", "check-progress", "hw", "--sweep", cwd=course)
        self.assertNotIn("第一章初稿", progress.read_text(encoding="utf-8"))
        self.assertIn("第一章初稿", (unit / "CHANGELOG.md").read_text(encoding="utf-8"))
        self.run_cmd("./fw", "log", "hw", "里程碑一行", cwd=course)
        self.assertIn("里程碑一行", (unit / "CHANGELOG.md").read_text(encoding="utf-8"))

    def test_unattended_missing_slug_does_not_create_course(self):
        result = self.run_cmd(sys.executable, str(REPO / "scripts/course-init.py"),
                              *self.arguments("--yes"), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "courses").exists())

    def test_existing_directory_is_preserved(self):
        course = self.root / "courses/1142-methods"
        course.mkdir(parents=True)
        marker = course / "author-notes.txt"
        marker.write_text("keep this", encoding="utf-8")
        result = self.run_cmd(sys.executable, str(REPO / "scripts/course-init.py"),
                              "1142-methods", *self.arguments("--yes"), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(), "keep this")
        self.assertEqual(list(course.iterdir()), [marker])

    def test_slug_suggestions_preserve_the_whole_title(self):
        self.assertEqual(course_init.slugify("Research Methods"), "research-methods")
        self.assertEqual(course_init.slugify("研究方法"), "")
        self.assertEqual(course_init.slugify("AI 研究方法"), "")


if __name__ == "__main__":
    unittest.main()
