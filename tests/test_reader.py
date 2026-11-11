"""reader: transcript → reading page. Invented transcripts only."""

import importlib.util
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
spec = importlib.util.spec_from_file_location("reader", REPO / "scripts/reader.py")
rd = importlib.util.module_from_spec(spec)
sys.modules["reader"] = rd  # dataclasses look the module up while it loads
spec.loader.exec_module(rd)
TEMPLATE = rd.TEMPLATE.read_text(encoding="utf-8")


def render(text: str) -> str:
    doc = rd.parse(text)
    r = rd.Renderer(doc)
    body, _ = r.body(skip_first_h1=True)
    return body + r.notes()


class Markers(unittest.TestCase):
    def test_marker_forms_and_offset(self):
        doc = rd.parse("---\nmarker_offset: 918\n---\n**[Page 1 start]**\n\n甲。\n\n"
                       "**[Page 1 end, Page 2 start]**\n\n乙。\n\n[Page 3 start]\n\n丙。\n\n**[Page 3 end]**\n")
        self.assertEqual([b[1] for b in doc.blocks if b[0] == "pg"], [919, 920, 921])

    def test_cjk_paragraph_cut_by_a_break_is_rejoined_with_chip(self):
        html = render("**[Page 5 start]**\n\n戰略研究的四\n\n**[Page 5 end, Page 6 start]**\n\n個境界。\n")
        self.assertIn('戰略研究的四<span class="pg" id="p6"', html)
        self.assertIn("</span>個境界。", html)
        self.assertEqual(html.count("<p>"), 1)

    def test_sentence_end_keeps_paragraphs_apart(self):
        html = render("**[Page 5 start]**\n\n完整的一句。\n\n**[Page 6 start]**\n\n新的段落。\n")
        self.assertEqual(html.count("<p>"), 2)
        self.assertIn('class="pgbreak" id="p6"', html)

    def test_footnote_ref_at_paragraph_end_does_not_hide_the_sentence_end(self):
        html = render("**[Page 5 start]**\n\n完整的一句。<sup>4</sup>\n\n**[Page 6 start]**\n\n新段。\n")
        self.assertEqual(html.count("<p>"), 2)

    def test_latin_hyphenated_word_is_rejoined(self):
        html = render("**[Page 1 start]**\n\nthe argu-\n\n**[Page 2 start]**\n\nment holds.\n")
        self.assertIn('the argu<span class="pg" id="p2"', html)
        self.assertIn("</span>ment holds.", html)


class Footnotes(unittest.TestCase):
    def test_blockquote_notes_with_continuation(self):
        doc = rd.parse("**[Page 1 start]**\n\n正文<sup>1</sup>。\n\n> <sup>1</sup> 第一條註\n>\n"
                       "> <sup>2</sup> 第二條\n\n**[Page 2 start]**\n\n> （註 1 續）接續文字\n")
        self.assertEqual([(n.label, n.page) for n in doc.notes], [("1", 1), ("2", 1)])
        self.assertEqual(doc.notes[0].text, "第一條註接續文字")

    def test_per_page_numbering_resolves_to_the_note_on_that_page(self):
        html = render("**[Page 1 start]**\n\n甲<sup>1</sup>。\n\n> <sup>1</sup> 第一頁的註\n\n"
                      "**[Page 2 start]**\n\n乙<sup>1</sup>。\n\n> <sup>1</sup> 第二頁的註\n")
        refs = re.findall(r'class="fn" href="#(n\d)"', html)
        self.assertEqual(refs, ["n1", "n2"])

    def test_markdown_footnotes(self):
        html = render("正文[^a]。\n\n[^a]: 註文\n    續行\n")
        self.assertIn('href="#n1"', html)
        self.assertIn("註文續行", html)

    def test_plain_blockquote_is_not_a_note(self):
        doc = rd.parse("> 引言一句。\n>\n> 出處\n")
        self.assertEqual(doc.notes, [])
        self.assertEqual(doc.blocks[0][0], "quote")


class Safety(unittest.TestCase):
    def test_raw_html_is_escaped(self):
        html = render('文字<script>alert(1)</script><img src=x onerror=alert(1)>\n')
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)

    def test_only_http_links(self):
        html = render("[x](javascript:alert(1)) 與 http://example.org/a 。\n")
        self.assertNotIn('href="javascript', html)
        self.assertIn('href="http://example.org/a"', html)


class Page(unittest.TestCase):
    def test_bib_fields_and_cite_line(self):
        with tempfile.TemporaryDirectory() as d:
            bib = Path(d) / "references.bib"
            bib.write_text("@incollection{wang2020x,\n  author = {王小明},\n  editor = {李大華},\n"
                           "  title = {{虛構}的篇名},\n  booktitle = {虛構論文集},\n  year = {2020},\n"
                           "  pages = {1--20},\n  langid = {chinese},\n}\n", encoding="utf-8")
            f = rd.bib_fields(bib, "wang2020x")
        self.assertEqual(f["title"], "虛構的篇名")
        self.assertEqual(rd.cite_line(f), "王小明（2020），收錄於李大華主編，《虛構論文集》，頁 1–20。")

    def test_end_to_end_in_a_scratch_course(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            unit = root / "units" / "01-paper-x"
            (unit / "refs").mkdir(parents=True)
            (unit / "WORK.json").write_text("{}", encoding="utf-8")
            (unit / "refs" / "doe2001x.md").write_text(
                "<!-- 校讀說明 -->\n**[Page 1 start]**\n\n# 虛構篇名\n\n## 一、前言\n\n正文<sup>1</sup>。\n\n"
                "> <sup>1</sup> 註一\n\n## 二、結論\n\n完。\n", encoding="utf-8")
            old = os.environ.get("FW_COURSE_ROOT")
            os.environ["FW_COURSE_ROOT"] = str(root)
            try:
                md = rd.find_transcript("doe2001x")
                out = root / "_output" / "doe2001x.html"
                stats = rd.render_page(md, out, TEMPLATE)
            finally:
                if old is None:
                    os.environ.pop("FW_COURSE_ROOT")
                else:
                    os.environ["FW_COURSE_ROOT"] = old
            page = out.read_text(encoding="utf-8")
        self.assertEqual(stats["notes"], 1)
        self.assertEqual(stats["unreferenced"], 0)
        self.assertIn("<title>虛構篇名</title>", page)
        self.assertEqual(page.count("<h1>"), 1)          # the transcript's h1 became the page title
        self.assertIn("校讀說明", page)
        self.assertNotIn("{{", page)


if __name__ == "__main__":
    unittest.main()
