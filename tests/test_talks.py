"""A non-presentation unit can own occasion-specific talks over one Model."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]


class TalkTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.unit = self.root / "units/01-paper-final"
        self.unit.mkdir(parents=True)
        (self.unit / "WORK.json").write_text(
            json.dumps({"type": "paper", "title": "Final", "author": "A", "date": "2026-01-01"}),
            encoding="utf-8")
        (self.unit / "paper.qmd").write_text("# Argument\n", encoding="utf-8")
        (self.unit / "PROGRESS.md").write_text("# 進度\n", encoding="utf-8")
        (self.unit / "DECISIONS.md").write_text("# 現行規則\n", encoding="utf-8")
        self.env = dict(os.environ, FW_COURSE_ROOT=str(self.root))

    def run_fw(self, script, *args):
        return subprocess.run([sys.executable, str(REPO / "scripts" / script), *args],
                              cwd=self.root, env=self.env, capture_output=True,
                              text=True, timeout=120)

    def test_talk_init_declares_unit_model_without_copying_it(self):
        r = self.run_fw("talk-init.py", "final", "--name", "week16-seminar",
                        "--model", "paper.qmd", "--variant", "thesis")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        talk = self.unit / "talks/week16-seminar"
        config = json.loads((talk / "talk.json").read_text(encoding="utf-8"))
        self.assertEqual(config["model"], ["paper.qmd"])
        for name in ("points.md", "storyboard.md", "deck.html", "asset/deck-stage.js"):
            self.assertTrue((talk / name).is_file(), name)
        self.assertFalse((talk / "paper.qmd").exists(), "the assignment Model is never copied into a talk")
        self.assertTrue((self.unit / "notes/glossary.md").is_file())
        self.assertTrue((self.unit / "notes/qa.md").is_file())

        built = self.run_fw("build.py", str(talk))
        self.assertNotEqual(built.returncode, 0, "a fresh storyboard must not pass the deck gate")
        self.assertIn("storyboard has", built.stdout + built.stderr)
        built = self.run_fw("build.py", str(talk), "--no-deck-gate")
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        self.assertIn("talks/week16-seminar/deck.html", built.stdout)

        refreshed = self.run_fw("deck-refresh.py", str(talk), "--dry-run")
        self.assertEqual(refreshed.returncode, 0, refreshed.stdout + refreshed.stderr)

    def test_talk_init_rejects_a_model_outside_the_unit(self):
        outside = self.root / "outside.qmd"
        outside.write_text("no\n", encoding="utf-8")
        r = self.run_fw("talk-init.py", "final", "--name", "bad",
                        "--model", "../../outside.qmd")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("leaves the unit", r.stderr)

    def test_deck_gate_rejects_a_declared_model_that_was_moved(self):
        r = self.run_fw("talk-init.py", "final", "--name", "seminar",
                        "--model", "paper.qmd")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        (self.unit / "paper.qmd").rename(self.unit / "renamed.qmd")
        built = self.run_fw("build.py", str(self.unit / "talks/seminar"))
        self.assertNotEqual(built.returncode, 0)
        self.assertIn("model file does not exist: paper.qmd", built.stdout + built.stderr)


if __name__ == "__main__":
    unittest.main()
