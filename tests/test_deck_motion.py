"""Tests for the motion-variation catalogue, the compiler's 動態 column and the GSAP engine's packaging."""

import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), REPO / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


from scripts._deck_motion import VARIATIONS, apply_motion, options_for, split_codes  # noqa: E402

deck_compile = _load("deck-compile")
pick = _load("deck-motion-pick")

SLIDE = """  <section class="slide" style="--chapter:x" data-label="t">
      <h2 class="kicker rise">T</h2>
      <p class="lead rise">L</p>
          <div class="card card--x rise d1">a</div>
          <div class="card rise d2">b</div>
      <div class="verdict box rise d4">v</div>
  </section>"""


class CatalogueTests(unittest.TestCase):
    def test_every_code_is_documented(self):
        doc = (REPO / ".agents/skills/deck-plan/reference/motion-catalog.md").read_text(encoding="utf-8")
        for code in VARIATIONS:
            self.assertIn(f"`{code}`", doc, f"{code} missing from motion-catalog.md")

    def test_split_codes_accepts_separators(self):
        self.assertEqual(split_codes("M-POP、M-PUSH"), ["M-POP", "M-PUSH"])
        self.assertEqual(split_codes("M-STEP M-ZOOM"), ["M-STEP", "M-ZOOM"])
        self.assertEqual(split_codes("—"), [])

    def test_options_follow_the_layout(self):
        self.assertIn("M-COUNT", options_for("L-STAT-HERO"))
        self.assertNotIn("M-COUNT", options_for("L-3CARD-VERDICT"))
        self.assertNotIn("M-DRAW", options_for("L-FLOW-3STAGE"), "manual-only codes are not offered to the compiler route")


class ApplyMotionTests(unittest.TestCase):
    def test_step_reads_beats_off_the_stagger_classes_and_compacts(self):
        out, warnings = apply_motion(SLIDE, ["M-STEP"])
        self.assertEqual(warnings, [])
        self.assertIn('<h2 class="kicker rise" data-beat="0">', out)
        self.assertIn('class="card card--x rise d1" data-beat="1"', out)
        self.assertIn('class="verdict box rise d4" data-beat="3"', out, "d4 after d1,d2 becomes beat 3: no empty key press")

    def test_pop_type_push(self):
        out, _ = apply_motion(SLIDE, ["M-POP", "M-TYPE", "M-PUSH"])
        self.assertIn('data-beat="1" data-fx="pop"', out)
        self.assertIn('data-fx="type" data-dur="1.6"', out)
        self.assertIn('<section class="slide" style="--chapter:x" data-label="t" data-enter="push">', out)
        self.assertNotIn('data-fx="pop">v', out, "the verdict is a box, not a card")

    def test_chars_and_lines_target_titles_only(self):
        out, _ = apply_motion(SLIDE, ["M-CHARS"])
        self.assertIn('<h2 class="kicker rise" data-beat="0" data-fx="chars"', out)
        self.assertNotIn('data-fx="chars">L', out)

    def test_count_on_stat_hero(self):
        html = '<section class="slide"><div class="stat-hero__stat rise d1"><div class="stat-hero__num">5,380</div></div></section>'
        out, _ = apply_motion(html, ["M-COUNT"])
        self.assertIn('class="stat-hero__num" data-beat="1" data-fx="count"', out)

    def test_none_and_unknown_and_manual(self):
        out, warnings = apply_motion(SLIDE, ["M-NONE"])
        self.assertEqual((out, warnings), (SLIDE, []))
        out, warnings = apply_motion(SLIDE, ["M-DRAW", "M-XYZ"])
        self.assertEqual(out, SLIDE)
        self.assertEqual(len(warnings), 2)
        self.assertTrue(any("M-XYZ" in w for w in warnings))
        self.assertTrue(any("手寫" in w for w in warnings))

    def test_idempotent_on_existing_attributes(self):
        once, _ = apply_motion(SLIDE, ["M-POP"])
        twice, _ = apply_motion(once, ["M-POP"])
        self.assertEqual(once, twice)


STORYBOARD = """# 分鏡稿

## 前提

- 標題：半導體戰略
- 聽眾：研究生
- Seed: 1337

## 投影片

| # | 來源論點 | 內容形狀 | 版型 | 講 | 畫面內容 | 口說重點 | 名詞與提問 | AI 協助 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0 | — | 14 章節／封面 | L-HERO-TITLE | 0.5 min | title: 半導體戰略<br>sub: 大國博弈下的地緣邏輯 | 開場致詞 | — | — |
| 1 | P1 | 3 Theory primer | L-3CARD-VERDICT | 2 min | title: 核心困境<br>lead: 逆全球化浪潮<br>cards:<br>- [資本] 支出膨脹: 成本上升 40%<br>- [聚落] 支援斷鏈: 缺乏化學品配套<br>- [人才] 勞動文化: 管理磨合困難<br>verdict: 區域化代價高昂 | 口說要點 | 晶片、Q1 | — |
| 2 | P2 | 11 Numbers | L-STAT-HERO | 1 min | title: 規模<br>num: 5,380<br>label: 個帳號<br>context: 代理網路 | 數字 | — | — |
| 3 | P2 | 11 Numbers | L-STAT-HERO | 1 min | title: 規模二<br>num: 2,300 萬<br>label: 筆問答<br>context: 觀測 | 數字 | — | — |
| 4 | P3 | 14 結論 | L-FINALE-SUMMARY | 1 min | heading: 結語<br>onesentence: 戰略安全與經濟效率不可兼得 | 總結觀點 | — | — |
"""


class PickerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.talk = self.tmp / "talk"
        self.talk.mkdir()
        (self.talk / "storyboard.md").write_text(STORYBOARD, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_request_has_one_choice_per_layout_row(self):
        req = pick.build_request(self.talk)
        self.assertEqual(len(req["questions"]), 5)
        q = req["questions"]["s2"]
        self.assertEqual(q["type"], "choice")
        self.assertIn("M-COUNT", q["criteria"])
        self.assertNotIn("M-COUNT", req["questions"]["s1"]["criteria"])
        for opt in q["criteria"].values():
            self.assertEqual(set(opt), {"what", "pros", "cons"})
        self.assertIn("半導體戰略", json.dumps(req["state"], ensure_ascii=False))

    def test_answers_become_picks_with_deck_rules(self):
        answers = {"s0": {"choice": "M-CHARS", "probabilities": {"M-CHARS": .7}, "confidence": .7},
                   "s1": {"choice": "M-POP", "probabilities": {"M-POP": .6}, "confidence": .6},
                   "s2": {"choice": "M-SCRAMBLE", "probabilities": {"M-SCRAMBLE": .5}, "confidence": .5},
                   "s3": {"choice": "M-SCRAMBLE", "probabilities": {"M-SCRAMBLE": .8}, "confidence": .8},
                   "s4": {"choice": "M-ZOOM", "probabilities": {"M-ZOOM": .55}, "confidence": .55}}
        picks, notes = pick.picks_from_answers(self.talk, answers)
        self.assertEqual(picks["3"], "M-SCRAMBLE", "the more confident scramble wins")
        self.assertEqual(picks["2"], "M-COUNT", "a second scramble becomes a count-up")
        self.assertTrue(any("M-SCRAMBLE" in n for n in notes))

    def test_write_column_then_compile(self):
        pick.write_column(self.talk, {"0": "M-CHARS", "1": "M-POP", "2": "M-COUNT", "3": "M-COUNT", "4": "M-NONE"})
        text = (self.talk / "storyboard.md").read_text(encoding="utf-8")
        header = next(ln for ln in text.splitlines() if ln.startswith("| #"))
        self.assertEqual([c.strip() for c in header.strip("|").split("|")][:5], ["#", "來源論點", "內容形狀", "版型", "動態"])
        self.assertIn("| L-3CARD-VERDICT | M-POP |", text)
        self.assertIn("| L-FINALE-SUMMARY | M-NONE |", text)
        # writing again replaces, never duplicates
        pick.write_column(self.talk, {"1": "M-STEP"})
        text = (self.talk / "storyboard.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("動態"), 1)
        self.assertIn("| L-3CARD-VERDICT | M-STEP |", text)
        compiled, warnings = deck_compile.compile_storyboard(self.talk)
        self.assertEqual(warnings, [])
        self.assertIn('data-fx="chars"', compiled)
        self.assertIn('data-fx="count"', compiled)
        self.assertIn('data-beat="1"', compiled)


class EnginePackagingTests(unittest.TestCase):
    ASSET = REPO / ".agents/skills/deck-svg/template/asset"

    def test_bundle_carries_the_plugins_and_the_licence(self):
        head = (self.ASSET / "gsap.min.js").read_text(encoding="utf-8", errors="replace")
        self.assertIn("standard-license", head[:2000])
        for name in ("GSAP", "Flip", "DrawSVGPlugin", "TextPlugin", "SplitText", "MorphSVGPlugin", "MotionPathPlugin", "ScrambleTextPlugin", "GSDevTools"):
            self.assertRegex(head, rf"/\*!\s*\* {name} 3\.", f"{name} missing from the bundle")

    def test_starters_load_gsap_before_the_engine(self):
        for variant in ("thesis", "reading-guide"):
            html = (REPO / f".agents/skills/deck-svg/template/variants/{variant}/deck.html").read_text(encoding="utf-8")
            tag = lambda name: html.index(f'<script src="asset/{name}"></script>')
            self.assertLess(tag("gsap.min.js"), tag("deck-motion.js"), variant)
            self.assertLess(tag("deck-motion.js"), tag("deck-stage.js"), variant)

    def test_engine_parses(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        subprocess.run([node, "--check", str(self.ASSET / "deck-motion.js")], check=True)
        subprocess.run([node, "--check", str(self.ASSET / "gsap.min.js")], check=True)

    def test_engine_documents_every_fx(self):
        src = (self.ASSET / "deck-motion.js").read_text(encoding="utf-8")
        fxs = re.findall(r"^\s{4}(\w+): \(tl, it, at\)", src, re.M)
        head = src.split("(() => {")[0]
        for fx in fxs:
            self.assertIn(fx, head, f"data-fx {fx} is implemented but not in the header comment")


if __name__ == "__main__":
    unittest.main()
