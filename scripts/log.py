#!/usr/bin/env python3
"""Record one milestone line in the unit's CHANGELOG.md.

    ./fw log [<unit>] "ch5 初稿完成，6,900 字"

The cheap, correct place for "what just got done" — so it does not get written
into PROGRESS.md instead, where every later session would pay to read it.
One line per milestone; the full story of a change belongs in its commit message.
Same as `./fw check-progress --log`, under the name an agent will guess.
"""
import subprocess
import sys
from pathlib import Path

args = sys.argv[1:]
if not args or args[0] in ("-h", "--help"):
    sys.exit(__doc__.strip())
unit, text = (args[:1], args[1]) if len(args) > 1 else ([], args[0])
sys.exit(subprocess.run([sys.executable, str(Path(__file__).with_name("check-progress.py")),
                         *unit, "--log", text]).returncode)
