"""Tests for the line between the storyboard stage (what a slide says) and the design stage (its form)."""

import importlib.util
import re
import shutil
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("deck_compile", REPO / "scripts/deck-compile.py")
deck_compile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deck_compile)

from scripts._deck_catalog import CATALOG, VisualRhythmResolver  # noqa: E402
from scripts._deck_content import (char_count, content_digest, density, sign_problem,  # noqa: E402
                                   signed_digest, type_floor)
from scripts._deck_explorer import catalog_examples  # noqa: E402
from scripts._deck_outline import outline_row, with_premise  # noqa: E402

SKILLS = REPO / ".agents/skills"
HEAD = ("| # | 來源論點 | 內容形狀 | 版型 | 動態 | 講 | 畫面內容 | 講者備註 | AI 協助 |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
CARDS = "title: 三個機制<br>cards:<br>- [甲] 支出: 成本上升<br>- [乙] 聚落: 供應斷層<br>- [丙] 人才: 文化磨合<br>verdict: 效率下降"


def storyboard(rows: list[tuple[str, str, str]], premises: str = "- 標題：甲\n- 聽眾：乙\n") -> str:
    body = "".join(f"| {i} | P1 | 3 理論入門 | {layout} | {motion} | 1 min | {content} | — | — |\n"
                   for i, (layout, motion, content) in enumerate(rows))
    return f"# 分鏡稿\n\n## 前提\n\n{premises}\n## 投影片\n\n{HEAD}{body}"


def compile_row(layout: str, content: str, talk: Path | None = None) -> tuple[str | None, list[str], list[str]]:
    losses: list[str] = []
    html, warnings = deck_compile.render_row({"#": "1", "版型": layout, "畫面內容": content}, 1, 3,
                                             VisualRhythmResolver(1), talk, None, losses)
    return html, warnings, losses


class ConservationTests(unittest.TestCase):
    """A compiled slide shows everything its row says, or the compiler says what it does not."""

    def test_catalog_examples_lose_nothing_in_any_variant(self):
        for layout_id, example in catalog_examples().items():
            if layout_id == "L-CUSTOM":      # its body is a file in a talk
                continue
            for variant in CATALOG[layout_id].allowed_variants:
                _, warnings, losses = compile_row(layout_id, f"{example}<br>variant: {variant}")
                self.assertEqual((warnings, losses), ([], []), f"{layout_id} {variant}")

    def test_items_past_the_layouts_room_are_reported_once(self):
        content = CARDS.replace("<br>verdict", "<br>- [丁] 法規: 審查延宕<br>- [戊] 能源: 供電不足<br>verdict")
        html, _, losses = compile_row("L-3CARD-VERDICT", content)
        self.assertNotIn("審查延宕", html)
        self.assertEqual(len(losses), 1, losses)
        self.assertIn("cards 的第 4、5 項", losses[0])
        self.assertIn("L-3CARD-VERDICT 放不下這麼多項", losses[0])

    def test_five_parallel_items_have_a_layout(self):
        content = CARDS.replace("<br>verdict", "<br>- [丁] 法規: 審查延宕<br>- [戊] 能源: 供電不足<br>verdict")
        html, warnings, losses = compile_row("L-6CARD-GRID", content)
        self.assertEqual((warnings, losses), ([], []))
        self.assertEqual(html.count('class="axis__card'), 5)
        self.assertIn("效率下降", html)

    def test_a_slot_the_layout_does_not_have_is_reported(self):
        _, _, losses = compile_row("L-3CARD-VERDICT", CARDS + "<br>cite: Smith (1987)")
        self.assertEqual(len(losses), 1, losses)
        self.assertIn("槽位 cite 不是 L-3CARD-VERDICT 的槽位", losses[0])
        self.assertIn("Smith (1987)", losses[0])

    def test_a_field_the_layout_does_not_draw_is_reported(self):
        _, _, losses = compile_row("L-FLOW-3STAGE", "title: t<br>stages:<br>- [第一步] 巡航: 壓縮預警<br>- 宣示: 挑戰現狀<br>- 演練: 局部管制")
        self.assertEqual(len(losses), 1, losses)
        self.assertIn("stages 第 1 項的「第一步」", losses[0])

    def test_a_closing_point_keeps_the_text_after_its_colon(self):
        html, _, losses = compile_row("L-FINALE-SUMMARY", "heading: 結語<br>points:<br>- 韌性：效率的代價<br>- 第二點")
        self.assertIn("<li>韌性：效率的代價</li>", html)
        self.assertEqual(losses, [])

    def test_design_slots_and_labels_are_not_content_to_find(self):
        _, warnings, losses = compile_row("L-3CARD-VERDICT", CARDS + "<br>variant: bubble<br>verdict_label: none<br>eyebrow: 第二章")
        self.assertEqual((warnings, losses), ([], []))

    def test_missing_required_slots_warn(self):
        _, warnings, _ = compile_row("L-3CARD-VERDICT", "title: 只有標題")
        self.assertTrue(any("少了必填槽位 cards" in w for w in warnings), warnings)
        self.assertTrue(any("少了必填槽位 verdict" in w for w in warnings), warnings)
        # a name the layout reads in the same place counts
        _, warnings, _ = compile_row("L-FINALE-SUMMARY", "title: 結語<br>onesentence: 一句話")
        self.assertEqual(warnings, [])

    def test_a_row_without_a_layout_is_not_designed_yet(self):
        html, warnings, losses = compile_row("—", CARDS)
        self.assertIsNone(html)
        self.assertEqual(losses, [])
        self.assertTrue(any("還沒選版型" in w for w in warnings), warnings)


class CustomLayoutTests(unittest.TestCase):
    """L-CUSTOM gives a row a hand-written form that survives compiles and still shows every word."""

    ROW = ("title: 三種制度的比較<br>html: slides/compare.html<br>rows:<br>"
           "- [regime: 總統制, executive: 民選總統]<br>- [regime: 內閣制, executive: 國會多數黨]<br>verdict: 問責跟著行政權的來源走")

    def setUp(self):
        self.talk = Path(tempfile.mkdtemp(prefix="thesisbug2-test-custom-"))
        (self.talk / "slides").mkdir()

    def tearDown(self):
        shutil.rmtree(self.talk, ignore_errors=True)

    def write(self, body: str) -> None:
        (self.talk / "slides" / "compare.html").write_text(body, encoding="utf-8")

    def test_body_sits_in_the_standard_frame(self):
        self.write('<style>.cmp3 td { padding: 8px }</style>\n<table class="cmp3 rise d1"><tr><td>總統制</td><td>民選總統</td></tr>'
                   "<tr><td>內閣制</td><td>國會多數黨</td></tr></table>")
        html, warnings, losses = compile_row("L-CUSTOM", self.ROW, self.talk)
        self.assertEqual((warnings, losses), ([], []))
        self.assertIn('<h2 class="kicker rise">三種制度的比較</h2>', html)
        self.assertIn('<table class="cmp3 rise d1">', html)
        self.assertIn("問責跟著行政權的來源走", html)
        self.assertIn('class="topbar"', html)

    def test_text_the_body_leaves_out_is_reported(self):
        self.write("<table><tr><td>總統制</td><td>民選總統</td></tr><tr><td>內閣制</td></tr></table>")
        _, _, losses = compile_row("L-CUSTOM", self.ROW, self.talk)
        self.assertEqual(len(losses), 1, losses)
        self.assertIn("國會多數黨", losses[0])

    def test_a_whole_slide_or_a_file_outside_the_talk_is_refused(self):
        self.write('<section class="slide">總統制</section>')
        html, warnings, _ = compile_row("L-CUSTOM", self.ROW, self.talk)
        self.assertIn("手寫版面待放", html)
        self.assertTrue(any("只寫投影片內文" in w for w in warnings), warnings)
        html, warnings, _ = compile_row("L-CUSTOM", self.ROW.replace("slides/compare.html", "../secret.html"), self.talk)
        self.assertTrue(any("不在 talk 目錄裡" in w for w in warnings), warnings)

    def test_derived_views_get_every_item(self):
        o = outline_row({"#": "1", "版型": "L-CUSTOM", "畫面內容": self.ROW}, 1)
        self.assertEqual(o.closing, "問責跟著行政權的來源走")
        self.assertEqual(len(o.items), 2)


class SignOffTests(unittest.TestCase):
    """The design stage may give a row a form; it may not change what the row says."""

    def setUp(self):
        self.base = storyboard([("—", "—", CARDS), ("—", "—", "title: 結語<br>points:<br>- 一<br>- 二")])
        self.digest = content_digest(self.base)

    def test_design_work_keeps_the_digest(self):
        designed = storyboard([("L-3CARD-VERDICT", "M-STEP", CARDS + "<br>variant: bubble"),
                               ("L-FINALE-SUMMARY", "—", "title: 結語<br>points_align: left<br>points:<br>- 一<br>- 二")])
        self.assertEqual(content_digest(designed), self.digest)
        # the same text moved into the slots another layout reads
        moved = storyboard([("L-FLOW-3STAGE", "M-POP", CARDS.replace("cards:", "stages:")),
                            ("—", "—", "title: 結語<br>points:<br>- 一<br>- 二")])
        self.assertEqual(content_digest(moved), self.digest)
        self.assertEqual(content_digest(with_premise(self.base, "- Seed: 4821")), self.digest)

    def test_content_changes_move_the_digest(self):
        for changed in (
            storyboard([("—", "—", CARDS.replace("成本上升", "成本升")), ("—", "—", "title: 結語<br>points:<br>- 一<br>- 二")]),
            storyboard([("—", "—", CARDS.replace("<br>- [丙] 人才: 文化磨合", "")), ("—", "—", "title: 結語<br>points:<br>- 一<br>- 二")]),
            storyboard([("—", "—", CARDS)]),
            self.base.replace("- 聽眾：乙", "- 聽眾：丙"),
            self.base.replace("| P1 |", "| P2 |", 1),
        ):
            self.assertNotEqual(content_digest(changed), self.digest)

    def test_compile_refuses_content_changed_after_the_sign_off(self):
        talk = Path(tempfile.mkdtemp(prefix="thesisbug2-test-sign-"))
        try:
            signed = with_premise(storyboard([("L-3CARD-VERDICT", "—", CARDS)]),
                                  f"- 內容簽核：2026-11-21 · {content_digest(storyboard([('L-3CARD-VERDICT', '—', CARDS)]))}（註）")
            self.assertEqual(sign_problem(signed), "")
            (talk / "storyboard.md").write_text(signed, encoding="utf-8")
            self.assertEqual(deck_compile.compile_checked(talk)[2], [])
            # a design pass that trims a card to make the row fit
            (talk / "storyboard.md").write_text(signed.replace("成本上升", "升"), encoding="utf-8")
            problems = deck_compile.compile_checked(talk)[2]
            self.assertTrue(problems and "在簽核之後改過" in problems[0], problems)
        finally:
            shutil.rmtree(talk, ignore_errors=True)

    def test_an_unsigned_storyboard_is_not_refused(self):
        self.assertIsNone(signed_digest(self.base))
        self.assertEqual(sign_problem(self.base), "")


class PremiseTests(unittest.TestCase):
    def test_density_is_high_unless_the_premises_say_otherwise(self):
        self.assertEqual(density(storyboard([])), ("高", False))
        text = storyboard([], "- 標題：甲\n- 密度：中（課堂導讀，同學邊聽邊看）\n")
        self.assertEqual(density(text), ("中", True))
        scaffold = (REPO / "assets/templates/presentation/scaffold/storyboard.md").read_text(encoding="utf-8")
        self.assertEqual(density(scaffold), ("高", True))

    def test_type_floor_comes_from_the_room(self):
        self.assertEqual(type_floor(storyboard([])), 34)
        self.assertEqual(type_floor(storyboard([], "- 場地與投影：線上會議分享畫面，字級下限 27px，深色\n")), 27)
        scaffold = (REPO / "assets/templates/presentation/scaffold/storyboard.md").read_text(encoding="utf-8")
        self.assertEqual(type_floor(scaffold), 34)

    def test_deck_must_declare_the_floor_the_storyboard_sets(self):
        talk = Path(tempfile.mkdtemp(prefix="thesisbug2-test-floor-"))
        try:
            (talk / "storyboard.md").write_text(storyboard([], "- 場地與投影：小會議室大螢幕，字級下限 30px\n"), encoding="utf-8")
            (talk / "deck.html").write_text('<html lang="zh-Hant"><body></body></html>', encoding="utf-8")
            self.assertIn('data-deck-type-floor="30"', deck_compile.floor_problem(talk))
            (talk / "deck.html").write_text('<html lang="zh-Hant" data-deck-type-floor="30"><body></body></html>', encoding="utf-8")
            self.assertEqual(deck_compile.floor_problem(talk), "")
            (talk / "storyboard.md").write_text(storyboard([], "- 場地與投影：字級下限 20px\n"), encoding="utf-8")
            self.assertIn("不是支援的值", deck_compile.floor_problem(talk))
        finally:
            shutil.rmtree(talk, ignore_errors=True)

    def test_deck_scripts_read_the_declared_floor(self):
        asset = SKILLS / "deck-svg/template/asset"
        self.assertIn("dataset.deckTypeFloor", (asset / "deck-check.js").read_text(encoding="utf-8"))
        self.assertIn("dataset.deckTypeFloor", (asset / "deck-font-controls.js").read_text(encoding="utf-8"))

    def test_characters_on_a_slide_are_counted_from_its_text(self):
        self.assertEqual(char_count("title: 甲乙<br>variant: bubble<br>cards:<br>- [丙] 丁: 戊己"), 6)


class StageSeparationTests(unittest.TestCase):
    """The storyboard stage's skill does not put the layouts in front of whoever writes the content."""

    def test_deck_plan_names_no_catalog_layout(self):
        for path in [SKILLS / "deck-plan/SKILL.md", *sorted((SKILLS / "deck-plan/reference").glob("*.md"))]:
            codes = set(re.findall(r"\bL-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", path.read_text(encoding="utf-8")))
            self.assertLessEqual(codes, {"L-CUSTOM"}, path.name)
            self.assertNotIn("layout-catalog", path.read_text(encoding="utf-8"), path.name)

    def test_catalogs_belong_to_the_design_stage(self):
        for name in ("layout-catalog.md", "motion-catalog.md"):
            self.assertTrue((SKILLS / "deck-svg/reference" / name).is_file(), name)
            self.assertFalse((SKILLS / "deck-plan/reference" / name).exists(), name)

    def test_scaffold_leaves_the_design_columns_to_the_design_stage(self):
        scaffold = (REPO / "assets/templates/presentation/scaffold/storyboard.md").read_text(encoding="utf-8")
        self.assertIn("「版型」「動態」兩欄留 —", scaffold)
        self.assertIn("- 密度：高", scaffold)


if __name__ == "__main__":
    unittest.main()
