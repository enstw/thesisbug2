"""The derived Views (deck-3d, deck-slidev) read a storyboard through one outline:
every catalog slot has a place in it, and each View renders that outline without
inventing or losing a row.

The 3D View's packing and placement run in the browser (world.js) and are checked
there, by `index.html#debug`; these tests stop at the DECK data handed to it."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


deck_3d = load("deck-3d")
deck_slidev = load("deck-slidev")

from scripts._deck_catalog import CATALOG, ITEM_CAP  # noqa: E402
from scripts._deck_outline import COMMON, SPECS, deck_notes, outline_storyboard  # noqa: E402
from scripts._paths import prose_files  # noqa: E402

HEADER = ("| # | 來源論點 | 內容形狀 | 版型 | 動態 | 講 | 畫面內容 | 講者備註 | AI 協助 |\n"
          "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")

ROWS = [
    ("L-HERO-TITLE", "—", "title: 泡一壺茶<br>sub: 水溫、時間與茶量<br>meta: 示範講者"),
    ("L-HERO-TITLE", "—", "title: 一、準備<br>sub: 器具與水"),
    ("L-3CARD-VERDICT", "M-STEP",
     "eyebrow: 準備<br>title: 三件器具<br>lead: 少一件也能泡<br>cards:<br>"
     "- [壺] 茶壺: 留住溫度<br>- [杯] 茶杯: 分次倒出<br>- [濾] 濾網: 擋住茶葉<br>verdict: 先備齊再燒水"),
    ("L-VS-CONFRONT", "—",
     'title: 熱泡還是冷泡<br>issue: 同一種茶葉，哪一種比較順口？<br>'
     'side_a: {camp: "熱泡", points: ["三分鐘完成", "香氣明顯"]}<br>'
     'side_b: {camp: "冷泡", points: ["不易苦澀", "要等一晚"]}<br>ask_or_verdict: 看你有多少時間'),
    ("L-HERO-TITLE", "—", "title: 二、沖泡"),
    ("L-FLOW-3STAGE", "—",
     "title: 沖泡三步<br>stages:<br>- 溫壺: 先用熱水燙過<br>- 注水: 沿壺邊倒入<br>- 出湯: 一次倒完<br>verdict: 每一步都不要急"),
    ("L-STAT-HERO", "—",
     "title: 水溫決定苦不苦<br>stat_number: 85°C<br>stat_label: 綠茶的建議水溫<br>context: 沸水放涼兩分鐘<br>"
     "implications:<br>- 太燙: 茶湯發苦<br>- 太涼: 香氣出不來"),
    ("L-QUOTE-CRITIQUE", "—",
     "title: 一句老話<br>quote: 水是茶的母親。<br>citation: 示範引文，頁 3<br>critiques:<br>- [水] 硬水: 茶色偏暗"),
    ("L-FINALE-SUMMARY", "—", "heading: 結語<br>onesentence: 好水、對的溫度、不急。<br>points:<br>- 先備器具<br>- 再顧水溫"),
]


def storyboard(rows=ROWS):
    lines = [f"| {i} | P{i} | 示範 | {layout} | {motion} | 1 min | {content} | — | 示範 |"
             for i, (layout, motion, content) in enumerate(rows)]
    return "# 分鏡\n\n## 前提\n\n- **標題：** 泡一壺茶\n\n## 投影片\n\n" + HEADER + "\n".join(lines) + "\n"


class OutlineTests(unittest.TestCase):
    def setUp(self):
        self.outlines, self.warnings = outline_storyboard(storyboard())

    def test_every_catalog_layout_has_a_spec_that_places_every_slot(self):
        # A slot added to a layout without a place in the outline would vanish from the derived Views.
        self.assertEqual(set(CATALOG), set(SPECS))
        for layout_id, layout in CATALOG.items():
            known = SPECS[layout_id].slots() | set(COMMON)
            unplaced = set(layout.required_slots) | set(layout.optional_slots)
            self.assertFalse(unplaced - known, f"{layout_id}: {sorted(unplaced - known)}")

    def test_rows_keep_their_order_and_kinds(self):
        self.assertEqual([o.num for o in self.outlines], list(range(len(ROWS))))
        self.assertEqual([o.kind for o in self.outlines],
                         ["cover", "section", "content", "content", "section", "content", "content",
                          "content", "finale"])
        self.assertEqual(self.warnings, [])

    def test_a_closing_hero_title_is_the_finale_not_a_section(self):
        outlines, _ = outline_storyboard(storyboard(ROWS[:3] + [("L-HERO-TITLE", "—", "title: 謝謝")]))
        self.assertEqual(outlines[-1].kind, "finale")

    def test_slots_land_in_their_roles(self):
        cards = self.outlines[2]
        self.assertEqual((cards.label, cards.title, cards.lead), ("準備", "三件器具", "少一件也能泡"))
        self.assertEqual([(it.tag, it.head, it.body) for it in cards.items],
                         [("壺", "茶壺", "留住溫度"), ("杯", "茶杯", "分次倒出"), ("濾", "濾網", "擋住茶葉")])
        self.assertEqual(cards.closing, "先備齊再燒水")
        self.assertTrue(cards.steps)

        vs = self.outlines[3]
        self.assertTrue(vs.sides)
        self.assertEqual([(it.head, it.body) for it in vs.items],
                         [("熱泡", "三分鐘完成；香氣明顯"), ("冷泡", "不易苦澀；要等一晚")])

        self.assertTrue(self.outlines[5].ordered)
        stat = self.outlines[6]
        self.assertEqual((stat.big, stat.big_label, stat.lead), ("85°C", "綠茶的建議水溫", "沸水放涼兩分鐘"))
        quote = self.outlines[7]
        self.assertEqual((quote.quote, quote.cite), ("水是茶的母親。", "示範引文，頁 3"))
        finale = self.outlines[8]
        self.assertEqual((finale.title, finale.lead), ("結語", "好水、對的溫度、不急。"))

    def test_items_stop_at_the_layout_cap(self):
        many = "<br>".join(f"- [標{i}] 項目{i}: 說明{i}" for i in range(8))
        outlines, _ = outline_storyboard(storyboard([("L-3CARD-VERDICT", "—", f"title: 太多<br>cards:<br>{many}")]))
        self.assertEqual(len(outlines[0].items), ITEM_CAP["L-3CARD-VERDICT"])

    def test_a_drawing_is_reported_not_silently_lost(self):
        outlines, warnings = outline_storyboard(storyboard(
            [("L-CANVAS", "—", "title: 流程圖<br>lead: 一張圖<br>start: 開始<br>end: 結束")]))
        self.assertEqual(outlines[0].dropped, ["start", "end"])
        self.assertEqual(len(warnings), 1)
        self.assertIn("deck.html", warnings[0])

    def test_a_row_outside_the_catalog_is_skipped_with_a_warning(self):
        outlines, warnings = outline_storyboard(storyboard(ROWS[:1] + [(".matrix 3×3", "—", "title: 舊版型")]))
        self.assertEqual(len(outlines), 1)
        self.assertEqual(len(warnings), 1)


class NotesTests(unittest.TestCase):
    def talk(self, notes):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        talk = Path(tmp.name)
        if notes is not None:
            block = json.dumps(notes, ensure_ascii=False)
            (talk / "deck.html").write_text(
                f'<script type="application/json" id="speaker-notes">{block}</script>', encoding="utf-8")
        return talk

    def test_notes_come_from_the_assembled_deck(self):
        self.assertEqual(deck_notes(self.talk(["甲", "乙"]), 2), (["甲", "乙"], ""))

    def test_a_missing_deck_gives_empty_notes_and_says_why(self):
        notes, problem = deck_notes(self.talk(None), 2)
        self.assertEqual(notes, ["", ""])
        self.assertIn("missing", problem)

    def test_a_deck_from_another_storyboard_is_not_matched_by_position(self):
        notes, problem = deck_notes(self.talk(["甲", "乙", "丙"]), 2)
        self.assertEqual(notes, ["", ""])
        self.assertIn("3 speaker notes for 2", problem)


class Deck3DTests(unittest.TestCase):
    def setUp(self):
        self.outlines, _ = outline_storyboard(storyboard())
        self.notes = [f"備註{i}" for i in range(len(self.outlines))]
        self.deck = deck_3d.build_deck(self.outlines, self.notes, "後備標題")

    def test_section_rows_open_islands_and_the_cover_is_not_a_scene(self):
        self.assertEqual(self.deck["cover"], {"title": "泡一壺茶", "sub": "水溫、時間與茶量",
                                              "meta": "示範講者", "note": "備註0"})
        self.assertEqual([isl["name"] for isl in self.deck["islands"]], ["一、準備", "二、沖泡"])
        self.assertEqual(self.deck["islands"][0]["note"], "備註1")

    def test_rows_before_the_first_section_form_an_unnamed_island(self):
        outlines, _ = outline_storyboard(storyboard([ROWS[0], ROWS[2], ROWS[1], ROWS[3]]))
        deck = deck_3d.build_deck(outlines, [""] * 4, "t")
        self.assertEqual([isl["name"] for isl in deck["islands"]], ["", "一、準備"])

    def test_items_with_a_heading_and_a_body_unfold_into_their_own_scenes(self):
        scenes = [s for s in self.deck["islands"][0]["scenes"] if s["label"].startswith("2")]
        # overview, three items, the closing
        self.assertEqual([s["label"] for s in scenes],
                         ["2・三件器具", "2-1・茶壺", "2-2・茶杯", "2-3・濾網", "2-4・裁決"][:4] + [scenes[-1]["label"]])
        self.assertEqual(len(scenes), 5)
        self.assertEqual([b["t"] for b in scenes[0]["body"]], ["少一件也能泡", "壺｜茶壺", "杯｜茶杯", "濾｜濾網"])
        self.assertEqual((scenes[1]["title"], scenes[1]["big"], scenes[1]["body"]),
                         ("茶壺", "壺", [{"t": "留住溫度"}]))
        self.assertEqual(scenes[-1]["body"], [{"t": "先備齊再燒水", "lg": True}])
        # every stop within a row carries that row's note
        self.assertEqual({s["note"] for s in scenes}, {"備註2"})
        self.assertEqual({s["kicker"] for s in scenes}, {"準備"})

    def test_a_sequence_without_tags_numbers_its_scenes(self):
        flow = [s for s in self.deck["islands"][1]["scenes"] if s["label"].startswith("5")]
        self.assertEqual([b["t"] for b in flow[0]["body"]], ["1. 溫壺", "2. 注水", "3. 出湯"])
        self.assertEqual([s["big"] for s in flow[1:4]], ["1", "2", "3"])

    def test_two_camps_become_one_side_by_side_scene(self):
        duo = next(s for s in self.deck["islands"][0]["scenes"] if s.get("duo"))
        self.assertEqual(duo["left"], {"h": "熱泡", "t": "三分鐘完成；香氣明顯"})
        self.assertEqual(duo["right"], {"h": "冷泡", "t": "不易苦澀；要等一晚"})
        self.assertEqual((duo["lead"], duo["foot"]), ("同一種茶葉，哪一種比較順口？", "看你有多少時間"))

    def test_items_without_bodies_stay_on_one_scene(self):
        finale = [s for s in self.deck["islands"][1]["scenes"] if s["label"].startswith("8")]
        self.assertEqual(len(finale), 1)
        self.assertEqual([b["t"] for b in finale[0]["body"]], ["好水、對的溫度、不急。", "先備器具", "再顧水溫"])

    def test_the_deck_literal_cannot_close_its_script_element(self):
        text = deck_3d.deck_json({"title": "</script><b>", "sep": "a b"})
        self.assertNotIn("<", text)
        self.assertNotIn(" ", text)
        self.assertEqual(json.loads(text), {"title": "</script><b>", "sep": "a b"})

    def test_the_view_is_written_from_the_template_alone(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = deck_3d.write_view(Path(tmp.name), self.deck)
        self.assertEqual(sorted(p.name for p in out.iterdir()),
                         ["engine.js", "index.html", "presenter.html", "world.js"])
        index = (out / "index.html").read_text(encoding="utf-8")
        self.assertIn("<title>泡一壺茶</title>", index)
        self.assertNotIn("{{", index)
        literal = index.split("const DECK = ", 1)[1].split(";</script>", 1)[0]
        self.assertEqual(json.loads(literal), self.deck)

    def test_the_engine_carries_no_talk(self):
        # engine.js and world.js are copied as they are; a talk's words belong in DECK only.
        for name in ("engine.js", "world.js", "presenter.html", "host.html"):
            text = (deck_3d.TEMPLATE / name).read_text(encoding="utf-8")
            self.assertNotIn("泡一壺茶", text)
            self.assertNotIn("units/", text)


class DeckSlidevTests(unittest.TestCase):
    def setUp(self):
        self.outlines, _ = outline_storyboard(storyboard())
        self.notes = [f"備註{i}" for i in range(len(self.outlines))]
        self.slides = deck_slidev.render_slides(self.outlines, self.notes, "泡一壺茶")

    def test_one_slide_per_row_with_a_layout_from_the_default_theme(self):
        layouts = [line.split(": ")[1] for line in self.slides.splitlines() if line.startswith("layout: ")]
        self.assertEqual(layouts, ["cover", "section", "default", "default", "section", "default", "fact",
                                   "quote", "default"])

    def test_a_long_term_is_a_heading_not_a_fact(self):
        # `fact` prints its heading several times the body size; a long term would fill the slide.
        def layout(term):
            outlines, _ = outline_storyboard(storyboard([("L-DEFN-EXAMPLE", "—", f"title: 名詞<br>term: {term}<br>"
                                                          "formal_definition: 第一泡前先用熱水燙過茶葉")]))
            return deck_slidev.slide_body(outlines[0])[0]
        self.assertEqual(layout("溫潤泡"), "fact")
        self.assertEqual(layout("溫潤泡 (rinsing the leaves)"), "default")

    def test_spectrum_markers_come_through_as_label_and_description(self):
        outlines, _ = outline_storyboard(storyboard([(
            "L-SPECTRUM-POLES", "—", "title: 水的軟硬<br>pole_left: 軟<br>pole_right: 硬<br>markers:<br>"
            "- [label: 自來水, pct: 80, desc: 需先靜置]<br>- [label: 山泉水, pct: 20, desc: 回甘快]")]))
        self.assertEqual([(it.head, it.body) for it in outlines[0].items],
                         [("山泉水", "回甘快"), ("自來水", "需先靜置")])

    def test_the_headmatter_names_the_talk_and_keeps_the_font_local(self):
        head = self.slides.split("---\n")[1]
        self.assertIn('title: "泡一壺茶"', head)
        self.assertIn("provider: none", head)
        self.assertIn("layout: cover", head)

    def test_a_step_row_reveals_its_list_by_clicks(self):
        cards = self.slides.split("# 三件器具")[1].split("\n---\n")[0]
        self.assertIn("<v-clicks>", cards)
        self.assertIn("- **壺｜茶壺**：留住溫度", cards)
        self.assertIn("> **裁決**　先備齊再燒水", cards.replace(self.outlines[2].closing_label, "裁決"))
        flow = self.slides.split("# 沖泡三步")[1].split("\n---\n")[0]
        self.assertNotIn("<v-clicks>", flow)
        self.assertIn("1. **溫壺**：先用熱水燙過", flow)

    def test_two_camps_sit_in_two_columns(self):
        vs = self.slides.split("# 熱泡還是冷泡")[1].split("\n---\n")[0]
        self.assertIn('<div class="grid grid-cols-2 gap-8">', vs)
        self.assertLess(vs.index("### 熱泡"), vs.index("### 冷泡"))

    def test_each_note_is_the_slide_s_trailing_comment(self):
        for i, chunk in enumerate(self.slides.split("\n---\nlayout: ")):
            self.assertTrue(chunk.rstrip().endswith(f"<!--\n備註{i}\n-->"), chunk[-60:])

    def test_a_note_cannot_end_its_own_comment(self):
        self.assertEqual(deck_slidev.note_comment("甲 --> 乙\n\n丙"), ["<!--", "甲 --＞ 乙\n\n丙", "-->"])
        self.assertEqual(deck_slidev.note_comment("  \n"), [])

    def test_slot_text_prints_as_the_characters_it_was_given(self):
        md = deck_slidev.md
        self.assertEqual(md("a*b_c"), r"a\*b\_c")
        self.assertEqual(md("<b> & {x}"), "&lt;b&gt; &amp; {x}")
        # Markdown decodes an entity before Vue compiles the slide, so `{{` needs v-pre
        self.assertEqual(md("{{x}}"), "<span v-pre>{{</span>x}}")
        self.assertEqual(md("$5 [@k] `c`"), r"\$5 \[@k\] \`c\`")
        self.assertEqual(md("1. 第一"), r"1\. 第一")          # not an ordered list
        self.assertEqual(md("--- 分隔"), r"\-\-\- 分隔")      # not a slide break, not a dash
        self.assertEqual(md("A -- B ... (c) +-1"), r"A -\- B .\.\. \(c) +\-1")   # typographer left off
        self.assertEqual(md("兩行\n  文字"), "兩行 文字")

    def test_the_project_installs_without_a_build_script_prompt(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        talk = Path(tmp.name)
        (talk / "asset").mkdir()
        (talk / "asset" / "ENSFont.woff2").write_bytes(b"font")
        out = deck_slidev.write_view(talk, self.slides)
        self.assertEqual(sorted(p.name for p in out.iterdir()),
                         [".gitignore", "package.json", "pnpm-workspace.yaml", "public", "slides.md", "styles"])
        self.assertEqual((out / "public" / "ENSFont.woff2").read_bytes(), b"font")
        self.assertIn("allowBuilds:", (out / "pnpm-workspace.yaml").read_text(encoding="utf-8"))
        package = json.loads((out / "package.json").read_text(encoding="utf-8"))
        self.assertIn("@slidev/cli", package["devDependencies"])
        self.assertIn("node_modules/", (out / ".gitignore").read_text(encoding="utf-8"))


class DerivedViewsAreNotProseTests(unittest.TestCase):
    def test_generated_views_and_installed_packages_are_not_checked_as_writing(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        unit = Path(tmp.name)
        talk = unit / "talks" / "demo"
        for path in ("storyboard.md", "slidev/slides.md", "slidev/node_modules/pkg/README.md", "deck3d/notes.md"):
            (talk / path).parent.mkdir(parents=True, exist_ok=True)
            (talk / path).write_text("# x\n", encoding="utf-8")
        found = [p.relative_to(unit.resolve()).as_posix() for p in prose_files(unit)]
        self.assertEqual(found, ["talks/demo/storyboard.md"])


if __name__ == "__main__":
    unittest.main()
