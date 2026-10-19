"""storyboard-review renders a storyboard as one review page from the files that own each part."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]

STORYBOARD = """# 分鏡稿

<!-- 審閱說明第一行。 -->

## 前提

- 標題：主標「測試」
- 流程步驟：S1 讀取、S2 特徵、S3 模型、保留（圖：@fig-flow）
- 流程對照：notes/map.md § 矩陣｜第 3 週

## 待選

<!-- 每題一個上層條列，選項縮排。 -->

- **#0 標題**（建議 B：比較短）
  - A 長的標題
  - B 短標題

## 投影片

| # | 來源論點 | 環節 | 內容形狀 | 版型 | 講 | 畫面內容 | 公式 | 口說重點 | AI 協助 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0 | P1 | — | 14 封面 | L-HERO-TITLE | 20 秒 | title: 測試簡報<br>sub: 副標 | — | 開場 | — |
| 1 | P1 | 改：S3；講：保留 | 11 數字 | `.stats.four` | 30 秒 | 程式 `p ** 2` 與 **粗體** | $\\lambda F_i$ | 講重點 | AI 起草 |
"""


class StoryboardReviewTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.unit = self.root / "units/03-homework-x"
        (self.unit).mkdir(parents=True)
        (self.root / "notes").mkdir()
        (self.unit / "WORK.json").write_text(json.dumps({"type": "homework", "title": "X"}), encoding="utf-8")
        (self.unit / "homework.qmd").write_text(
            "# 報告\n\n```{mermaid}\n%%| label: fig-flow\n%%| fig-cap: \"骨架\"\nflowchart LR\n  A --> B\n```\n",
            encoding="utf-8")
        (self.unit / "points.md").write_text("- **P1** 第一點\n- **P2** 沒人引用\n", encoding="utf-8")
        (self.unit / "storyboard.md").write_text(STORYBOARD, encoding="utf-8")
        (self.root / "notes/map.md").write_text(
            "## 矩陣\n\n| 步驟 | 第 2 週教材 | 第 3 週教材 | 第 3 週最佳化 |\n|---|---|---|---|\n"
            "| S1 | a | b | **c** |\n", encoding="utf-8")
        self.env = dict(os.environ, FW_COURSE_ROOT=str(self.root))

    def run_review(self, *args):
        return subprocess.run([sys.executable, str(REPO / "scripts/storyboard-review.py"), *args],
                              cwd=self.root, env=self.env, capture_output=True, text=True, timeout=120)

    def page(self):
        return (self.unit / "_output/storyboard.html").read_text(encoding="utf-8")

    def test_every_part_lands_on_one_page(self):
        r = self.run_review("units/03-homework-x")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("2 slides", r.stdout)
        html = self.page()
        self.assertIn("審閱說明第一行", html)
        self.assertEqual(html.count('class="card'), 2)
        # A catalog code previews the real compiled slide; a legacy class gets a sketch.
        self.assertEqual(html.count("<iframe"), 1)
        self.assertIn("測試簡報", html)
        self.assertIn('<svg viewBox="0 0 192 108">', html)
        # The 環節 column drives the strip and the slide × step table.
        self.assertIn('<td class="chg">改</td>', html)
        self.assertIn('<td class="say">講</td>', html)
        self.assertIn("flowchart LR", html, "the Model diagram named in 流程步驟 is embedded")
        self.assertIn("第 3 週最佳化", html)
        self.assertNotIn("第 2 週教材", html, "the crosswalk keeps only the named columns")
        # Formulas stay as $…$ for KaTeX; code keeps its ** (a power, not bold).
        self.assertIn("$\\lambda F_i$", html)
        self.assertIn("<code>p ** 2</code>", html)
        self.assertIn("p ** 2 與 粗體", html)
        # 〈待選〉 becomes radios with the recommended option checked.
        self.assertIn('value="B" checked', html)
        self.assertIn('data-q="#0 標題"', html)
        # Every point is listed; an uncited one is flagged.
        self.assertIn('class="point unused"><b>P2</b>', html)

    def test_optional_parts_are_omitted_when_not_declared(self):
        text = STORYBOARD.split("## 待選")[0].replace("- 流程步驟：S1 讀取、S2 特徵、S3 模型、保留（圖：@fig-flow）\n", "")
        text += "## 投影片\n" + STORYBOARD.split("## 投影片\n")[1]
        (self.unit / "storyboard.md").write_text(text, encoding="utf-8")
        r = self.run_review("units/03-homework-x")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        html = self.page()
        self.assertNotIn('id="map"', html)
        self.assertNotIn('id="choose"', html)
        self.assertNotIn("mermaid.min.js", html)

    def test_a_unit_without_storyboard_is_refused(self):
        (self.unit / "storyboard.md").unlink()
        r = self.run_review("units/03-homework-x")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no storyboard.md", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
