"""Tests for the seed, the depth variants and the explorer page built from the catalog examples."""

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

from scripts._deck_catalog import CATALOG, VisualRhythmResolver, tag_accents  # noqa: E402
from scripts._deck_explorer import build_explorer, catalog_examples, render_example  # noqa: E402
from scripts._deck_outline import ensure_seed, extract_seed, outline_row, with_seed  # noqa: E402

DECK_CSS = (REPO / ".agents/skills/deck-svg/template/asset/deck.css").read_text(encoding="utf-8")
TABLE = ("| # | 來源論點 | 內容形狀 | 版型 | 動態 | 講 | 畫面內容 | 講者備註 | AI 協助 |\n"
         "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")


def row(layout: str, content: str, num: int = 1) -> dict[str, str]:
    return {"#": str(num), "版型": layout, "畫面內容": content}


class VariantTests(unittest.TestCase):
    def test_every_layout_has_an_example_in_the_catalog_document(self):
        self.assertEqual(set(catalog_examples()), set(CATALOG))

    def test_every_declared_variant_renders_differently(self):
        # Ten layouts once declared variants their renderers ignored, so a seed changed only the accent.
        for layout_id, example in catalog_examples().items():
            variants = CATALOG[layout_id].allowed_variants
            rendered = {v: render_example(layout_id, v, example) for v in variants}
            self.assertEqual(len(set(rendered.values())), len(variants), layout_id)

    def test_a_variant_is_a_form_with_its_own_style_rule(self):
        # A variant that differed only by a class deck.css does not style would look the same on stage.
        for layout_id, example in catalog_examples().items():
            variants = CATALOG[layout_id].allowed_variants
            if len(variants) < 2:
                continue
            classes = {v: set(re.findall(r'class="([^"]*)"', render_example(layout_id, v, example)))
                       for v in variants}
            for v in variants[1:]:
                own = {c for names in classes[v] - classes[variants[0]] for c in names.split()}
                styled = [c for c in own if re.search(rf"\.{re.escape(c)}(?![\w-])", DECK_CSS)]
                self.assertTrue(styled, f"{layout_id} {v}: none of {sorted(own)} is styled in deck.css")

    def test_documented_variants_are_the_implemented_ones(self):
        doc = (REPO / ".agents/skills/deck-plan/reference/layout-catalog.md").read_text(encoding="utf-8")
        for section in re.split(r"(?m)^### \d+\. ", doc)[1:]:
            layout_id = re.match(r"`(L-[A-Z0-9-]+)`", section).group(1)
            line = re.search(r"\*\*深度變體\*\*：(.*)", section)
            documented = re.findall(r"`([a-z0-9-]+)`（", line.group(1)) if line else ["default"]
            self.assertEqual(documented or ["default"], CATALOG[layout_id].allowed_variants, layout_id)

    def test_a_layout_shows_every_variant_before_repeating_one(self):
        layout = CATALOG["L-3CARD-VERDICT"]
        for seed in range(20):
            res = VisualRhythmResolver(seed)
            drawn = [res.resolve(layout, i, 9, "e", "t")[1] for i in range(6)]
            self.assertEqual(sorted(drawn[:3]), sorted(layout.allowed_variants))
            self.assertEqual(drawn[:3], drawn[3:])

    def test_seeds_give_different_mixes(self):
        layouts = [CATALOG[k] for k in ("L-3CARD-VERDICT", "L-FLOW-3STAGE", "L-VS-CONFRONT", "L-DEFN-EXAMPLE")]

        def mix(seed: int) -> tuple[str, ...]:
            res = VisualRhythmResolver(seed)
            return tuple(res.resolve(layout, i, 9, "e", "t")[1] for i, layout in enumerate(layouts))
        self.assertGreater(len({mix(seed) for seed in range(40)}), 10)

    def test_pinning_one_slide_leaves_the_others_as_drawn(self):
        layout = CATALOG["L-FLOW-3STAGE"]
        free, pinned = VisualRhythmResolver(7), VisualRhythmResolver(7)
        a = [free.resolve(layout, i, 9, "e", "t") for i in range(4)]
        b = [pinned.resolve(layout, i, 9, "e", "t", pinned="disc-rail" if i == 1 else "") for i in range(4)]
        self.assertEqual(b[1][1], "disc-rail")
        for i in (0, 2, 3):
            self.assertEqual((a[i][0].accent, a[i][1]), (b[i][0].accent, b[i][1]))

    def test_variant_slot_pins_and_an_unknown_name_warns(self):
        content = "title: t<br>stages:<br>- a: 1<br>- b: 2<br>- c: 3"
        html, warnings = deck_compile.render_row(row("L-FLOW-3STAGE", content + "<br>variant: chevron-step"),
                                                 1, 3, VisualRhythmResolver(1))
        self.assertIn("flowdiag--chevron-step", html)
        self.assertEqual(warnings, [])
        _, warnings = deck_compile.render_row(row("L-FLOW-3STAGE", content + "<br>variant: zigzag"),
                                              1, 3, VisualRhythmResolver(1))
        self.assertTrue(any("沒有變體 'zigzag'" in w for w in warnings), warnings)


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="thesisbug2-test-seed-"))
        self.storyboard = self.tmp / "storyboard.md"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_missing_seed_is_written_once_as_the_last_premise_bullet(self):
        self.storyboard.write_text("# 分鏡稿\n\n## 前提\n\n- 標題：甲\n- 聽眾：乙\n  第二行\n\n## 投影片\n\n" + TABLE,
                                   encoding="utf-8")
        seed, written = ensure_seed(self.storyboard)
        self.assertTrue(written)
        self.assertTrue(1000 <= seed <= 9999)
        text = self.storyboard.read_text(encoding="utf-8")
        self.assertEqual(extract_seed(text), seed)
        premise = text.split("## 前提")[1].split("## 投影片")[0]
        self.assertRegex(premise, rf"第二行\n- Seed: {seed}（")
        self.assertEqual(ensure_seed(self.storyboard), (seed, False))
        self.assertEqual(self.storyboard.read_text(encoding="utf-8"), text)

    def test_a_written_seed_is_kept(self):
        self.storyboard.write_text("## 前提\n\n- Seed: 7\n", encoding="utf-8")
        self.assertEqual(ensure_seed(self.storyboard), (7, False))

    def test_a_storyboard_without_premises_gets_the_section(self):
        text = with_seed("# 分鏡稿\n\n## 投影片\n\n" + TABLE, 4821)
        self.assertLess(text.index("## 前提"), text.index("## 投影片"))
        self.assertEqual(extract_seed(text), 4821)
        # a bullet, not a table row: ./fw build counts table rows as slides
        self.assertEqual(deck_compile.extract_storyboard_rows(text), [])

    def test_compiling_for_a_check_never_writes_the_storyboard(self):
        talk = self.tmp / "talk"
        talk.mkdir()
        source = "## 前提\n\n- 標題：甲\n\n## 投影片\n\n" + TABLE + "| 0 | — | 封面 | L-HERO-TITLE | — | 1 | title: 甲 | — | — |\n"
        (talk / "storyboard.md").write_text(source, encoding="utf-8")
        deck_compile.compile_storyboard(talk)
        self.assertEqual((talk / "storyboard.md").read_text(encoding="utf-8"), source)

    def test_stale_deck_css_is_reported(self):
        talk = self.tmp / "talk"
        (talk / "asset").mkdir(parents=True)
        self.assertEqual(deck_compile.stale_deck_css(talk, "talk"), "")
        (talk / "asset" / "deck.css").write_text(DECK_CSS, encoding="utf-8")
        self.assertEqual(deck_compile.stale_deck_css(talk, "talk"), "")
        (talk / "asset" / "deck.css").write_text(DECK_CSS + "/* older */", encoding="utf-8")
        self.assertIn("./fw deck-refresh talk", deck_compile.stale_deck_css(talk, "talk"))


