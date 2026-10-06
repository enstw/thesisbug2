"""deck-notes: speaker notes are assembled from the View's 講法 and the
Model's glossary and Q&A, routed by the storyboard; broken routes are refused."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]


class DeckNotesTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "units").mkdir()
        self.env = dict(os.environ, FW_COURSE_ROOT=str(self.root))
        r = self.run_fw("unit-init.py", "--title", "T", "--author", "A", "--type", "presentation",
                        "--variant", "reading-guide", "--name", "talk")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.unit = next((self.root / "units").glob("*-talk"))
        html = (self.unit / "deck.html").read_text(encoding="utf-8")
        self.labels = re.findall(r'<section class="slide[^"]*"[^>]*data-label="([^"]*)"', html)
        self.write("notes/glossary.md", "# 講者備援：名詞解說\n\n## 公共財\n\n**一句話**：大家都享受得到 [@k2020, {12}]。\n\n- 完整要點留在備援檔。\n")
        self.write("notes/qa.md", "# 講者備援：預想提問\n\n## Q1 為什麼？\n\n**簡答**：因為 [@k2020, {3-4}]。\n\n完整回答。\n")
        rows = "".join(f"| {i} | — | 1 One claim | `.claim` | 1 min | x | 講第 {i} 張 | {'公共財、Q1' if i == 1 else '—'} | — |\n"
                       for i in range(len(self.labels)))
        self.write("storyboard.md", "| # | 來源論點 | 內容形狀 | 版型 | 講 | 畫面內容 | 口說重點 | 名詞與提問 | AI 協助 |\n"
                   "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n" + rows)

    def write(self, name, text):
        (self.unit / name).write_text(text, encoding="utf-8")

    def run_fw(self, script, *args):
        return subprocess.run([sys.executable, str(REPO / "scripts" / script), *args], cwd=self.root,
                              env=self.env, capture_output=True, text=True, timeout=120)

    def notes(self):
        html = (self.unit / "deck.html").read_text(encoding="utf-8")
        m = re.search(r'id="speaker-notes">(.*?)</script>', html, re.S)
        return json.loads(m.group(1))

    def test_init_then_assemble_routes_glossary_and_questions(self):
        r = self.run_fw("deck-notes.py", "talk", "--init")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        md = (self.unit / "speaker-notes.md").read_text(encoding="utf-8")
        self.assertIn(f"## 1｜{self.labels[1]}\n\n- 講第 1 張", md, "seeded from the storyboard's 口說重點")
        self.assertEqual(self.run_fw("deck-notes.py", "talk", "--check").returncode, 1, "starter notes differ")

        r = self.run_fw("deck-notes.py", "talk")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        notes = self.notes()
        self.assertEqual(len(notes), len(self.labels))
        self.assertEqual(notes[1], f"{self.labels[1]}\n【講法】\n・講第 1 張\n【名詞】\n・公共財：大家都享受得到 [@k2020, p. 12]。"
                                   "\n【提問】\n・Q1 為什麼？\n　因為 [@k2020, pp. 3-4]。")
        self.assertNotIn("完整要點留在備援檔", notes[1], "only the first paragraph goes into the note")
        self.assertEqual(self.run_fw("deck-notes.py", "talk", "--check").returncode, 0)

    def test_refuses_a_term_or_question_the_unit_backup_lacks(self):
        self.run_fw("deck-notes.py", "talk", "--init")
        sb = self.unit / "storyboard.md"
        sb.write_text(sb.read_text(encoding="utf-8").replace("公共財、Q1", "搭便車、Q9"), encoding="utf-8")
        before = (self.unit / "deck.html").read_bytes()
        r = self.run_fw("deck-notes.py", "talk")
        self.assertEqual(r.returncode, 1)
        self.assertIn("'搭便車', which notes/glossary.md does not have", r.stdout)
        self.assertIn("names Q9", r.stdout)
        self.assertEqual((self.unit / "deck.html").read_bytes(), before, "nothing written on a problem")

    def test_a_moved_slide_shows_as_a_label_mismatch(self):
        self.run_fw("deck-notes.py", "talk", "--init")
        md = self.unit / "speaker-notes.md"
        md.write_text(md.read_text(encoding="utf-8").replace(f"## 1｜{self.labels[1]}", "## 1｜別張"), encoding="utf-8")
        r = self.run_fw("deck-notes.py", "talk")
        self.assertEqual(r.returncode, 1)
        self.assertIn("§ 1 is '別張'", r.stdout)

    def test_build_checks_only_a_notes_file_written_for_deck_notes(self):
        # A unit's own notes format (from before the command) is left alone ...
        self.write("speaker-notes.md", "# 講者備註\n\n## 第 0 頁｜封面\n\n**講法**\n")
        r = self.run_fw("build.py", "talk")
        self.assertNotIn("speaker notes:", r.stdout + r.stderr)
        # ... while one created by --init is held to the deck.
        (self.unit / "speaker-notes.md").unlink()
        self.run_fw("deck-notes.py", "talk", "--init")
        r = self.run_fw("build.py", "talk")
        self.assertIn("speaker notes:", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
