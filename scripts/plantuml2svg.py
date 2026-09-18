#!/usr/bin/env python3
"""
Render a PlantUML source file to SVG / PNG / PDF via Kroki (POST).

Usage:
    ./fw plantuml2svg input.plantuml output.svg
    ./fw plantuml2svg input.plantuml output.png --format png
    ./fw plantuml2svg input.plantuml --format svg           # prints URL only

Why Kroki: plantuml.com's public server has been returning HTTP 509
(bandwidth limit) for this IP; Kroki's POST endpoint is self-hosted,
rate-limit friendly, and accepts raw UTF-8 PlantUML in the request
body — no deflate/base64 dance needed.

Diagrams in this repo default to **SVG** for sharp rendering at any
zoom. Quarto PDF builds convert SVG through `rsvg-convert` automatically;
deck-stage HTML decks embed SVG directly. Falls back to PNG only if the SVG
toolchain is unavailable; PNG should specify --format png explicitly.
"""

import argparse
import sys
import urllib.request

SERVER = "https://kroki.io/plantuml"


def render_url(fmt: str) -> str:
    return f"{SERVER}/{fmt}"


def render(text: str, fmt: str) -> bytes:
    req = urllib.request.Request(
        render_url(fmt),
        data=text.encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "text/plain",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render PlantUML via Kroki (SVG/PNG/PDF).",
    )
    parser.add_argument("input", help="PlantUML source file (.plantuml / .puml)")
    parser.add_argument("output", nargs="?", help="Output file path")
    parser.add_argument(
        "--format",
        default="svg",
        choices=["svg", "png", "pdf"],
        help="Output format (default: svg — preferred for vector rendering)",
    )
    args = parser.parse_args()

    text = open(args.input, encoding="utf-8").read()

    if args.output:
        data = render(text, args.format)
        with open(args.output, "wb") as f:
            f.write(data)
        print(f"Wrote {args.format.upper()} to {args.output}")
    else:
        print(render_url(args.format))


if __name__ == "__main__":
    main()
