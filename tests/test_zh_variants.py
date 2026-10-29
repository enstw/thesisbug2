"""check-zh-variants: quote spans are exempt, the rest of the line is not."""

import importlib.util
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_zh_variants", REPO / "scripts/check-zh-variants.py")
zv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zv)

OPEN, CLOSE = zv.SPAN_OPEN, zv.SPAN_CLOSE


class StripSpans(unittest.TestCase):
    def test_span_removed_and_rest_kept(self):
        rest, unclosed = zv.strip_spans(f"他說「{OPEN}坚决反对{CLOSE}」，内容如下")
        self.assertEqual(rest, "他說「」，内容如下")
        self.assertFalse(unclosed)

    def test_two_spans_on_one_line(self):
        rest, _ = zv.strip_spans(f"{OPEN}简{CLOSE}與{OPEN}体{CLOSE}")
        self.assertEqual(rest, "與")

    def test_unclosed_open_is_flagged(self):
        rest, unclosed = zv.strip_spans(f"引文{OPEN}坚决反对")
        self.assertTrue(unclosed)
        self.assertIn(OPEN, rest)


class Scan(unittest.TestCase):
    """Through scan(): the variant layer needs no opencc, so these run anywhere."""

    def scan_text(self, text):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            unit = Path(d)
            (unit / "chapters").mkdir()
            (unit / "chapters" / "01.qmd").write_text(text + "\n", encoding="utf-8")
            problems, _ = zv.scan(unit)
        return [ch for _, _, ch, _ in problems]

    def test_variant_inside_span_is_exempt(self):
        self.assertEqual(self.scan_text(f"引文「{OPEN}内{CLOSE}」"), [])

    def test_variant_outside_span_still_caught(self):
        self.assertIn("内", self.scan_text(f"引文「{OPEN}内{CLOSE}」，内容"))

    def test_unclosed_span_reported_and_does_not_swallow_line(self):
        found = self.scan_text(f"内容{OPEN}内")
        self.assertIn("<", found)
        self.assertIn("内", found)


if __name__ == "__main__":
    unittest.main()
