"""A report assembled with Quarto includes is checked as it renders.

The facts of a talk live in the notes a report includes, so check-citations
and check-zh-variants have to read those files; check-zh-variants also reads
the unit's other Markdown, and none of them follow a path out of the unit.
"""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("_paths", REPO / "scripts/_paths.py")
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)
VARIANT = "爲"  # a variant code point: flagged without opencc, so the test needs no extra package


class ReportIncludeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.unit = self.root / "units" / "01-presentation-talk"
        (self.unit / "notes").mkdir(parents=True)
        (self.unit / "refs").mkdir()
        (self.root / "units" / "02-paper-other").mkdir()
        (self.unit / "WORK.json").write_text('{"type": "presentation"}', encoding="utf-8")
        (self.root / "units" / "02-paper-other" / "WORK.json").write_text('{"type": "paper"}', encoding="utf-8")
        self.env = dict(os.environ, FW_COURSE_ROOT=str(self.root))
        self.write("references.bib",
                   "@article{inc2020a,\n  author = {A},\n  title = {T},\n  year = {2020},\n}\n"
                   "@article{dead2020b,\n  author = {B},\n  title = {T},\n  year = {2020},\n}\n")
        self.write("draft.qmd",
                   "# 導言\n\n<!-- 停用：{{< include notes/b.md >}} -->\n\n"
                   "{{< include notes/a.md >}}\n\n{{< include ../02-paper-other/x.md >}}\n")
        self.write("notes/a.md", "# A\n\n內容 [@inc2020a, {3}]。\n\n{{< include /notes/nested.md >}}\n")
        self.write("notes/nested.md", "巢狀。\n\n{{< include a.md >}}\n")
        self.write("notes/b.md", "停用的檔案 [@dead2020b]。\n")
        (self.root / "units" / "02-paper-other" / "x.md").write_text(f"別的單元{VARIANT}。\n", encoding="utf-8")

    def write(self, name, text):
        (self.unit / name).write_text(text, encoding="utf-8")

    def run_fw(self, script, *args):
        return subprocess.run([sys.executable, str(REPO / "scripts" / script), *args], cwd=self.root,
                              env=self.env, capture_output=True, text=True, timeout=120)

    def test_included_files_follow_quarto_paths_and_stay_in_the_unit(self):
        found = paths.included_files(self.unit / "draft.qmd", self.unit)
        notes = (self.unit / "notes").resolve()
        # a.md, then nested.md through a project-relative path; the cycle back to
        # a.md, the commented include and the other unit's file are skipped
        self.assertEqual(found, [notes / "a.md", notes / "nested.md"])

    def test_check_citations_reads_included_notes(self):
        r = self.run_fw("check-citations.py", "01-presentation-talk")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("1 cited keys", r.stdout)
        self.assertIn("UNUSED ENTRIES", r.stdout)
        self.assertIn("@dead2020b", r.stdout, "a commented-out include is not part of the report")

    def test_check_zh_variants_reads_the_units_prose_but_not_sources_or_logs(self):
        self.write("notes/standalone.md", f"沒被收進報告的筆記{VARIANT}。\n")
        self.write("storyboard.md", f"| 1 | 分鏡{VARIANT} |\n")
        self.write("refs/source.md", f"轉錄保留原文{VARIANT}。\n")
        self.write("PROGRESS.md", f"紀錄引用原文{VARIANT}。\n")
        r = self.run_fw("check-zh-variants.py", "01-presentation-talk")
        self.assertEqual(r.returncode, 1)
        flagged = {Path(line.split(":")[0]).name for line in r.stdout.splitlines() if VARIANT in line}
        self.assertEqual(flagged, {"standalone.md", "storyboard.md"})


if __name__ == "__main__":
    unittest.main()
