"""deck-refresh: framework-owned deck assets are re-copied; author files are not."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("_deck", REPO / "scripts/_deck.py")
deck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deck)
PALETTE_TAG = '<script src="asset/deck-palette.js"></script>'
AUTHOR_FILES = ("deck.html", "storyboard.md", "points.md", "draft.qmd", "presentation.qmd")


class DeckRefreshTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "units").mkdir()
        self.env = dict(os.environ, FW_COURSE_ROOT=str(self.root))

    def run_fw(self, script, *args):
        return subprocess.run([sys.executable, str(REPO / "scripts" / script), *args], cwd=self.root,
                              env=self.env, capture_output=True, text=True, timeout=120)

    def scaffold(self, *args):
        r = self.run_fw("unit-init.py", "--title", "T", "--author", "A", *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return next((self.root / "units").glob(f"*-{args[args.index('--name') + 1]}"))

    def test_refresh_adds_updates_and_leaves_author_files(self):
        unit = self.scaffold("--type", "presentation", "--variant", "thesis", "--name", "talk")
        (unit / "asset/deck-palette.js").unlink()
        (unit / "asset/deck.css").write_text("/* stale */\n", encoding="utf-8")
        html = unit / "deck.html"
        html.write_text(html.read_text(encoding="utf-8").replace(PALETTE_TAG + "\n", "")
                        .replace("<html lang=\"zh-Hant\">", "<html lang=\"zh-Hant\" data-deck-theme-default=\"paper\">"),
                        encoding="utf-8")
        (unit / "notes/mine.md").write_text("author note\n", encoding="utf-8")
        before = {name: (unit / name).read_bytes() for name in (*AUTHOR_FILES, "notes/mine.md")}

        dry = self.run_fw("deck-refresh.py", "talk", "--dry-run")
        self.assertIn("new        asset/deck-palette.js", dry.stdout)
        self.assertFalse((unit / "asset/deck-palette.js").exists(), "--dry-run must not write")

        r = self.run_fw("deck-refresh.py", "talk")
        self.assertEqual(r.returncode, 1, "a missing tag is a finding")
        self.assertIn("new        asset/deck-palette.js", r.stdout)
        self.assertIn("updated    asset/deck.css", r.stdout)
        self.assertIn("unchanged  asset/deck-stage.js", r.stdout)
        self.assertIn(f"  {PALETTE_TAG}\n      after <script src=\"asset/deck-theme-rules.js\"></script>", r.stdout)
        for dst, src in deck.deck_assets().items():
            self.assertEqual((unit / dst).read_bytes(), src.read_bytes(), dst)
        for name, content in before.items():
            self.assertEqual((unit / name).read_bytes(), content, f"{name} is the author's")

        html.write_text(html.read_text(encoding="utf-8").replace(
            '<script src="asset/deck-theme-rules.js"></script>',
            '<script src="asset/deck-theme-rules.js"></script>\n' + PALETTE_TAG), encoding="utf-8")
        again = self.run_fw("deck-refresh.py", "talk")
        self.assertEqual(again.returncode, 0, again.stdout)
        self.assertNotIn("new ", again.stdout)
        self.assertNotIn("updated ", again.stdout)

    def test_uncommitted_asset_edit_is_skipped(self):
        unit = self.scaffold("--type", "presentation", "--variant", "reading-guide", "--name", "guide")
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-C", str(self.root)]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-qm", "init"], check=True)
        (unit / "asset/tokens.css").write_text("/* local, uncommitted */\n", encoding="utf-8")
        r = self.run_fw("deck-refresh.py", "guide")
        self.assertEqual(r.returncode, 1)
        self.assertIn("skipped    asset/tokens.css", r.stdout)
        self.assertEqual((unit / "asset/tokens.css").read_text(encoding="utf-8"), "/* local, uncommitted */\n")

    def test_refuses_a_non_presentation_unit(self):
        self.scaffold("--type", "homework", "--name", "hw", "--no-build")
        r = self.run_fw("deck-refresh.py", "hw")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not a talk", r.stderr)
        self.assertFalse(any((self.root / "units").glob("*-hw/asset")))

    def test_starters_load_every_asset_tag(self):
        for variant in ("thesis", "reading-guide"):
            with self.subTest(variant=variant):
                html = deck.starter_deck(variant).read_text(encoding="utf-8")
                self.assertEqual(deck.missing_tags(html, variant), [])
                self.assertIn("data-deck-theme-default", html, "starter shows the per-deck default theme")


if __name__ == "__main__":
    unittest.main()
