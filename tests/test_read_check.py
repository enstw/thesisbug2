"""read-check: one paragraph per prompt, and only verbatim picks reach the report."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

_spec = importlib.util.spec_from_file_location("read_check", REPO / "scripts" / "read-check.py")
read_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(read_check)

CHAPTER = """---
title: 測試
---

# 第一章

<!-- 作者備註：
     這段不該出現 -->

甲機構在二〇二〇年提出**同構接合**的說法[@smith2020, p. 3]，並據此
安排後續的同構接合比較^[這是註腳]。這一段夠長，足以通過最短字數的門檻，所以會被切成一個提問。

| 表頭 | 不是段落 |
| :--- | :--- |

```python
print("程式碼不是段落")
```

> 引文是別人的原話，不交給讀者挑。

Latin words wrap
across lines 但中文接在後面，同構接合在這裡又出現一次，這一段同樣寫得夠長，可以通過最短字數的門檻，所以也會被切成一個提問。

短段落。
"""


class ParagraphTests(unittest.TestCase):
    def setUp(self):
        self.paras = read_check.paragraphs(CHAPTER)

    def test_only_prose_paragraphs_survive(self):
        joined = "\n".join(t for _line, t in self.paras)
        for hidden in ("第一章", "不該出現", "不是段落", "程式碼", "原話", "title"):
            self.assertNotIn(hidden, joined)
        self.assertEqual(len(self.paras), 3)

    def test_reader_sees_notes_not_keys_or_markup(self):
        first = self.paras[0][1]
        self.assertIn("提出同構接合的說法[註]，並據此安排", first)
        self.assertIn("比較[註]。", first)
        self.assertNotIn("smith2020", first)
        self.assertNotIn("**", first)

    def test_line_numbers_point_at_the_source(self):
        lines = CHAPTER.split("\n")
        for line, shown in self.paras:
            self.assertEqual(lines[line - 1].strip()[:3], shown[:3] if not shown.startswith("甲") else "甲機構")

    def test_latin_lines_join_with_a_space_and_cjk_without(self):
        self.assertTrue(self.paras[1][1].startswith("Latin words wrap across lines 但中文"))


class QuotationTests(unittest.TestCase):
    def quoted(self, text):
        return [text[s:e] for s, e in read_check.quote_spans(text)]

    def test_a_quotation_is_known_by_the_citation_after_it(self):
        self.assertEqual(self.quoted("作者說「貨幣是權力」[註]，本文稱之為「同構接合」。"), ["「貨幣是權力」"])
        self.assertEqual(self.quoted("他稱為「數位支柱」（a digital pillar）[註]。"), ["「數位支柱」"])

    def test_quotations_sharing_a_citation_and_elisions_count(self):
        self.assertEqual(self.quoted("法案要求「扣押」、「凍結」[註]；又稱「依面值……贖回」，另見「同構接合」。"),
                         ["「扣押」", "「凍結」", "「依面值……贖回」"])

    def test_the_manuscripts_own_term_in_quotation_marks_stays_in(self):
        self.assertEqual(self.quoted("本文所說的「同構接合」，指兩個結構以同一方式相接[註]。"), [])

    def test_the_author_marks_a_quotation_the_rule_misses(self):
        recs = read_check.paragraph_records(
            "官方稱之為<!-- quote -->「變相買賣外匯」<!-- /quote -->，逐案追訴[@x, p. 1]，本文另稱「同構接合」，"
            "這一段夠長可以通過最短字數的門檻。\n")
        text = recs[0]["text"]
        self.assertNotIn("quote", text)
        self.assertEqual([text[s:e] for s, e in recs[0]["quotes"]], ["「變相買賣外匯」"])


    def test_a_quotation_is_the_sources_wording_when_its_transcript_has_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            unit = root / "units" / "01-paper-x"
            (unit / "refs").mkdir(parents=True)
            (root / "library" / "refs").mkdir(parents=True)
            (unit / "refs" / "chen2024.md").write_text(
                "認知作戰的核心不在於說服，\n而在於使對手喪失「判斷真偽」的能力。這是第一句。\n", encoding="utf-8")
            (unit / "refs" / "wang2021.md").write_text("货币是权力的延伸。\n", encoding="utf-8")
            (root / "library" / "refs" / "wang2021.tc.md").write_text("貨幣是權力的延伸。\n", encoding="utf-8")
            os.environ["FW_COURSE_ROOT"] = str(root)
            self.addCleanup(os.environ.pop, "FW_COURSE_ROOT")
            recs = read_check.paragraph_records(
                "陳氏說「認知作戰的核心不在於說服……喪失『判斷真偽』的能力」[@chen2024, p. 12]，"
                "又說對手會「失去辨別力」[^1]；王氏稱「貨幣是權力的延伸」[@wang2021, p. 2]，"
                "史氏則說「貨幣是一種承諾」[@smith2020, p. 9]。\n\n[^1]: 見 [@chen2024, p. 13]。\n",
                read_check.Sources(unit))
            text = recs[0]["text"]
            self.assertEqual([text[s:e] for s, e in recs[0]["quotes"]],
                             ["「認知作戰的核心不在於說服……喪失『判斷真偽』的能力」", "「貨幣是權力的延伸」"])
            self.assertEqual([(text[q["s"]:q["e"]], q["cite"], q["refs"]) for q in recs[0]["translations"]],
                             [("「失去辨別力」", "[^1]", ["units/01-paper-x/refs/chen2024.md"]),
                              ("「貨幣是一種承諾」", "[@smith2020, p. 9]", [])])

class GlossaryTests(unittest.TestCase):
    def test_entries_are_bold_lead_ins_with_a_colon(self):
        terms = read_check.glossary_terms(
            "## 名詞定義\n\n<!-- x -->**甲詞（alpha）**：定義。\n\n**乙／丙**：定義。\n\n**強調** 不是條目。\n")
        self.assertEqual([(t["term"], t["names"], t["gloss"]) for t in terms],
                         [("甲詞", ["甲詞"], "alpha"), ("乙／丙", ["乙", "丙"], "")])

    def test_definition_is_the_rest_of_the_block_as_the_reader_sees_it(self):
        terms = read_check.glossary_terms(
            "**甲詞（alpha）**：甲詞指**某種**安排[@smith2020, p. 3]，\n分兩行寫。\n\n下一段不是定義。\n\n"
            "- **乙**: 第一條。\n- **丙**: 第二條。\n")
        self.assertEqual([(t["head"], t["definition"]) for t in terms],
                         [("甲詞（alpha）", "甲詞指某種安排[註]，分兩行寫。"), ("乙", "第一條。"), ("丙", "第二條。")])


class AnswerParsingTests(unittest.TestCase):
    def test_array_is_found_inside_a_runners_banner(self):
        raw = 'LOGS: /tmp/x [info]\n=== reader: ok ===\n```json\n["同構接合", "據此安排"]\n```\n'
        self.assertEqual(read_check.first_string_array(raw), ["同構接合", "據此安排"])

    def test_empty_array_means_nothing_picked_and_prose_means_unparsed(self):
        self.assertEqual(read_check.first_string_array("[]"), [])
        self.assertIsNone(read_check.first_string_array("這段沒有問題。"))


class CommandTests(unittest.TestCase):
    def run_fw(self, root, *args):
        env = dict(os.environ, FW_COURSE_ROOT=str(root))
        return subprocess.run([sys.executable, str(REPO / "scripts" / "read-check.py"), *args],
                              cwd=root, env=env, capture_output=True, text=True)

    def test_prompts_then_collect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            unit = root / "units" / "01-paper-x"
            (unit / "chapters").mkdir(parents=True)
            (unit / "WORK.json").write_text("{}", encoding="utf-8")
            (unit / "chapters" / "01.qmd").write_text(CHAPTER, encoding="utf-8")
            (unit / "chapters" / "02.qmd").write_text(
                "另一章也用了同構接合這個詞，而且一樣沒有解釋它的意思，這一段夠長可以通過最短字數的門檻，所以算一段。\n",
                encoding="utf-8")
            out = root / "rc"

            r = self.run_fw(root, "prompts", "units/01-paper-x", "--out", str(out), "--reader", "某領域的教授")
            self.assertEqual(r.returncode, 0, r.stderr)
            meta = json.loads((out / "paras.json").read_text(encoding="utf-8"))
            ids = [p["id"] for p in meta["paragraphs"]]
            self.assertEqual(ids, ["p0001", "p0002", "p0003"])  # 短段落 dropped by --min
            prompt = (out / "prompts" / "p0001.md").read_text(encoding="utf-8")
            self.assertIn("你是某領域的教授", prompt)
            self.assertIn(meta["paragraphs"][0]["text"], prompt)
            # Isolation: a prompt carries its own paragraph and no other.
            self.assertNotIn(meta["paragraphs"][1]["text"], prompt)

            (out / "picks" / "a").mkdir(parents=True)
            (out / "picks" / "b").mkdir(parents=True)
            (out / "picks" / "a" / "p0001.json").write_text('["同構接合", "原文沒有的字"]', encoding="utf-8")
            (out / "picks" / "a" / "p0002.json").write_text("我覺得都很清楚", encoding="utf-8")
            (out / "picks" / "b" / "p0001.txt").write_text('=== ok ===\n["同構接合"]', encoding="utf-8")
            (out / "picks" / "b" / "p0003.json").write_text("[]", encoding="utf-8")

            r = self.run_fw(root, "collect", str(out))
            self.assertEqual(r.returncode, 0, r.stderr)
            picks = json.loads((out / "picks.json").read_text(encoding="utf-8"))
            self.assertEqual([(x["text"], x["readers"]) for x in picks["p0001"]], [("同構接合", ["a", "b"])])
            self.assertEqual(picks["p0002"], [])
            report = (out / "report.md").read_text(encoding="utf-8")
            self.assertIn("| a | 1 | 1 | 1 | 1 |", report)   # one dropped, one unparsed
            self.assertIn("| b | 2 | 1 | 0 | 0 |", report)
            # Spread is counted over the whole manuscript: 3 in chapter 1, 1 in chapter 2.
            self.assertIn("| 同構接合 |  | a、b | 1 | 4 | 2 |", report)
            self.assertIn("units/01-paper-x/chapters/01.qmd:", report)
            self.assertNotIn("## 詞彙表條目", report)

            (unit / "glossary.md").write_text(
                "<!-- ¶ --> **同構接合（isomorphic coupling）**：兩個結構以同一方式相接。\n\n"
                "- **受許可／無許可（permissioned / permissionless）**: 是否須經核准。\n\n"
                "**不是條目的粗體** 後面沒有冒號。\n", encoding="utf-8")
            r = self.run_fw(root, "collect", str(out), "--glossary", "glossary.md")
            self.assertEqual(r.returncode, 0, r.stderr)
            report = (out / "report.md").read_text(encoding="utf-8")
            self.assertIn("| 同構接合 | 同構接合 | a、b | 1 | 4 | 2 |", report)
            self.assertIn("| 同構接合 | isomorphic coupling | 4 | a、b |", report)
            self.assertIn("| 受許可／無許可 | permissioned / permissionless | 0 |  |", report)

    QUOTING = ("作者認為美元的地位「日益鈣化」[@smith2020, p. 3]，本文則把日益鈣化的過程稱為同構接合，"
               "這一段夠長可以通過最短字數的門檻，所以算一段。\n")

    def quoting_unit(self, root, transcripts):
        unit = root / "units" / "01-paper-x"
        (unit / "chapters").mkdir(parents=True)
        (unit / "WORK.json").write_text("{}", encoding="utf-8")
        (unit / "chapters" / "01.qmd").write_text(self.QUOTING, encoding="utf-8")
        for name, text in transcripts.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text, encoding="utf-8")
        out = root / "rc"
        r = self.run_fw(root, "prompts", "units/01-paper-x", "--out", str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        (out / "picks" / "a").mkdir(parents=True)
        (out / "picks" / "a" / "p0001.json").write_text('["鈣化", "同構接合", "「日益鈣化」"]', encoding="utf-8")
        r = self.run_fw(root, "collect", str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        return (json.loads((out / "picks.json").read_text(encoding="utf-8"))["p0001"],
                (out / "report.md").read_text(encoding="utf-8"))

    def test_picks_inside_the_sources_own_wording_are_set_aside(self):
        # The cited work is in Chinese (or is a published translation): the
        # quotation is in its transcript, across a line and a page break.
        with tempfile.TemporaryDirectory() as tmp:
            picks, report = self.quoting_unit(Path(tmp).resolve(), {
                "units/01-paper-x/refs/smith2020.md":
                    "**[Page 3 start]**\n\n美元的地位日益\n\n**[Page 4 start]**\n\n鈣化，難以撼動。\n"})
            # 鈣化 also occurs in the author's own words, so that occurrence is the one kept.
            self.assertEqual([x["text"] for x in picks], ["鈣化", "同構接合"])
            self.assertGreater(picks[0]["s"], 20)
            self.assertNotIn("translation", picks[0])
            self.assertIn("來源原文內的片段 1 個不列入", report)
            self.assertIn("「日益鈣化」〔a〕", report)
            self.assertNotIn("自譯引文", report)

    def test_picks_inside_the_manuscripts_own_translation_stay_in(self):
        # The cited work is in English, so the Chinese in the quotation marks
        # is the manuscript's and a reader's pick there is a rewrite item.
        with tempfile.TemporaryDirectory() as tmp:
            picks, report = self.quoting_unit(Path(tmp).resolve(), {
                "library/refs/smith2020.md": "**[Page 3 start]**\n\nThe dollar's role is increasingly calcified.\n"})
            self.assertEqual([x["text"] for x in picks], ["「日益鈣化」", "鈣化", "同構接合"])
            self.assertEqual(picks[0]["translation"], {"quote": "「日益鈣化」", "cite": "[@smith2020, p. 3]",
                                                       "refs": ["library/refs/smith2020.md"]})
            self.assertNotIn("translation", picks[2])
            self.assertIn("自譯引文內的片段 2 處照常列入", report)
            self.assertIn("「日益鈣化」 [@smith2020, p. 3] → `library/refs/smith2020.md`：「日益鈣化」〔a〕；鈣化〔a〕", report)
            self.assertNotIn("不列入", report)

    def test_a_quotation_with_no_transcript_to_compare_stays_in(self):
        # Set aside only what is shown to be a source's wording.
        with tempfile.TemporaryDirectory() as tmp:
            picks, report = self.quoting_unit(Path(tmp).resolve(), {})
            self.assertEqual(picks[0]["translation"]["refs"], [])
            self.assertIn("「日益鈣化」 [@smith2020, p. 3] → 未比對：", report)

    def test_glossary_goes_to_every_reader_and_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            unit = root / "units" / "01-paper-x"
            (unit / "chapters").mkdir(parents=True)
            (unit / "WORK.json").write_text("{}", encoding="utf-8")
            (unit / "chapters" / "01.qmd").write_text(CHAPTER, encoding="utf-8")
            (unit / "glossary.md").write_text(
                "**同構接合（isomorphic coupling）**：兩個結構以同一方式相接[@smith2020, p. 3]。\n", encoding="utf-8")
            out = root / "rc"

            r = self.run_fw(root, "prompts", "units/01-paper-x", "--out", str(out), "--glossary", "glossary.md")
            self.assertEqual(r.returncode, 0, r.stderr)
            meta = json.loads((out / "paras.json").read_text(encoding="utf-8"))
            self.assertEqual([g["term"] for g in meta["glossary"]], ["同構接合"])
            for pid in ("p0001", "p0002"):
                prompt = (out / "prompts" / f"{pid}.md").read_text(encoding="utf-8")
                self.assertIn("- 同構接合（isomorphic coupling）：兩個結構以同一方式相接[註]。", prompt)
                self.assertIn("以及論文前面的名詞定義", prompt)
            # The glossary is background: it comes before the paragraph, which stays last.
            self.assertLess(prompt.index("isomorphic coupling"), prompt.index(meta["paragraphs"][1]["text"]))

            (out / "picks" / "a").mkdir(parents=True)
            (out / "picks" / "a" / "p0001.json").write_text('["同構接合", "同構接合比較"]', encoding="utf-8")
            # collect falls back to the glossary the readers were given.
            r = self.run_fw(root, "collect", str(out))
            self.assertEqual(r.returncode, 0, r.stderr)
            report = (out / "report.md").read_text(encoding="utf-8")
            self.assertIn("- 讀者拿到的名詞定義：1 條（同構接合）", report)
            self.assertIn("讀者讀過定義仍然挑出的條目", report)
            self.assertIn("| 同構接合 | isomorphic coupling | 3 | a |", report)

            r = self.run_fw(root, "prompts", "units/01-paper-x", "--out", str(root / "plain"))
            self.assertEqual(r.returncode, 0, r.stderr)
            prompt = (root / "plain" / "prompts" / "p0001.md").read_text(encoding="utf-8")
            self.assertIn("你手上只有這一段，沒有論文其他部分。", prompt)
            self.assertNotIn("名詞定義", prompt)
            (root / "plain" / "picks" / "a").mkdir(parents=True)
            (root / "plain" / "picks" / "a" / "p0001.json").write_text("[]", encoding="utf-8")
            r = self.run_fw(root, "collect", str(root / "plain"))
            self.assertIn("- 讀者沒有拿到名詞定義", (root / "plain" / "report.md").read_text(encoding="utf-8"))

    def test_sample_keeps_every_file_and_is_repeatable(self):
        paras = [{"file": f, "line": i, "text": f"{f}{i}"} for f in ("a", "b", "c") for i in range(10)]
        one = read_check.sample(paras, 5, seed=7)
        self.assertEqual(one, read_check.sample(paras, 5, seed=7))
        self.assertEqual({p["file"] for p in one}, {"a", "b", "c"})
        self.assertEqual(len(one), 5)


if __name__ == "__main__":
    unittest.main()
