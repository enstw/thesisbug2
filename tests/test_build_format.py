"""A unit builds to HTML only when it asks to, and the PDF build stays as it was."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build", REPO / "scripts/build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class BuildFormatTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.unit = self.root / "units" / "01-homework-x"
        self.unit.mkdir(parents=True)

    def generated(self, work, fmt="pdf"):
        build.generate(self.unit, self.root, work, fmt)
        return (self.unit / build.GEN_YML).read_text(encoding="utf-8")

    def test_pdf_build_has_no_html_block(self):
        yml = self.generated({"type": "homework", "title": "T"})
        self.assertIn("\n  pdf:\n", yml)
        self.assertNotIn("\n  html:\n", yml)

    def test_html_block_comes_first_and_keeps_the_pdf_block(self):
        yml = self.generated({"type": "homework", "title": "T"}, "html")
        self.assertRegex(yml, r"\nformat:\n  html:\n    embed-resources: true\n")
        self.assertIn("\n  pdf:\n", yml)
        self.assertNotIn("# The HTML report", yml)

    def test_target_joins_the_render_list_once(self):
        # Quarto ignores _quarto.yml for a file off the render list, so a target must be on it.
        yml = build.add_render_target("project:\n  render:\n    - paper.qmd\n\ntitle: T\n", "plan.qmd")
        self.assertIn("  render:\n    - paper.qmd\n    - plan.qmd\n", yml)
        self.assertEqual(build.add_render_target(yml, "plan.qmd"), yml)
        self.assertEqual(build.add_render_target(yml, None), yml)

    def test_template_without_html_refuses(self):
        with self.assertRaises(SystemExit) as e:
            self.generated({"type": "paper", "title": "T"}, "html")
        self.assertIn("no html format", str(e.exception))

    def test_format_comes_from_work_json_and_the_flag_overrides_it(self):
        self.assertEqual(build.output_format({}, []), "pdf")
        self.assertEqual(build.output_format({"format": "html"}, []), "html")
        self.assertEqual(build.output_format({"format": "html"}, ["--format", "pdf"]), "pdf")
        with self.assertRaises(SystemExit):
            build.output_format({"format": "docx"}, [])


if __name__ == "__main__":
    unittest.main()
