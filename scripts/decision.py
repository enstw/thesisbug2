#!/usr/bin/env python3
"""Query current decisions and preserve revisions: fw decision <unit> --help."""
from _workflow_cli import main

if __name__ == "__main__":
    raise SystemExit(main("decision"))
