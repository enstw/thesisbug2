"""deck-notes: a slide names its knowledge points in data-notes, the unit's
speaker-notes.md holds them, and the presenter window shows each point's first
paragraph, traced to the Model; broken references are refused. Older per-slide 講法 files
still assemble."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]

KNOWLEDGE = """# 講者備註：知識點

## K1 公共財

**一句話**：大家都享受得到 [@k2020, {12}]。

- 完整要點留在備援檔。

## K2 外交政策分析（FPA）

**一句話**：國際關係的一個領域 [@k2020, {38}]。

## Q1 為什麼？

**簡答**：因為 [@k2020, {3-4}]。

完整回答。
"""


class NotesCase(unittest.TestCase):
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
        self.labels = re.findall(r'<section class="slide[^"]*"[^>]*data-label="([^"]*)"', self.deck())

    def write(self, name, text):
        (self.unit / name).write_text(text, encoding="utf-8")

    def deck(self):
        return (self.unit / "deck.html").read_text(encoding="utf-8")

    def run_fw(self, script, *args):
        return subprocess.run([sys.executable, str(REPO / "scripts" / script), *args], cwd=self.root,
                              env=self.env, capture_output=True, text=True, timeout=120)

    def notes(self):
        m = re.search(r'id="speaker-notes">(.*?)</script>', self.deck(), re.S)
        return json.loads(m.group(1))


class KnowledgeNotesTests(NotesCase):
    def setUp(self):
        super().setUp()
        self.write("speaker-notes.md", KNOWLEDGE)

    def bind(self, refs):
        """Put data-notes on every slide: refs maps slide number → value; others get —."""
        count = iter(range(len(self.labels)))

        def one(m):
            n = next(count)
            value = refs.get(n, "—")
            return m.group(0) if value is None else f'{m.group(0)} data-notes="{value}"'
        self.write("deck.html", re.sub(r'<section class="slide[^"]*"', one, self.deck()))

    def test_assembles_each_slide_from_its_data_notes(self):
        self.bind({1: "K1 Q1"})
        self.assertEqual(self.run_fw("deck-notes.py", "talk", "--check").returncode, 1, "starter notes differ")
        r = self.run_fw("deck-notes.py", "talk")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        notes = self.notes()
        self.assertEqual(len(notes), len(self.labels))
        self.assertEqual(notes[1], f"{self.labels[1]}\n・K1 公共財：大家都享受得到 [@k2020, p. 12]。"
                                   "\n・Q1 為什麼？\n　因為 [@k2020, pp. 3-4]。")
        self.assertEqual(notes[2], self.labels[2], "a slide with data-notes=— shows its label only")
        self.assertNotIn("完整要點留在備援檔", notes[1], "only the first paragraph goes into the note")
        self.assertEqual(self.run_fw("deck-notes.py", "talk", "--check").returncode, 0)

    def test_notes_move_with_their_slide(self):
        self.bind({1: "K1"})
        sections = re.findall(r"<section\b.*?</section>", self.deck(), re.S)
        html = (self.deck().replace(sections[1], "@@ONE@@").replace(sections[2], sections[1])
                .replace("@@ONE@@", sections[2]))
        self.write("deck.html", html)
        self.assertEqual(self.run_fw("deck-notes.py", "talk").returncode, 0)
        notes = self.notes()
        self.assertIn("K1 公共財", notes[2], "the note followed its slide")
        self.assertNotIn("K1", notes[1])

    def test_data_time_heads_the_note(self):
        self.bind({1: 'K1" data-time="1.5'})
        self.assertEqual(self.run_fw("deck-notes.py", "talk").returncode, 0)
        self.assertTrue(self.notes()[1].startswith(f"{self.labels[1]}（1.5 分）\n"))

    def test_refuses_free_text_unknown_numbers_and_uncited_points(self):
        self.write("speaker-notes.md", KNOWLEDGE + "\n## K3 沒出處\n\n**一句話**：只是一句話。\n")
        self.bind({1: "K1 K3 解釋一下 K9"})
        before = (self.unit / "deck.html").read_bytes()
        r = self.run_fw("deck-notes.py", "talk")
        self.assertEqual(r.returncode, 1)
        self.assertIn("only K/Q numbers, found '解釋一下'", r.stdout)
        self.assertIn("names K9", r.stdout)
        self.assertIn("K3 沒出處: the first paragraph names no Model section", r.stdout)
        self.assertEqual((self.unit / "deck.html").read_bytes(), before, "nothing written on a problem")

    def test_a_point_traces_to_its_model_section_instead_of_a_citation(self):
        # The note is drawn from the Model, where the facts are cited, so a locator into the
        # Model is enough; only points this deck names are checked (another talk may own the rest).
        with open(self.unit / "guide.qmd", "a", encoding="utf-8") as f:
            f.write("\n## 二、方法\n\n### 抽樣的取捨\n\n作者的判斷。\n")
        self.write("speaker-notes.md", KNOWLEDGE
                   + "\n## K3 抽樣\n\n**一句話**：作者自己的取捨（HM § 二 › 抽樣的取捨）。\n"
                   + "\n## K4 走錯\n\n**一句話**：指到不存在的節（HM § 二 › 沒有這節）。\n"
                   + "\n## K5 別場的\n\n**一句話**：這場沒用到，不檢查。\n")
        self.bind({1: "K3"})
        r = self.run_fw("deck-notes.py", "talk")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("・K3 抽樣：作者自己的取捨（HM § 二 › 抽樣的取捨）。", self.notes()[1])
        self.bind({1: "K4"})
        r = self.run_fw("deck-notes.py", "talk")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no Model heading '沒有這節'", r.stdout)
        self.assertNotIn("K5", r.stdout)

    def test_a_content_slide_without_data_notes_is_refused(self):
        self.bind({2: None})
        r = self.run_fw("deck-notes.py", "talk")
        self.assertEqual(r.returncode, 1)
        self.assertIn(f"slide 2 ({self.labels[2]}) has no data-notes", r.stdout)

    def test_an_abbreviation_on_the_slide_needs_its_point(self):
        sections = re.findall(r"  <section\b.*?</section>\n", self.deck(), re.S)
        self.write("deck.html", self.deck().replace(sections[1], sections[1].replace("</section>", "<p>FPA</p></section>")))
        self.bind({1: "K1"})
        r = self.run_fw("deck-notes.py", "talk")
        self.assertEqual(r.returncode, 1)
        self.assertIn("shows 'FPA'", r.stdout)
        self.write("deck.html", self.deck().replace('data-notes="K1"', 'data-notes="K1 K2"'))
        r = self.run_fw("deck-notes.py", "talk")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_init_creates_the_knowledge_file_once(self):
        (self.unit / "speaker-notes.md").unlink()
        r = self.run_fw("deck-notes.py", "talk", "--init")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("# 講者備註：知識點", (self.unit / "speaker-notes.md").read_text(encoding="utf-8"))
        r = self.run_fw("deck-notes.py", "talk", "--init")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("exists; edit it instead", r.stderr)

    def test_the_scaffold_starts_with_a_knowledge_file_and_build_asks_for_bindings(self):
        self.assertIn("# 講者備註：知識點", (self.unit / "speaker-notes.md").read_text(encoding="utf-8"))
        r = self.run_fw("build.py", "talk")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("has no data-notes", r.stdout + r.stderr)

    def test_build_refuses_a_talk_json_deck_whose_notes_have_no_file(self):
        # Notes typed into deck.html pass no gate; a talk.json talk was made
        # under the deck-notes contract, so the missing file blocks the build.
        (self.unit / "speaker-notes.md").unlink()
        self.assertTrue((self.unit / "talk.json").is_file())
        r = self.run_fw("build.py", "talk")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no speaker-notes.md", r.stdout + r.stderr)
        self.assertNotIn("not blocking", r.stdout + r.stderr)

    def test_build_notes_a_root_deck_from_before_talk_json_without_blocking_on_it(self):
        # An older root deck is not force-migrated, but every build says so.
        (self.unit / "speaker-notes.md").unlink()
        (self.unit / "talk.json").unlink()
        r = self.run_fw("build.py", "talk")
        self.assertIn("note: no speaker-notes.md", r.stdout + r.stderr)
        self.assertIn("not blocking", r.stdout + r.stderr)
        self.assertNotIn("            no speaker-notes.md", r.stdout + r.stderr)

    def test_starter_decks_carry_placeholders_not_sample_notes(self):
        # A realistic sample note taught agents to write notes in deck.html.
        for variant in ("reading-guide", "thesis"):
            path = REPO / ".agents/skills/deck-svg/template/variants" / variant / "deck.html"
            html = path.read_text(encoding="utf-8")
            notes = json.loads(re.search(r'id="speaker-notes">(.*?)</script>', html, re.S).group(1))
            self.assertTrue(notes and all(n.startswith("[講者備註") for n in notes), variant)
            self.assertNotIn("投影片與 speaker-notes", html, variant)


class LegacyNotesTests(NotesCase):
    """Decks on the per-slide 講法 file keep assembling without a forced migration."""

    def setUp(self):
        super().setUp()
        (self.unit / "notes").mkdir(exist_ok=True)
        self.write("notes/glossary.md", "# 講者備援：名詞解說\n\n## 公共財\n\n**一句話**：大家都享受得到 [@k2020, {12}]。\n\n- 完整要點留在備援檔。\n")
        self.write("notes/qa.md", "# 講者備援：預想提問\n\n## Q1 為什麼？\n\n**簡答**：因為 [@k2020, {3-4}]。\n\n完整回答。\n")
        rows = "".join(f"| {i} | — | 1 One claim | `.claim` | 1 min | x | 講第 {i} 張 | {'公共財、Q1' if i == 1 else '—'} | — |\n"
                       for i in range(len(self.labels)))
        self.write("storyboard.md", "| # | 來源論點 | 內容形狀 | 版型 | 講 | 畫面內容 | 口說重點 | 名詞與提問 | AI 協助 |\n"
                   "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n" + rows)
        sections = "".join(f"## {i}｜{label}\n\n- 講第 {i} 張\n\n" for i, label in enumerate(self.labels))
        self.write("speaker-notes.md", "# 講者備註\n\n<!-- 改完這份就跑 ./fw deck-notes <talk>。 -->\n\n" + sections)

    def test_assemble_routes_glossary_and_questions(self):
        r = self.run_fw("deck-notes.py", "talk")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        notes = self.notes()
        self.assertEqual(notes[1], f"{self.labels[1]}\n【講法】\n・講第 1 張\n【名詞】\n・公共財：大家都享受得到 [@k2020, p. 12]。"
                                   "\n【提問】\n・Q1 為什麼？\n　因為 [@k2020, pp. 3-4]。")
        self.assertEqual(self.run_fw("deck-notes.py", "talk", "--check").returncode, 0)

    def test_refuses_a_term_or_question_the_unit_backup_lacks(self):
        sb = self.unit / "storyboard.md"
        sb.write_text(sb.read_text(encoding="utf-8").replace("公共財、Q1", "搭便車、Q9"), encoding="utf-8")
        r = self.run_fw("deck-notes.py", "talk")
        self.assertEqual(r.returncode, 1)
        self.assertIn("'搭便車', which notes/glossary.md does not have", r.stdout)
        self.assertIn("names Q9", r.stdout)

    def test_a_moved_slide_shows_as_a_label_mismatch(self):
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
        # ... while one written for the command is held to the deck.
        sections = "".join(f"## {i}｜{label}\n\n- 講第 {i} 張\n\n" for i, label in enumerate(self.labels))
        self.write("speaker-notes.md", "# 講者備註\n\n<!-- ./fw deck-notes -->\n\n" + sections)
        r = self.run_fw("build.py", "talk")
        self.assertIn("speaker notes:", r.stdout + r.stderr)


class DeckCompileNotesTests(NotesCase):
    """deck-compile binds each slide to its 講者備註 numbers and reports what happens to the notes."""

    STORYBOARD = ("| # | 來源論點 | 內容形狀 | 版型 | 講 | 畫面內容 | 講者備註 | AI 協助 |\n"
                  "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
                  "| 0 | — | 14 封面 | L-HERO-TITLE | 0.5 min | title: 開場標題 | — | — |\n"
                  "| 1 | — | 14 結論 | L-FINALE-SUMMARY | 1 min | heading: 結語<br>onesentence: 一句話 | {refs} | — |\n")

    def setUp(self):
        super().setUp()
        self.write("speaker-notes.md", KNOWLEDGE)
        self.write("storyboard.md", self.STORYBOARD.format(refs="K1、Q1"))

    def test_compile_binds_numbers_and_assembles_the_notes(self):
        r = self.run_fw("deck-compile.py", "talk")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('data-notes="K1 Q1" data-time="1"', self.deck())
        self.assertIn("speaker notes into", r.stdout)
        self.assertEqual(self.notes()[1], "結語（1 分）\n・K1 公共財：大家都享受得到 [@k2020, p. 12]。"
                                          "\n・Q1 為什麼？\n　因為 [@k2020, pp. 3-4]。")
        self.assertEqual(self.run_fw("deck-notes.py", "talk", "--check").returncode, 0)

    def test_compile_reports_a_notes_refusal_and_exits_non_zero(self):
        self.write("storyboard.md", self.STORYBOARD.format(refs="K1、K9"))
        r = self.run_fw("deck-compile.py", "talk")
        self.assertEqual(r.returncode, 1)
        self.assertIn("names K9", r.stderr)
        self.assertIn("speaker notes not updated", r.stderr)

    def test_compile_without_a_notes_file_prints_the_migration(self):
        (self.unit / "speaker-notes.md").unlink()
        self.write("storyboard.md", self.STORYBOARD.replace("講者備註", "名詞與提問").format(refs="—"))
        r = self.run_fw("deck-compile.py", "talk")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("note: no speaker-notes.md", r.stderr)
        self.assertIn("--init", r.stderr)
        self.assertNotRegex(self.deck(), r"<section[^>]*data-notes", "an older storyboard compiles exactly as before")

class AbbreviationPatternTests(unittest.TestCase):
    def test_file_names_and_roman_numerals_are_not_abbreviations(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("deck_notes", REPO / "scripts" / "deck-notes.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        found = mod.ABBREVIATION.findall("寫成 SKILL.md 的步驟；SALT II 未生效；FPA 與 IVF；第 IV 部分；Codex CLI")
        self.assertEqual(found, ["SALT", "FPA", "IVF", "CLI"])


if __name__ == "__main__":
    unittest.main()
