"""refs-snapshot: help never runs a subcommand; push keeps rows it cannot see locally."""

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "refs-snapshot.sh"

# A stand-in for gh: the release exists, uploads succeed, and every call is
# logged so a test can tell whether anything reached the network.
FAKE_GH = """#!/usr/bin/env bash
echo "$*" >> "$GH_LOG"
exit 0
"""


def row(rel, data, tag="refs"):
    return f"{rel}\t{hashlib.sha256(data).hexdigest()}\t{len(data)}\t{tag}\n"


class RefsSnapshotTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "course"
        (self.root / "library" / "refs").mkdir(parents=True)
        (self.root / "units" / "01-talk" / "refs").mkdir(parents=True)
        bindir = Path(tmp.name) / "bin"
        bindir.mkdir()
        gh = bindir / "gh"
        gh.write_text(FAKE_GH, encoding="utf-8")
        gh.chmod(0o755)
        self.log = Path(tmp.name) / "gh.log"
        self.env = dict(os.environ, FW_COURSE_ROOT=str(self.root), GH_LOG=str(self.log),
                        PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}")
        self.manifest = self.root / "library" / "refs" / "MANIFEST.tsv"

    def run_snapshot(self, *args):
        return subprocess.run(["bash", str(SCRIPT), *args], cwd=self.root, env=self.env,
                              capture_output=True, text=True, timeout=60)

    def gh_calls(self):
        return self.log.read_text(encoding="utf-8") if self.log.exists() else ""

    def write_manifest(self, *rows):
        self.manifest.write_text("# header\n# managed\n# path\tsha256\tbytes\trelease\n" + "".join(rows),
                                 encoding="utf-8")

    def manifest_paths(self):
        return [line.split("\t")[0] for line in self.manifest.read_text(encoding="utf-8").splitlines()
                if line and not line.startswith("#")]

    def test_help_after_a_subcommand_prints_usage_and_uploads_nothing(self):
        (self.root / "units/01-talk/refs/new2026.pdf").write_bytes(b"new")
        for args in (("push", "--help"), ("push", "-h"), ("pull", "--help"), ("--help",), ("help",)):
            r = self.run_snapshot(*args)
            self.assertEqual(r.returncode, 0, (args, r.stderr))
            self.assertIn("refs-snapshot push", r.stdout)
        self.assertEqual(self.gh_calls(), "")
        self.assertFalse(self.manifest.exists())

    def test_push_rejects_arguments_without_uploading(self):
        (self.root / "units/01-talk/refs/new2026.pdf").write_bytes(b"new")
        r = self.run_snapshot("push", "--dry-run")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("push takes no arguments", r.stderr)
        self.assertNotIn("upload", self.gh_calls())

    def test_push_keeps_rows_whose_original_is_not_on_this_machine(self):
        self.write_manifest(row("library/refs/old2001.pdf", b"old"),
                            row("units/02-paper/refs/other2020.pdf", b"other"))
        (self.root / "units/01-talk/refs/new2026.pdf").write_bytes(b"new")
        r = self.run_snapshot("push")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 uploaded", r.stdout)
        self.assertIn("2 kept", r.stdout)
        self.assertEqual(self.manifest_paths(), ["library/refs/old2001.pdf",
                                                 "units/01-talk/refs/new2026.pdf",
                                                 "units/02-paper/refs/other2020.pdf"])
        self.assertIn(row("library/refs/old2001.pdf", b"old").strip(),
                      self.manifest.read_text(encoding="utf-8"))

    def test_forget_drops_only_the_named_row(self):
        self.write_manifest(row("library/refs/keep2001.pdf", b"keep"),
                            row("library/refs/drop2002.pdf", b"drop"))
        r = self.run_snapshot("forget", "library/refs/drop2002.pdf")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.manifest_paths(), ["library/refs/keep2001.pdf"])
        self.assertTrue(self.manifest.read_text(encoding="utf-8").startswith("# header"))
        self.assertEqual(self.gh_calls(), "")

    def test_forget_refuses_a_path_not_in_the_manifest(self):
        self.write_manifest(row("library/refs/keep2001.pdf", b"keep"))
        r = self.run_snapshot("forget", "library/refs/typo.pdf")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not in manifest", r.stderr)
        self.assertEqual(self.manifest_paths(), ["library/refs/keep2001.pdf"])


if __name__ == "__main__":
    unittest.main()
