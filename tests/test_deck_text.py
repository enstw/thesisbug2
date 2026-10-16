"""deck-text: the comprehension test's reader sees only what the audience sees."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("deck_text", REPO / "scripts" / "deck-text.py")
deck_text = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(deck_text)

DECK = """<!DOCTYPE html><html><body>
<deck-stage width="1920" height="1080">
  <section class="slide hero" data-label="封面">
    <div class="hero__layers" aria-hidden="true"><span>背景裝飾字</span></div>
    <h1 class="rise">主標</h1>
    <p class="hero__sub">副標　一</p>
    <span class="hero__hint"><kbd>→</kbd> 換頁</span>
  </section>
  <section class="slide" data-label="不該外洩的標籤">
    <div class="topbar"><span class="eyebrow">一、章名</span><span class="chap"><b>小標</b></span></div>
    <h2 class="title" data-beat="0">某甲指控某乙<br>把請求轉給某丙</h2>
    <div class="card"><span class="tag">標籤</span><h3>卡片標題</h3></div>
    <svg class="art dg"><defs><marker><path d="M0 0"/></marker></defs>
      <rect x="0" y="0" width="10" height="10"/><text x="1" y="1">圖中文字</text></svg>
    <table class="cmp"><tr><th>欄一</th><th>欄二</th></tr><tr><td>甲</td><td>乙</td></tr></table>
    <style>.x{color:red}</style><script>var hidden = 1;</script>
  </section>
  <section class="slide" data-label="空白"></section>
</deck-stage>
<script type="application/json" id="speaker-notes">["備註不該出現","備註二","備註三"]</script>
</body></html>"""


class DeckTextTests(unittest.TestCase):
    def setUp(self):
        self.texts = deck_text.slide_texts(DECK)

    def test_one_entry_per_slide(self):
        self.assertEqual(len(self.texts), 3)

    def test_visible_text_kept_in_reading_order(self):
        self.assertEqual(self.texts[0], "主標\n副標　一")
        lines = self.texts[1].split("\n")
        self.assertEqual(lines[:5], ["一、章名", "小標", "某甲指控某乙", "把請求轉給某丙", "標籤"])
        self.assertIn("圖中文字", lines)
        self.assertIn("｜ 欄一 ｜ 欄二", lines)

    def test_hidden_and_author_only_text_left_out(self):
        joined = "\n".join(self.texts)
        for leaked in ("背景裝飾字", "換頁", "不該外洩的標籤", "備註", "color:red", "hidden = 1"):
            self.assertNotIn(leaked, joined)

    def test_empty_slide_is_marked(self):
        self.assertIn("## 第 2 張\n\n（沒有文字）", deck_text.render("deck.html", self.texts))

    def test_command_writes_file_for_a_talk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "units").mkdir()
            env = dict(os.environ, FW_COURSE_ROOT=str(root))
            r = subprocess.run([sys.executable, str(REPO / "scripts" / "unit-init.py"), "--title", "T",
                                "--author", "A", "--type", "presentation", "--variant", "reading-guide",
                                "--name", "talk"], cwd=root, env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr)
            unit = next((root / "units").glob("*-talk"))
            out = root / "deck-text.md"
            r = subprocess.run([sys.executable, str(REPO / "scripts" / "deck-text.py"), "talk", "--out", str(out)],
                               cwd=root, env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr)
            md = out.read_text(encoding="utf-8")
            sections = (unit / "deck.html").read_text(encoding="utf-8").count('<section class="slide')
            self.assertEqual(md.count("\n## 第 "), sections)
            self.assertNotIn("speaker-notes", md)


if __name__ == "__main__":
    unittest.main()
