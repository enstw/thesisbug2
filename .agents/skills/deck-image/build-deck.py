#!/usr/bin/env python3
"""build-deck.py — assemble an image-based <deck-stage> HTML deck.

Reads a manifest JSON describing the deck, copies the shared deck runtime
(deck-stage.js + presenter-stage.js, sourced from the sibling deck-runtime
skill) into the deck's asset folder, and writes a self-contained HTML file
where each slide is one full-bleed PNG. This is the assembly half of
/deck-image; the PNGs come from a per-slide renderer (/genimage-img2,
/genimage-nb, /genimage-canvas) and this script never cares which.

Usage:
    build-deck.py <manifest.json> [--assets <dir>] [--base <dir>]

Manifest schema (keys with defaults are optional):
    {
      "title":       "Deck title",                 # <title> + first <h-less>
      "description": "meta description",           # <meta name=description>
      "lang":        "zh-Hant",                    # <html lang>
      "width":       1920,                          # deck-stage design width
      "height":      1080,                          # deck-stage design height
      "slides_dir":  "generated-slides",           # where the PNGs live (rel to base)
      "asset_dir":   "asset",                       # where JS is copied (rel to base)
      "out":         "deck.html",                   # output file (rel to base)
      "hint":        true,                          # show the →/P hint on slide 1
      "slides": [
        {"file": "01-title.png",
         "label": "標題",          # thumbnail-rail / presenter label
         "alt":   "alt text",       # <img alt>, also presenter fallback label
         "notes": "speaker notes"}  # presenter window notes (press P)
      ]
    }

Stdlib only — no pip/uv needed.
"""
import argparse
import html
import json
import shutil
import sys
from pathlib import Path

PAGE = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title}</title>
<meta name="description" content="{description}" />
<style>
  /* deck-stage 在掛載前隱藏，避免第一張投影片以原始樣式閃現 */
  deck-stage:not(:defined) {{ visibility: hidden; }}

  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; background: #000; }}

  /* 每張投影片就是一張 16:9 的成品圖，鋪滿 {width}×{height} 畫布 */
  .imgslide {{ padding: 0; background: #000; }}
  .imgslide img {{
    width: 100%; height: 100%;
    object-fit: cover; display: block;
    user-select: none; -webkit-user-drag: none;
  }}

  /* 第一頁右下角的操作提示（疊在圖上，列印時隱藏） */
  .hint {{
    position: absolute; right: 36px; bottom: 28px; z-index: 2;
    color: rgba(243,245,250,.75); font-size: 22px; letter-spacing: .04em;
    font-family: "PingFang TC", "Noto Sans CJK TC", system-ui, sans-serif;
    text-shadow: 0 1px 8px rgba(0,0,0,.9);
  }}
  .hint kbd {{
    display: inline-block; padding: 3px 12px; margin: 0 4px;
    border: 1px solid rgba(255,255,255,.25); border-radius: 7px;
    background: rgba(12,16,25,.85); color: #f3f5fa; font-size: 20px;
    font-family: inherit;
  }}
  @media print {{ .hint {{ display: none; }} }}
</style>
</head>
<body>

<deck-stage width="{width}" height="{height}">

{sections}
</deck-stage>

<script type="application/json" id="speaker-notes">
{notes}
</script>

<script src="{asset_dir}/deck-stage.js"></script>
<script src="{asset_dir}/presenter-stage.js"></script>
</body>
</html>
"""

SECTION = """  <section class="imgslide" data-label="{label}">
    <img src="{src}" alt="{alt}" />{hint}
  </section>
"""

HINT = '\n    <span class="hint"><kbd>→</kbd> 換頁　<kbd>P</kbd> 講者視窗</span>'


def attr(s: str) -> str:
    """Escape a string for use inside a double-quoted HTML attribute."""
    return html.escape(str(s), quote=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Assemble an image-based deck-stage HTML deck.")
    ap.add_argument("manifest", help="path to the manifest JSON")
    ap.add_argument("--assets", help="dir holding deck-stage.js + presenter-stage.js "
                                     "(default: the sibling deck-runtime skill's "
                                     "template/asset dir)")
    ap.add_argument("--base", help="base dir for relative paths in the manifest "
                                   "(default: the manifest's own directory)")
    args = ap.parse_args()

    man_path = Path(args.manifest).expanduser().resolve()
    if not man_path.is_file():
        print(f"ERROR: manifest not found: {man_path}", file=sys.stderr)
        return 1
    man = json.loads(man_path.read_text(encoding="utf-8"))

    base = Path(args.base).expanduser().resolve() if args.base else man_path.parent
    # Runtime JS is owned by the sibling deck-runtime skill (single source of
    # truth, shared with deck-svg) rather than bundled here.
    default_assets = (Path(__file__).resolve().parent.parent
                      / "deck-runtime" / "template" / "asset")
    assets_dir = (Path(args.assets).expanduser().resolve()
                  if args.assets else default_assets)

    lang = man.get("lang", "zh-Hant")
    title = man.get("title", "Image Deck")
    description = man.get("description", title)
    width = int(man.get("width", 1920))
    height = int(man.get("height", 1080))
    slides_dir = man.get("slides_dir", "generated-slides")
    asset_dir = man.get("asset_dir", "asset")
    out = man.get("out", "deck.html")
    show_hint = man.get("hint", True)
    slides = man.get("slides", [])
    if not slides:
        print("ERROR: manifest has no 'slides'", file=sys.stderr)
        return 1

    # 1) copy the shared deck-runtime into the deck's asset folder
    dest_assets = base / asset_dir
    dest_assets.mkdir(parents=True, exist_ok=True)
    missing = []
    for js in ("deck-stage.js", "presenter-stage.js"):
        src = assets_dir / js
        if not src.is_file():
            missing.append(str(src))
            continue
        shutil.copyfile(src, dest_assets / js)
    if missing:
        print("ERROR: deck-runtime asset(s) not found (is the sibling "
              "deck-runtime skill present?):\n  " + "\n  ".join(missing),
              file=sys.stderr)
        return 1

    # 2) build sections + collect notes, warn on any missing image
    sections, notes, warnings = [], [], []
    for i, s in enumerate(slides):
        fname = s["file"]
        src_rel = f"{slides_dir}/{fname}"
        if not (base / src_rel).is_file():
            warnings.append(src_rel)
        label = s.get("label", s.get("alt", f"Slide {i + 1}"))
        alt = s.get("alt", label)
        hint = HINT if (i == 0 and show_hint) else ""
        sections.append(SECTION.format(label=attr(label), src=attr(src_rel),
                                       alt=attr(alt), hint=hint))
        notes.append(s.get("notes", ""))

    notes_json = json.dumps(notes, ensure_ascii=False, indent=0)

    page = PAGE.format(
        lang=attr(lang), title=html.escape(title), description=attr(description),
        width=width, height=height, asset_dir=attr(asset_dir),
        sections="\n".join(sections), notes=notes_json,
    )

    out_path = base / out
    out_path.write_text(page, encoding="utf-8")

    print(f"DECK_OK {out_path}")
    print(f"  slides: {len(slides)}  assets: {dest_assets}")
    if warnings:
        print("  WARNING: missing image file(s) referenced by the deck:", file=sys.stderr)
        for w in warnings:
            print(f"    {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
