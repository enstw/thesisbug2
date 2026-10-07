"""Tests for the presentation layout catalog, slot parser, and deck compiler."""

import shutil
import tempfile
import unittest
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("deck_compile", REPO / "scripts/deck-compile.py")
deck_compile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deck_compile)

from scripts._deck_catalog import (
    CATALOG,
    SlideContext,
    VisualRhythmResolver,
    get_layout,
    parse_slot_payload,
)

compile_storyboard = deck_compile.compile_storyboard
apply_compilation = deck_compile.apply_compilation
extract_seed = deck_compile.extract_seed


class SlotParserTests(unittest.TestCase):
    def test_parse_simple_kv(self):
        text = "title: 供應鏈重組策略<br>lead: 地緣政治壓力加劇"
        slots = parse_slot_payload(text)
        self.assertEqual(slots.get("title"), "供應鏈重組策略")
        self.assertEqual(slots.get("lead"), "地緣政治壓力加劇")

    def test_parse_cards_with_tags_and_colons(self):
        text = (
            "lead: 全球化遭遇三大逆流<br>"
            "cards:<br>"
            "- [資本] 成本激增: 赴美建廠資本支出攀升 40%<br>"
            "- [生態] 聚落缺失: 缺乏在地化學與封測即時支援<br>"
            "- [人才] 治理磨合: 派駐文化差異與當地技術勞工短缺<br>"
            "verdict: 區域化保障供應鏈韌性，但必然犧牲極限效率"
        )
        slots = parse_slot_payload(text)
        self.assertEqual(slots.get("lead"), "全球化遭遇三大逆流")
        self.assertEqual(slots.get("verdict"), "區域化保障供應鏈韌性，但必然犧牲極限效率")
        cards = slots.get("cards", [])
        self.assertEqual(len(cards), 3)
        self.assertEqual(cards[0]["tag"], "資本")
        self.assertEqual(cards[0]["head"], "成本激增")
        self.assertEqual(cards[0]["body"], "赴美建廠資本支出攀升 40%")
        self.assertEqual(cards[1]["tag"], "生態")
        self.assertEqual(cards[2]["tag"], "人才")

    def test_parse_inline_dict(self):
        text = 'side_a: {camp: "全面對美結盟", points: ["獲取最高階安全保證", "技術標準深度綁定"]}'
        slots = parse_slot_payload(text)
        side_a = slots.get("side_a", {})
        self.assertEqual(side_a.get("camp"), "全面對美結盟")
        self.assertEqual(side_a.get("points"), ["獲取最高階安全保證", "技術標準深度綁定"])


class VisualRhythmResolverTests(unittest.TestCase):
    def test_determinism_with_same_seed(self):
        res1 = VisualRhythmResolver(seed=42)
        res2 = VisualRhythmResolver(seed=42)
        l_3card = CATALOG["L-3CARD-VERDICT"]

        ctx1, var1 = res1.resolve(l_3card, 1, 5, "理論", "標題1")
        ctx2, var2 = res2.resolve(l_3card, 1, 5, "理論", "標題1")

        self.assertEqual(ctx1.accent, ctx2.accent)
        self.assertEqual(var1, var2)

    def test_non_consecutive_accents(self):
        res = VisualRhythmResolver(seed=2026)
        l_3card = CATALOG["L-3CARD-VERDICT"]
        accents = []
        for i in range(1, 15):
            ctx, _ = res.resolve(l_3card, i, 15, "章節", f"標題{i}")
            accents.append(ctx.accent)

        for i in range(len(accents) - 1):
            self.assertNotEqual(accents[i], accents[i + 1], f"Slide {i} and {i+1} have the same accent {accents[i]}")

    def test_all_16_layouts_exist(self):
        self.assertEqual(len(CATALOG), 16)
        for lid in (
            "L-HERO-TITLE", "L-FINALE-SUMMARY", "L-3CARD-VERDICT", "L-4CARD-GRID",
            "L-BENTO-FOCUS", "L-SPLIT-ANCHOR", "L-VS-CONFRONT", "L-MATRIX-DEEPDIVE",
            "L-SPECTRUM-POLES", "L-FLOW-3STAGE", "L-TIMELINE-RAIL", "L-CASCADE-FUNNEL",
            "L-QUOTE-CRITIQUE", "L-HYPOTHESIS-TEST", "L-STAT-HERO", "L-DEFN-EXAMPLE"
        ):
            self.assertIn(lid, CATALOG)
            defn = get_layout(lid)
            self.assertEqual(defn.id, lid)


