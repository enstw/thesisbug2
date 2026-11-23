"""word-freq: corpus list parsing, the author's lists, and what a scan leaves out. No segmenter needed."""

import importlib.util
from pathlib import Path
import sys
import unittest


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

_spec = importlib.util.spec_from_file_location("word_freq", REPO / "scripts" / "word-freq.py")
word_freq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(word_freq)

FREQ = """Frequency list: Word frequencies in entire "COCT"
__________________

Number\tWord\tFrequency

1\t,\t1000
2\t的\t900
39\t⾃己\t50
40\t自己\t30
41\t競逐\t5

Total:\t\t1985
"""

WORDLIST = """# 用詞

## 作者不用的詞（改稿時直接掃）

理由：省兩個字代價太大。

| 不用 | 改寫成 | 國教院筆數 |
| :--- | :--- | ---: |
| 競逐 | 競爭 | 571 |
| 複現 | 重複出現 | 26 |

## 學門用語（掃描略過）

作者認定可以照用的低頻詞。

洗錢、監理、起訴書

## 其他
不是清單
"""


class ParseFreq(unittest.TestCase):
    def test_kangxi_radicals_fold_into_the_ordinary_character(self):
        counts, _ = word_freq.parse_freq(FREQ)
        self.assertEqual(counts["自己"], 80)
        self.assertNotIn("⾃己", counts)

    def test_total_leaves_out_punctuation_and_the_total_line(self):
        counts, total = word_freq.parse_freq(FREQ)
        self.assertEqual(total, 900 + 80 + 5)
        self.assertNotIn("Total:", counts)


class CorpusCount(unittest.TestCase):
    def test_verb_with_resultative_takes_the_verbs_count(self):
        counts = {"定性": 444, "定性為": 3, "守門層": 0}
        self.assertEqual(word_freq.corpus_count("定性為", counts), 444)
        self.assertEqual(word_freq.corpus_count("守門層", counts), 0)
        self.assertEqual(word_freq.corpus_count("成為", {"成": 9, "成為": 5}), 5)


class AuthorLists(unittest.TestCase):
    def test_dropped_words_come_from_the_table_body(self):
        dropped, _ = word_freq.author_lists(WORDLIST)
        self.assertEqual(dropped, [("競逐", "競爭"), ("複現", "重複出現")])

    def test_approved_words_skip_prose_and_stop_at_the_next_heading(self):
        _, approved = word_freq.author_lists(WORDLIST)
        self.assertEqual(approved, {"洗錢", "監理", "起訴書"})

    def test_placeholder_line_approves_nothing(self):
        _, approved = word_freq.author_lists("## 學門用語\n\n（尚無）\n")
        self.assertEqual(approved, set())


class WhatIsScanned(unittest.TestCase):
    def test_quotes_titles_and_note_marks_are_blanked_in_place(self):
        para = {"text": "本文所稱「別人的競逐」見《競逐之書》[註]，此處競逐。", "quotes": [(4, 11)]}
        own = word_freq.own_text(para)
        self.assertEqual(len(own), len(para["text"]))
        self.assertEqual(own.count("競逐"), 1)
        self.assertTrue(own.endswith("此處競逐。"))

    def test_glossary_parts_cover_pieces_but_not_new_compounds(self):
        parts = word_freq.glossary_parts([{"names": ["咽喉點效應"]}])
        self.assertIn("咽喉點", parts)
        self.assertIn("效應", parts)
        self.assertNotIn("咽喉點效應論", parts)

    def test_tally_skips_short_non_cjk_and_covered_words(self):
        paras = [{"file": "u/chapters/01-intro.qmd", "line": 3}, {"file": "u/chapters/05-case.qmd", "line": 9}]
        words = [["競逐", "的", "USDT", "咽喉點"], ["競逐", "守門層"]]
        tags = [["VC", "DE", "FW", "Na"], ["VC", "Na"]]
        uses, where, _, first = word_freq.tally(paras, words, tags, {"咽喉點"})
        self.assertEqual(uses, {"競逐": 2, "守門層": 1})
        self.assertEqual(where["競逐"], {"01", "05"})
        self.assertEqual(first["守門層"], ("u/chapters/05-case.qmd", 9))


if __name__ == "__main__":
    unittest.main()
