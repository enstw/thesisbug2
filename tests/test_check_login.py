"""check-login reports whether a stored-credential login is usable, without leaking it."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
RECIPE = {"entry": "https://proxy.example.edu/login?url={url}", "user_key": "LIB_USER", "pass_key": "LIB_PASS",
          "user": "#u", "password": "#p", "submit": "#s", "success_url": "^https://x"}


class CheckLoginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="check-login-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sites = self.root / "sites"
        self.sites.mkdir()
        self.env = {**os.environ, "AUTHENTICATED_FETCH_SITES": str(self.sites)}

    def site(self, name, body, mode=0o600):
        cred = self.root / f"{name}-credentials"
        if body is not None:
            cred.write_text(body, encoding="utf-8")
            cred.chmod(mode)
        (self.sites / f"{name}.json").write_text(json.dumps({**RECIPE, "credentials": str(cred)}), encoding="utf-8")
        return cred

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(REPO / "scripts/fw"), "check-login", *args],
                              cwd=self.root, env=self.env, text=True, capture_output=True, timeout=20)

    def test_configured_site_is_ready_and_values_stay_private(self):
        self.site("lib", "# SECRET\nLIB_USER=someone\nLIB_PASS=hunter2-value\n")
        result = self.run_cli("lib", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["ready"])
        self.assertNotIn("hunter2-value", result.stdout + result.stderr)
        self.assertNotIn("someone", result.stdout + result.stderr)

    def test_unusable_credentials_are_not_ready(self):
        self.site("empty", "LIB_USER=\nLIB_PASS=\n")
        self.site("open", "LIB_USER=a\nLIB_PASS=b\n", mode=0o644)
        missing = self.site("missing", None)
        result = self.run_cli("--json")
        self.assertEqual(result.returncode, 1)
        reasons = {entry["site"]: entry["reason"] for entry in json.loads(result.stdout)["sites"]}
        self.assertIn("empty", reasons["empty"])
        self.assertIn("readable by other accounts", reasons["open"])
        self.assertIn("no credential file", reasons["missing"])
        self.assertFalse(missing.exists(), "the check must not create a credential template")

    def test_unknown_site_and_empty_directory(self):
        self.assertEqual(self.run_cli("nowhere").returncode, 1)
        self.assertEqual(self.run_cli().returncode, 1)
        self.site("lib", "LIB_USER=a\nLIB_PASS=b\n")
        self.assertEqual(self.run_cli().returncode, 0)
        self.assertEqual(self.run_cli("nowhere").returncode, 1)


if __name__ == "__main__":
    unittest.main()