class OverridableLabelTests(unittest.TestCase):
    """Fixed box labels (定論, 焦點象限特寫, 實證發現) can be renamed or dropped per slide."""

    CTX = SlideContext(slide_num=1, total_slides=1, accent="var(--c1)", eyebrow="e", data_label="d", variant="")

    def render(self, layout, text, variant=None):
        defn = get_layout(layout)
        return defn.render_func(parse_slot_payload(text), variant or defn.allowed_variants[0], self.CTX)

    def test_default_verdict_label_is_kept(self):
        html = self.render("L-FLOW-3STAGE", "title: t<br>stages:<br>- a: x<br>- b: y<br>- c: z<br>verdict: v")
        self.assertIn("<em>最終均衡：</em>v", html)

    def test_verdict_label_renames_prefix(self):
        html = self.render("L-FLOW-3STAGE", "title: t<br>stages:<br>- a: x<br>- b: y<br>- c: z<br>verdict: v<br>verdict_label: 機制意涵")
        self.assertIn("<em>機制意涵：</em>v", html)
        self.assertNotIn("最終均衡", html)

    def test_verdict_label_none_drops_prefix(self):
        html = self.render("L-BENTO-FOCUS", "title: t<br>cards:<br>- [a] h: b<br>- [b] h: b<br>- [c] h: b<br>verdict: v<br>verdict_label: none")
        self.assertNotIn("<em>", html.split('class="verdict')[1])

    def test_matrix_focus_none_and_note_label(self):
        html = self.render(
            "L-MATRIX-DEEPDIVE",
            "title: t<br>cells:<br>- a: 1<br>- b: 2<br>- c: 3<br>- d: 4<br>focus_quadrant: none<br>note_label: 解讀說明<br>deepdive_note: n",
        )
        self.assertNotIn(' hi"', html)
        self.assertIn("解讀說明", html)
        self.assertNotIn("焦點象限特寫", html)

    def test_matrix_default_focus_still_highlights(self):
        html = self.render("L-MATRIX-DEEPDIVE", "title: t<br>cells:<br>- a: 1<br>- b: 2<br>- c: 3<br>- d: 4<br>deepdive_note: n")
        self.assertIn(' hi"', html)
        self.assertIn("焦點象限特寫 (Q1)", html)

    def test_hypothesis_finding_label(self):
        html = self.render("L-HYPOTHESIS-TEST", 'title: t<br>finding: {label: "待解釋現象", status: "s", empirical_evidence: "e"}<br>theoretical_puzzle: p')
        self.assertIn("待解釋現象：s", html)
        self.assertNotIn("實證發現", html)

    def test_quote_critique_keeps_card_body(self):
        html = self.render("L-QUOTE-CRITIQUE", "title: t<br>quote: q<br>cite: c<br>critiques:<br>- [名詞] 甲 vs 乙: 甲是一種說明，乙是另一種說明<br>- [b] only head<br>- [c] x")
        self.assertIn("甲是一種說明，乙是另一種說明", html)
        self.assertIn("only head", html)

    def test_matrix_width_wide(self):
        base = "title: t<br>cells:<br>- a: 1<br>- b: 2<br>- c: 3<br>- d: 4<br>deepdive_note: n"
        self.assertIn("matrix-deepdive--wide", self.render("L-MATRIX-DEEPDIVE", base + "<br>matrix_width: wide"))
        self.assertNotIn("matrix-deepdive--wide", self.render("L-MATRIX-DEEPDIVE", base))

    def test_cascade_label_width_narrow(self):
        base = "title: t<br>levels:<br>- [甲] h: b<br>- [乙] h: b<br>- [丙] h: b"
        self.assertIn("tiers--narrow", self.render("L-CASCADE-FUNNEL", base + "<br>label_width: narrow"))
        self.assertNotIn("tiers--narrow", self.render("L-CASCADE-FUNNEL", base))

    def test_hero_title_lines(self):
        html = self.render("L-HERO-TITLE", "title: 甲乙，丙丁？<br>title_lines:<br>- 甲乙，<br>- 丙丁？")
        self.assertIn("甲乙，<br>丙丁？", html)
        self.assertIn("white-space: nowrap", html.split("<h1")[1].split(">")[0])
        self.assertNotIn("font-size", html.split("<h1")[1].split(">")[0])
        long = self.render("L-HERO-TITLE", "title: x<br>title_lines:<br>- 一二三四五六七八九十十一十二")
        self.assertIn("font-size: calc(", long.split("<h1")[1].split(">")[0])
        self.assertIn('data-label="甲乙，丙丁？"', html)
        colon = self.render("L-HERO-TITLE", "title: 甲乙：丙丁<br>title_lines:<br>- 甲乙：<br>- 丙丁")
        self.assertIn("甲乙：<br>丙丁", colon)

    def test_hero_sub_lines(self):
        html = self.render("L-HERO-TITLE", "title: t<br>sub: 問題——來源<br>sub_lines:<br>- 問題？<br>- Author（2020）來源")
        p = html.split('<p class="hero__sub')[1]
        self.assertIn("問題？<br>Author（2020）來源", p)
        self.assertIn("white-space: nowrap", p.split(">")[0])
        self.assertNotIn("font-size", p.split(">")[0])
        long = self.render("L-HERO-TITLE", "title: t<br>sub_lines:<br>- " + "長" * 40)
        self.assertIn("font-size: calc(36px", long.split('<p class="hero__sub')[1].split(">")[0])
        floor = self.render("L-HERO-TITLE", "title: t<br>sub_lines:<br>- " + "長" * 80)
        self.assertIn("font-size: calc(34px", floor.split('<p class="hero__sub')[1].split(">")[0])
        plain = self.render("L-HERO-TITLE", "title: t<br>sub: 一行")
        self.assertIn('<p class="hero__sub rise d1">一行</p>', plain)

    def test_finale_points_align_left(self):
        html = self.render("L-FINALE-SUMMARY", "heading: h<br>points:<br>- a<br>points_align: left")
        self.assertIn('style="text-align:left"', html)
        self.assertNotIn("text-align", self.render("L-FINALE-SUMMARY", "heading: h<br>points:<br>- a"))


class DeckCompilerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="thesisbug2-test-compile-"))
        self.talk = self.tmp / "talk"
        self.talk.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_compile_storyboard_to_deck_html(self):
        storyboard_content = """# 分鏡稿

## 前提

- 標題：半導體戰略
- Seed: 1337

## 投影片

| # | 來源論點 | 內容形狀 | 版型 | 講 | 畫面內容 | 口說重點 | 名詞與提問 | AI 協助 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0 | — | 14 章節／封面 | L-HERO-TITLE | 0.5 min | title: 半導體戰略<br>sub: 大國博弈下的地緣邏輯 | 開場致詞 | — | — |
| 1 | P1 | 3 Theory primer | L-3CARD-VERDICT | 2 min | title: 核心困境<br>lead: 逆全球化浪潮<br>cards:<br>- [資本] 支出膨脹: 成本上升 40%<br>- [聚落] 支援斷鏈: 缺乏化學品配套<br>- [人才] 勞動文化: 管理磨合困難<br>verdict: 區域化代價高昂 | 口說要點 | 晶片、Q1 | — |
| 2 | P2 | 14 結論 | L-FINALE-SUMMARY | 1 min | heading: 結語<br>onesentence: 戰略安全與經濟效率不可兼得 | 總結觀點 | — | — |
"""
        (self.talk / "storyboard.md").write_text(storyboard_content, encoding="utf-8")

        mock_deck = """<!DOCTYPE html>
<html>
<head>
<!-- 手寫的部分只有底下 <deck-stage> 內的投影片與 speaker-notes。 -->
<link rel="stylesheet" href="asset/deck.css">
</head>
<body>
<deck-stage width="1920" height="1080">
  <section class="slide" data-label="old">Old</section>
  <script type="application/json" id="speaker-notes">
  []
  </script>
</deck-stage>
</body>
</html>"""
        (self.talk / "deck.html").write_text(mock_deck, encoding="utf-8")

        # Compile
        compiled, warnings = compile_storyboard(self.talk)
        self.assertEqual(warnings, [])
        self.assertIn("半導體戰略", compiled)
        self.assertIn("核心困境", compiled)
        self.assertIn("結語", compiled)
        self.assertIn("card--", compiled)
        self.assertIn("verdict box", compiled)

        changed = apply_compilation(self.talk, compiled, dry_run=False)
        self.assertTrue(changed)

        # Verify new deck content
        new_deck = (self.talk / "deck.html").read_text(encoding="utf-8")
        self.assertIn("data-label=\"半導體戰略\"", new_deck)
        self.assertIn("data-label=\"核心困境\"", new_deck)
        self.assertIn("data-label=\"結語\"", new_deck)
        self.assertIn('<span class="eyebrow">Theory primer</span>', new_deck)
        self.assertNotIn('<span class="eyebrow">3</span>', new_deck)
        self.assertIn('<link rel="stylesheet" href="asset/deck.css">', new_deck)
        self.assertIn('<deck-stage width="1920" height="1080">', new_deck)
        self.assertIn('<script type="application/json" id="speaker-notes">', new_deck)

        # Second run without changes should report not changed
        changed_again = apply_compilation(self.talk, compiled, dry_run=False)
        self.assertFalse(changed_again)

    def test_build_deck_gate_catches_out_of_sync_storyboard(self):
        storyboard_content = """# 分鏡稿

## 前提

- 標題：測試簡報
- Seed: 42

## 投影片

| # | 來源論點 | 內容形狀 | 版型 | 講 | 畫面內容 | 口說重點 | 名詞與提問 | AI 協助 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0 | — | 14 封面 | L-HERO-TITLE | 0.5 min | title: 測試簡報 | 開場 | — | — |
| 1 | P1 | 3 理論 | L-3CARD-VERDICT | 2 min | title: 三要點<br>cards:<br>- A: a<br>- B: b<br>- C: c<br>verdict: 結論 | 要點 | — | — |
"""
        (self.tmp / "WORK.json").write_text('{"type": "presentation", "variant": "thesis"}', encoding="utf-8")
        (self.talk / "talk.json").write_text('{"title": "T", "variant": "thesis", "model": ["talk/points.md"]}', encoding="utf-8")
        (self.talk / "storyboard.md").write_text(storyboard_content, encoding="utf-8")
        (self.talk / "points.md").write_text("# 論點\n\nP1: 論點一。\n", encoding="utf-8")
        mock_deck = """<!DOCTYPE html><html><body><deck-stage width="1920" height="1080">
<section class="slide" data-label="old">Old</section>
<script type="application/json" id="speaker-notes">[]</script>
</deck-stage></body></html>"""
        (self.talk / "deck.html").write_text(mock_deck, encoding="utf-8")

        spec = importlib.util.spec_from_file_location("build", REPO / "scripts/build.py")
        build_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build_mod)

        # Before compile: deck gate should catch that deck is out of sync with storyboard
        with self.assertRaises(SystemExit) as cm:
            build_mod.deck_gate(self.tmp, self.talk, self.tmp)
        self.assertIn("deck out of sync", str(cm.exception))

        # After compile: deck gate should pass sync check without raising SystemExit
        compiled, _ = compile_storyboard(self.talk)
        apply_compilation(self.talk, compiled, dry_run=False)
        try:
            build_mod.deck_gate(self.tmp, self.talk, self.tmp)
        except SystemExit as e:
            self.assertNotIn("deck out of sync", str(e))


if __name__ == "__main__":
    unittest.main()
