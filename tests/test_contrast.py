"""Deck theme rules: shipped themes pass, bad pairs fail, Python and JS agree."""

import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_contrast", REPO / "scripts/check-contrast.py")
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)
spec = importlib.util.spec_from_file_location("unit_init", REPO / "scripts/unit-init.py")
unit_init = importlib.util.module_from_spec(spec)
spec.loader.exec_module(unit_init)

RULES = cc.load_rules()
TOKENS = (REPO / ".agents/skills/house-style/assets/css/tokens.css").read_text(encoding="utf-8")
DECK_CSS = (REPO / ".agents/skills/deck-svg/template/asset/deck.css").read_text(encoding="utf-8")
NODE = shutil.which("node")
SEEDS = (1, 7, 42, 4821, 9999)


def node_json(script: str):
    """Run the deck's own JS (rules + palette) under node and parse its JSON output."""
    prelude = (f"global.window={{}};require({json.dumps(str(cc.RULES))});"
               f"const P=require({json.dumps(str(cc.PALETTE))});const R=window.deckThemeRules;")
    out = subprocess.run([NODE, "-e", prelude + script], capture_output=True, text=True, timeout=120, check=True)
    return json.loads(out.stdout)


class ThemeRuleTests(unittest.TestCase):
    def test_every_shipped_theme_passes(self):
        ids, themes = cc.parse_themes(TOKENS)
        self.assertGreaterEqual(len(ids), 12)
        self.assertEqual(sorted(ids), sorted(themes))
        light = 0
        for tid in ids:
            with self.subTest(theme=tid):
                result = cc.check(themes[tid], RULES)
                self.assertEqual(result["fails"], [])
                light += result["light"]
        self.assertTrue(len(ids) // 2 - 1 <= light <= len(ids) // 2 + 1, "roughly half the themes are light")

    def test_default_theme_is_unchanged(self):
        # Existing decks must look the same: theme 1 keeps the pre-theme :root values.
        _, themes = cc.parse_themes(TOKENS)
        night = themes["night"]
        for token, value in {"ink": "#06080f", "ink-2": "#0c1019", "ink-3": "#141a28", "text": "#f3f5fa",
                             "body": "#c5ccdb", "muted": "#8b93a7", "c1": "#e7ad46", "c2": "#2dd4bf",
                             "c3": "#34d399", "c4": "#5b9dff", "accent": "#e7ad46"}.items():
            self.assertEqual(night[token], value)

    def test_known_bad_pairs_fail(self):
        _, themes = cc.parse_themes(TOKENS)
        grey = dict(themes["paper"], body="#8a8a8a")
        self.assertTrue(any(f.startswith("body/ink ") for f in cc.check(grey, RULES)["fails"]))
        twins = dict(themes["paper"], c2=themes["paper"]["c1"])
        self.assertTrue(any("c1/c2 ΔE00" in f for f in cc.check(twins, RULES)["fails"]))
        partial = {k: v for k, v in themes["paper"].items() if k != "muted"}
        self.assertEqual(cc.check(partial, RULES)["fails"], ["missing tokens: --muted"])

    def test_deck_css_uses_only_theme_tokens(self):
        # Every colour deck.css reads must be a token each theme defines, or a
        # theme switch would leave that colour on the default.
        used = set(re.findall(r"var\(--([\w-]+)", DECK_CSS))
        structural = {"chapter", "font", "ease", "deck-font-scale"}
        self.assertEqual(used - structural - set(RULES["tokens"]) - set(RULES["otherTokens"]), set())

    def test_new_assets_are_scaffolded(self):
        files = unit_init.presentation_files("thesis")
        for name in ("asset/deck-theme-controls.js", "asset/deck-theme-rules.js", "asset/deck-palette.js"):
            self.assertIn(name, files)
            self.assertTrue(files[name].is_file(), files[name])


@unittest.skipUnless(NODE, "node is not on PATH: skipping the Python/JS cross-check of deck-palette.js")
class CrossCheckTests(unittest.TestCase):
    def assert_same(self, py, js, where):
        self.assertEqual(py["ok"], js["ok"], where)
        self.assertEqual([f.split(" ")[0] for f in py["fails"]], [f.split(" ")[0] for f in js["fails"]], where)
        self.assertEqual(sorted(py["worst"]), sorted(js["worst"]), where)
        for key, (value, label) in py["worst"].items():
            self.assertAlmostEqual(value, js["worst"][key][0], places=9, msg=f"{where} {key}")
            self.assertEqual(label, js["worst"][key][1], f"{where} {key}")

    def test_fixed_themes_agree(self):
        _, themes = cc.parse_themes(TOKENS)
        js = node_json(f"const T={json.dumps(themes)};const o={{}};"
                       "for(const k in T)o[k]=P.check(T[k],R);console.log(JSON.stringify(o));")
        for tid, decls in themes.items():
            self.assert_same(cc.check(decls, RULES), js[tid], tid)

    def test_generated_palettes_pass_both_and_are_deterministic(self):
        js = node_json(f"const o={{}};for(const s of {list(SEEDS)}){{const a=P.generate(s,R),b=P.generate(s,R);"
                       "o[s]={tokens:a&&a.tokens,same:JSON.stringify(a)===JSON.stringify(b),"
                       "check:a&&P.check(a.tokens,R)};}console.log(JSON.stringify(o));")
        for seed in SEEDS:
            with self.subTest(seed=seed):
                got = js[str(seed)]
                self.assertTrue(got["tokens"], "generator gave up")
                self.assertTrue(got["same"], "same seed, different palette")
                self.assert_same(cc.check(got["tokens"], RULES), got["check"], f"r{seed}")
                self.assertTrue(got["check"]["ok"])


if __name__ == "__main__":
    unittest.main()