class BannerGridTests(unittest.TestCase):
    CONTENT = ('title: 架構<br>banner: {tag: "主軸", head: "甲理論", sub: "Theory A", body: "一句說明"}<br>cards:<br>'
               "- [tag: 美國, head: 子項一, sub: One, body: 說明一, cite: Smith (1987)]<br>"
               "- [tag: 中俄, head: 子項二, sub: Two, body: 說明二, cite: Lee (2001)]<br>"
               "- [tag: 美國, head: 子項三, body: 說明三]<br>"
               "- [中小國家] 子項四: 說明四")

    def render(self, content: str, variant: str = "soft-cards") -> tuple[str, list[str]]:
        return deck_compile.render_row(row("L-BANNER-6GRID", content + f"<br>variant: {variant}"),
                                       1, 3, VisualRhythmResolver(1))

    def test_cards_carry_second_name_citation_and_a_category_pill(self):
        html, warnings = self.render(self.CONTENT)
        self.assertEqual(warnings, [])
        for text in ("甲理論<small>Theory A</small>", '<p class="axis__sub">One</p>',
                     '<p class="axis__cite">Smith (1987)</p>', "<h3>子項四</h3>", "<p>說明四</p>"):
            self.assertIn(text, html)
        # four cards make a 2×2 grid
        self.assertIn("axis__grid--2", html)

    def test_one_category_has_one_colour(self):
        html, _ = self.render(self.CONTENT)
        pills = re.findall(r'<span class="pill" style="--chapter:(var\(--c\d\))">([^<]+)</span>', html)
        colour = {}
        for value, tag in pills:
            self.assertEqual(colour.setdefault(tag, value), value)
        self.assertEqual(len(pills), 4)
        self.assertEqual(len(set(colour.values())), 3)
        self.assertEqual(tag_accents(["a", "b", "a", "c"]), {"a": "var(--c1)", "b": "var(--c4)", "c": "var(--c2)"})

    def test_a_seventh_card_warns_instead_of_vanishing_silently(self):
        many = "title: t<br>banner: 主軸<br>cards:<br>" + "<br>".join(f"- [類] 項{i}: 說明" for i in range(7))
        html, warnings = self.render(many)
        self.assertEqual(html.count('class="axis__card'), 6)
        self.assertTrue(any("最多 6 張卡" in w for w in warnings), warnings)
        self.assertIn("<h3>主軸</h3>", html)

    def test_outline_keeps_the_banner_and_every_card_text(self):
        o = outline_row(row("L-BANNER-6GRID", self.CONTENT), 1)
        self.assertEqual((o.big, o.big_label, o.lead), ("甲理論（Theory A）", "主軸", "一句說明"))
        self.assertEqual(o.items[0].line(), "美國｜子項一（One）：說明一（Smith (1987)）")
        self.assertEqual(o.items[3].line(), "中小國家｜子項四：說明四")


class ExplorerTests(unittest.TestCase):
    def test_page_is_built_from_the_renderers(self):
        tmp = Path(tempfile.mkdtemp(prefix="thesisbug2-test-explorer-"))
        try:
            page = build_explorer(tmp / "explorer.html").read_text(encoding="utf-8")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertNotIn("/*CATALOG_DATA*/", page)
        for layout_id, layout in CATALOG.items():
            self.assertIn(f'"id": "{layout_id}"', page)
            for variant in layout.allowed_variants:
                self.assertIn(f'"{variant}": "', page)
        # the stylesheets are linked by absolute address, because the page is written outside the repo
        self.assertRegex(page, r'href="file://[^"]*/deck-svg/template/asset/deck\.css"')

    def test_the_shell_carries_no_hand_written_layout(self):
        shell = (REPO / "docs/layout-explorer.html").read_text(encoding="utf-8")
        self.assertIn("/*CATALOG_DATA*/[]", shell)
        self.assertNotIn('<section class="slide', shell)


if __name__ == "__main__":
    unittest.main()
