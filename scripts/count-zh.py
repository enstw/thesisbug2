#!/usr/bin/env python3
"""Count Chinese characters in a text file, excluding punctuation and English."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def count_zh_chars(text: str) -> int:
    """Count CJK Unified Ideographs only."""
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def main():
    parser = argparse.ArgumentParser(
        description="Count Chinese characters, excluding punctuation and English letters"
    )
    parser.add_argument("file", help="Path to the file to count")
    args = parser.parse_args()

    try:
        content = Path(args.file).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error reading file {args.file}: {exc}", file=sys.stderr)
        sys.exit(1)

    print(count_zh_chars(content))


if __name__ == "__main__":
    main()
