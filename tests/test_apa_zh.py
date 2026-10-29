"""apa-zh (《遠景基金會季刊》撰稿規範): thesis units get the variant, build splits the
bib by langid, and the two-CSL + cite-lang pipeline prints each language its way."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build", REPO / "scripts/build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

ZH = textwrap.dedent("""
    @article{chen_2010,
      author = {{陳欣之}}, title = {霸權治理的省思}, journal = {問題與研究},
      volume = {49}, number = {1}, pages = {59--85}, year = {2010}, langid = {chinese},
      annote = {Chen, H. C. (2010). Reviewing the Hegemonic Governance. Issues and Studies, 49 (1), pp. 59-85.}
    }
    @misc{two_zh, author = {{蔡佳泓} and {俞振華}}, title = {兩作者}, year = {2011}, langid = {chinese}}
    @misc{three_zh, author = {{黃秀端} and {甲} and {乙}}, title = {三作者}, year = {2020}, langid = {chinese}}
    @misc{web_zh, author = {{經濟部國際貿易署}}, title = {統計總表}, howpublished = {經濟部國際貿易署},
      year = {2024}, month = {10}, day = {22}, url = {https://www.trade.gov.tw/x}, langid = {chinese}}
""")
EN = textwrap.dedent("""
    @article{jervis_1999, author = {Jervis, Robert}, title = {Realism, Neoliberalism, and Cooperation},
      journal = {International Security}, volume = {24}, number = {1}, pages = {42--63}, year = {1999}, langid = {english}}
    @misc{allen_2024, author = {Allen, Gregory C. and Goldston, Isaac}, title = {The Biden Administration's Memorandum},
      howpublished = {CSIS}, year = {2024}, month = {10}, day = {25}, url = {https://www.csis.org/x}, langid = {english}}
    @techreport{stuster_2018, author = {Stuster, Jack and Adolf, Jurine and Byrne, Vicky}, title = {Human Exploration of Mars},
      institution = {{National Aeronautics and Space Administration}}, type = {NASA Contractor Report}, number = {220043},
      year = {2018}, langid = {english}}
""")
DOC = textwrap.dedent("""
    ---
    citeproc: false
    bibliography:
      zh: zh.json
      en: en.json
    csl: {zh}
    bibliography-csl:
      zh: {zh}
      en: {en}
    bibliography-lang:
      zh: zh-TW-u-co-stroke
      en: en-US
    lang: zh-TW-u-co-stroke
    ---

    甲 [@chen_2010, 25-40]；乙 @chen_2010 [60]；丙 [@two_zh, 74]；丁 [@three_zh, 37]；戊 [@web_zh]。
    A [@jervis_1999, 94]; B [@allen_2024]; C [@stuster_2018, 417-418]; D @jervis_1999 [50].

    ## 中文文獻 {{.unnumbered}}

    ::: {{#refs-zh}}
    :::

    ## 西文文獻 {{.unnumbered}}

    ::: {{#refs-en}}
    :::
""")


def pandoc_cmd():
    # The pandoc a build renders with (build.to_csljson's order).
    if shutil.which("quarto"):
        return ["quarto", "pandoc"]
    if shutil.which("pandoc"):
        return ["pandoc"]
    return None


class ApaZhSelectionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "library").mkdir()
        self.unit = self.root / "units" / "01-thesis-x"
        (self.unit / "chapters").mkdir(parents=True)
        (self.unit / "chapters" / "01-a.qmd").write_text("# A\n", encoding="utf-8")
        (self.unit / "references.bib").write_text(ZH + EN, encoding="utf-8")

    def test_thesis_with_apa_zh_uses_variant_template_and_splits_bib(self):
        work = {"type": "thesis", "title": "T", "author": "A", "date": "2026-01-01", "citation": "apa-zh"}
        build.generate(self.unit, self.root, work)
        yml = (self.unit / "_quarto.yml").read_text(encoding="utf-8")
        self.assertIn("_quarto-apa-zh.yml", yml.splitlines()[0])
        self.assertIn("cite-lang.lua", yml)
        self.assertIn("bibliography-csl:", yml)
        self.assertIn("apa-zh/headings.tex", yml)
        self.assertIn("\\renewcommand\\thesection{第\\fw@zh", (build.FRAMEWORK / "assets/templates/thesis/apa-zh/headings.tex").read_text(encoding="utf-8"))
        zh = (self.unit / "_bib-zh.bib").read_text(encoding="utf-8")
        en = (self.unit / "_bib-en.bib").read_text(encoding="utf-8")
        self.assertIn("chen_2010", zh)
        self.assertNotIn("jervis_1999", zh)
        self.assertIn("jervis_1999", en)
        if pandoc_cmd():
            self.assertIn("_bib-en.json", yml)
            self.assertTrue((self.unit / "_bib-en.json").is_file())

    def test_thesis_without_the_option_keeps_single_list(self):
        work = {"type": "thesis", "title": "T", "author": "A", "date": "2026-01-01"}
        build.generate(self.unit, self.root, work)
        yml = (self.unit / "_quarto.yml").read_text(encoding="utf-8")
        self.assertIn("apa.csl", yml)
        self.assertIn("lang: zh-TW", yml)
        self.assertNotIn("headings.tex", yml)
        self.assertFalse((self.unit / "_bib-zh.bib").exists())


@unittest.skipIf(pandoc_cmd() is None, "pandoc (or quarto) not installed")
class ApaZhRenderTests(unittest.TestCase):
    def test_each_language_prints_its_own_punctuation(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "zh.bib").write_text(ZH, encoding="utf-8")
            (d / "en.bib").write_text(EN, encoding="utf-8")
            for name in ("zh", "en"):
                subprocess.run([*pandoc_cmd(), str(d / f"{name}.bib"), "-t", "csljson", "-o", str(d / f"{name}.json")],
                               check=True, capture_output=True, env=build.pandoc_env())
            doc = DOC.format(zh=REPO / "assets/apa-zh-TW.csl", en=REPO / "assets/apa-zh-TW-en.csl")
            (d / "t.md").write_text(doc, encoding="utf-8")
            r = subprocess.run([*pandoc_cmd(), "t.md", "--lua-filter", str(REPO / "assets/multibib.lua"),
                                "--lua-filter", str(REPO / "assets/cite-lang.lua"), "-t", "plain", "--wrap=none"],
                               cwd=d, capture_output=True, text=True, timeout=120, env=build.pandoc_env())
            self.assertEqual(r.returncode, 0, r.stderr)
            out = r.stdout
            # in-text, per language
            for s in ("（陳欣之，2010，25-40）", "陳欣之（2010，60）", "（蔡佳泓、俞振華，2011，74）", "（黃秀端等人，2020，37）",
                      "(Jervis, 1999, 94)", "(Allen & Goldston, 2024)", "(Stuster et al., 2018, 417-418)", "Jervis (1999, 50)"):
                self.assertIn(s, out)
            # 中文文獻: full-width, 筆劃序 (陳 11 < 黃 12 < 經 13 < 蔡 15), annote in brackets
            zh_list = out[out.index("中文文獻"):out.index("西文文獻")]
            self.assertIn("陳欣之（2010）。霸權治理的省思。問題與研究，49（1），頁59-85。", zh_list)
            self.assertIn("[Chen, H. C. (2010). Reviewing the Hegemonic Governance.", zh_list)
            self.assertIn("蔡佳泓、俞振華（2011）。", zh_list)
            self.assertIn("經濟部國際貿易署，10月22日。", zh_list)
            self.assertLess(zh_list.index("陳欣之（2010）"), zh_list.index("蔡佳泓、俞振華（2011）"))
            # 西文文獻: English terms, title case kept, 遠景 journal form
            en_list = out[out.index("西文文獻"):]
            self.assertIn("International Security, 24 (1), pp. 42-63.", en_list)
            self.assertIn("The Biden Administration’s Memorandum. CSIS, October 25.", en_list)
            self.assertIn("(NASA Contractor Report No. 220043)", en_list)


if __name__ == "__main__":
    unittest.main()
