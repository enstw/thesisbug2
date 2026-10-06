#!/usr/bin/env python3
"""Check every deck theme in a tokens.css against the house-style colour rules.

    ./fw check-contrast                      the framework's house-style tokens.css
    ./fw check-contrast <talk>|<tokens.css>  a deck's own copy (<talk>/asset/tokens.css)
    ./fw check-contrast --emit r4821         print seed 4821's generated palette as a
                                             theme block to paste into tokens.css (needs node)

A theme is the :root block (theme 1) or a :root[data-deck-theme="<id>"] block;
--deck-themes lists the ids. The rules — text-on-surface pairs, WCAG and
lit-room thresholds per role, the colour-vision ΔE — are read from
house-style's deck-theme-rules.js, the same file the deck's deck-palette.js
reads, so the browser and this script cannot disagree about a threshold.
APCA Lc is reported, not gated. A theme that leaves a colour token undefined
fails too, because an inherited dark default inside a light theme is invisible
until it is projected. Exit status 1 when any theme fails. Standard library only.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

FRAMEWORK = Path(__file__).resolve().parent.parent
HOUSE = FRAMEWORK / ".agents" / "skills" / "house-style" / "assets"
DEFAULT_TOKENS = HOUSE / "css" / "tokens.css"
RULES = HOUSE / "themes" / "deck-theme-rules.js"
PALETTE = HOUSE / "themes" / "deck-palette.js"

Color = list   # [r, g, b] 0–255, then alpha 0–1


def load_rules(path: Path = RULES) -> dict:
    m = re.search(r"=\s*(\{.*\})\s*;\s*$", path.read_text(encoding="utf-8"), re.S)
    if not m:
        raise SystemExit(f"{path}: expected `window.deckThemeRules = {{…}};`")
    return json.loads(m.group(1))


# ---------------------------------------------------------------- parsing
def parse_color(value: str) -> Color:
    v = value.strip().lower()
    if v.startswith("#"):
        h = v[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) not in (6, 8):
            raise ValueError(value)
        return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16),
                int(h[6:8], 16) / 255 if len(h) == 8 else 1.0]
    m = re.fullmatch(r"rgba?\(([^)]*)\)", v)
    if m:
        p = [x for x in re.split(r"[\s,/]+", m.group(1).strip()) if x]
        rgb = [float(x[:-1]) * 2.55 if x.endswith("%") else float(x) for x in p[:3]]
        a = p[3] if len(p) > 3 else "1"
        return [*rgb, float(a[:-1]) / 100 if a.endswith("%") else float(a)]
    raise ValueError(f"unsupported colour (use #hex or rgb()/rgba()): {value}")


def parse_themes(css: str) -> tuple[list[str], dict[str, dict[str, str]]]:
    """→ (ids from --deck-themes, {id: {token: value}}); theme 1 is the :root block."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    blocks: dict[str, dict[str, str]] = {}
    for sel, body in re.findall(r"(:root(?:\[data-deck-theme=\"[\w-]+\"\])?)\s*\{([^}]*)\}", css):
        decls = {k: " ".join(v.split()) for k, v in re.findall(r"--([\w-]+)\s*:\s*([^;]+);", body)}
        m = re.search(r'"([\w-]+)"', sel)
        blocks[m.group(1) if m else ":root"] = decls
    root = blocks.pop(":root", {})
    ids = root.get("deck-themes", "").split()
    if ids:
        blocks[ids[0]] = root
    return ids, blocks


# ------------------------------------------- colour math (mirrors deck-palette.js)
def over(top: Color, bottom: Color) -> Color:
    a = top[3]
    return [top[i] * a + bottom[i] * (1 - a) for i in range(3)] + [1]


def _lin(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(c: Color) -> float:
    return 0.2126 * _lin(c[0]) + 0.7152 * _lin(c[1]) + 0.0722 * _lin(c[2])


def contrast(fg: Color, bg: Color, ambient: float = 0.0) -> float:
    a, b = luminance(fg) + 0.05 + ambient, luminance(bg) + 0.05 + ambient
    return max(a, b) / min(a, b)


def apca(fg: Color, bg: Color) -> float:
    """APCA-W3 0.0.98G-4g Lc (signed; positive = dark text on a light ground)."""
    def y(c: Color) -> float:
        v = 0.2126729 * (c[0] / 255) ** 2.4 + 0.7151522 * (c[1] / 255) ** 2.4 + 0.0721750 * (c[2] / 255) ** 2.4
        return v if v > 0.022 else v + (0.022 - v) ** 1.414
    yt, yb = y(fg), y(bg)
    if abs(yb - yt) < 0.0005:
        return 0.0
    if yb > yt:
        s = (yb ** 0.56 - yt ** 0.57) * 1.14
        return 0.0 if s < 0.1 else (s - 0.027) * 100
    s = (yb ** 0.65 - yt ** 0.62) * 1.14
    return 0.0 if s > -0.1 else (s + 0.027) * 100


MACHADO = {   # Machado, Oliveira & Fernandes (2009), severity 1.0, linear RGB
    "deutan": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "protan": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
}


def lab(c: Color, vision: str = "normal") -> tuple[float, float, float]:
    rgb = [_lin(x) for x in c[:3]]
    if vision in MACHADO:
        rgb = [min(1.0, max(0.0, row[0] * rgb[0] + row[1] * rgb[1] + row[2] * rgb[2])) for row in MACHADO[vision]]
    r, g, b = rgb
    xyz = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b,
           0.2126729 * r + 0.7151522 * g + 0.0721750 * b,
           0.0193339 * r + 0.1191920 * g + 0.9503041 * b)
    def f(t: float) -> float:
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116
    fx, fy, fz = f(xyz[0] / 0.95047), f(xyz[1] / 1.0), f(xyz[2] / 1.08883)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def ciede2000(p, q) -> float:
    (l1, a1, b1), (l2, a2, b2) = p, q
    cb = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = 0.5 * (1 - math.sqrt(cb ** 7 / (cb ** 7 + 25 ** 7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p, h2p = math.degrees(math.atan2(b1, a1p)) % 360, math.degrees(math.atan2(b2, a2p)) % 360
    dl, dc = l2 - l1, c2p - c1p
    dh = 0.0 if c1p * c2p == 0 else (h2p - h1p + 180) % 360 - 180
    dhh = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dh / 2))
    lbp, cbp = (l1 + l2) / 2, (c1p + c2p) / 2
    if c1p * c2p == 0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbp = (h1p + h2p) / 2
    else:
        hbp = (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2
    t = (1 - 0.17 * math.cos(math.radians(hbp - 30)) + 0.24 * math.cos(math.radians(2 * hbp))
         + 0.32 * math.cos(math.radians(3 * hbp + 6)) - 0.20 * math.cos(math.radians(4 * hbp - 63)))
    dth = 30 * math.exp(-(((hbp - 275) / 25) ** 2))
    rc = 2 * math.sqrt(cbp ** 7 / (cbp ** 7 + 25 ** 7))
    sl = 1 + 0.015 * (lbp - 50) ** 2 / math.sqrt(20 + (lbp - 50) ** 2)
    sc, sh = 1 + 0.045 * cbp, 1 + 0.015 * cbp * t
    rt = -math.sin(math.radians(2 * dth)) * rc
    return math.sqrt((dl / sl) ** 2 + (dc / sc) ** 2 + (dhh / sh) ** 2 + rt * (dc / sc) * (dhh / sh))


# ---------------------------------------------------- what deck.css draws
def surface(name: str, t: dict, surfaces: dict, depth: int = 0) -> Color:
    if depth > 8:
        raise ValueError(f"surface loop at {name}")
    base = None
    for layer in surfaces[name]:
        if layer != name and layer in surfaces:
            col = surface(layer, t, surfaces, depth + 1)
        else:
            tok, _, share = layer.partition("@")
            col = list(t[tok])
            if share:
                col[3] *= float(share)
        base = over(col, base) if base else (over(col, [255, 255, 255, 1]) if col[3] < 1 else col)
    return base


def pairs(t: dict, rules: dict) -> list[tuple[str, str, Color, Color]]:
    """(role, label, text colour, ground) for every pair the rules list, C expanded per chapter."""
    def subber(c):
        return (lambda n: n.replace("C", c)) if c else (lambda n: n)
    surfaces = {}
    for name, layers in rules["surfaces"].items():
        if name != "why":
            for c in rules["chapters"] if "C" in name else [None]:
                sub = subber(c)
                surfaces[sub(name)] = [sub(x) for x in layers]
    out, seen = [], set()
    for p in rules["pairs"]:
        uses_c = any("C" in x for x in p["text"] + p["on"])
        for c in rules["chapters"] if uses_c else [None]:
            sub = subber(c)
            for fg in dict.fromkeys(map(sub, p["text"])):
                for g in dict.fromkeys(map(sub, p["on"])):
                    label = f"{fg}/{g}"
                    if label not in seen:
                        seen.add(label)
                        out.append((p["role"], label, t[fg], surface(g, t, surfaces)))
    return out


def check(decls: dict[str, str], rules: dict) -> dict:
    """Same result shape as deckPalette.check: ok, fails, worst {key: [value, label]}, light."""
    missing = [k for k in rules["tokens"] + rules["otherTokens"] if k not in decls]
    if missing:
        return {"ok": False, "fails": ["missing tokens: " + ", ".join("--" + k for k in missing)], "worst": {}}
    t = {k: parse_color(decls[k]) for k in rules["tokens"]}
    fails, worst = [], {}

    def keep(key, value, label):
        if key not in worst or value < worst[key][0]:
            worst[key] = [value, label]

    for role, label, fg, bg in pairs(t, rules):
        if fg[3] < 1:
            fg = over(fg, bg)
        r = rules["roles"][role]
        for kind, ratio, floor in (("wcag", contrast(fg, bg), r["wcag"]),
                                   ("lit", contrast(fg, bg, rules["ambient"]["luminance"]), r["ambient"])):
            keep(f"{kind}-{role}", ratio, label)
            if ratio < floor:
                fails.append(f"{label} {kind} {ratio:.2f} < {floor}")
        if role == "body":
            keep("apca", abs(apca(fg, bg)), label)
    ch = rules["chapters"]
    for vision in rules["cvd"]["visions"]:
        for i in range(len(ch)):
            for j in range(i + 1, len(ch)):
                d = ciede2000(lab(t[ch[i]], vision), lab(t[ch[j]], vision))
                keep("de", d, f"{ch[i]}/{ch[j]} {vision}")
                if d < rules["cvd"]["deltaE00"]:
                    fails.append(f"{ch[i]}/{ch[j]} ΔE00 {d:.1f} < {rules['cvd']['deltaE00']} ({vision})")
    return {"ok": not fails, "fails": fails, "worst": worst, "light": luminance(t["ink"]) > 0.5}


# ------------------------------------------------------------------ CLI
def emit(seed_arg: str) -> int:
    """Generated palettes come from the deck's own JS, so the block is exactly what was on screen."""
    seed = int(seed_arg.lstrip("r"))
    node = shutil.which("node")
    if not node:
        print("node is not on PATH; open the deck with the palette active at deck.html#debug "
              "and copy the theme block the console prints instead", file=sys.stderr)
        return 2
    js = (f"global.window={{}};require({json.dumps(str(RULES))});"
          f"const p=require({json.dumps(str(PALETTE))});const r=window.deckThemeRules;"
          f"const g=p.generate({seed},r);if(!g)process.exit(1);"
          f"console.log(p.css('r{seed}',g.tokens,r));")
    res = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=60)
    if res.returncode:
        print(res.stderr or f"seed {seed} produced no passing palette", file=sys.stderr)
        return 1
    block = res.stdout.strip()
    _, themes = parse_themes(":root { --deck-themes: x; }\n" + block)
    ok = check(themes[f"r{seed}"], load_rules())["ok"]
    print(block)
    print(f"/* {'passes' if ok else 'FAILS'} check-contrast. To keep it: paste into tokens.css, "
          f"give it an id and --theme-name, add the id to --deck-themes. */")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    if argv and argv[0] == "--emit":
        return emit(argv[1]) if len(argv) > 1 else 2
    path = Path(argv[0]) if argv else DEFAULT_TOKENS
    if path.is_dir():
        path = path / "asset" / "tokens.css"
    if not path.is_file():
        print(f"no tokens.css at {path}", file=sys.stderr)
        return 2
    local = path.parent / "deck-theme-rules.js"   # a deck is checked against the rules it ships
    rules = load_rules(local if local.is_file() else RULES)
    ids, themes = parse_themes(path.read_text(encoding="utf-8"))
    problems = [] if ids else [":root has no --deck-themes list"]
    problems += [f"{i}: listed in --deck-themes but has no block" for i in ids if i not in themes]
    problems += [f"{i}: block not listed in --deck-themes" for i in themes if i not in ids]
    print(f"{path}\n{'#':>2} {'theme':<16} {'L/D':<3} {'body':>8} {'label':>8} {'lit body':>9} "
          f"{'lit lab':>8} {'APCA':>5} {'ΔE00':>5}  result")
    for n, tid in enumerate((i for i in ids if i in themes), 1):
        r = check(themes[tid], rules)
        name = themes[tid].get("theme-name", "").strip("\"'")
        if not r["worst"]:
            print(f"{n:>2} {tid:<16} FAIL  {r['fails'][0]}")
        else:
            w = r["worst"]
            print(f"{n:>2} {tid:<16} {'L' if r['light'] else 'D':<3} {w['wcag-body'][0]:>6.2f}:1 "
                  f"{w['wcag-label'][0]:>6.2f}:1 {w['lit-body'][0]:>7.2f}:1 {w['lit-label'][0]:>6.2f}:1 "
                  f"{w['apca'][0]:>5.0f} {w['de'][0]:>5.1f}  {'ok' if r['ok'] else 'FAIL'}  {name}")
        problems += [f"{tid}: {f}" for f in r["fails"]]
    ro = rules["roles"]
    print(f"\ngates: body ≥ {ro['body']['wcag']}:1, label ≥ {ro['label']['wcag']}:1; lit room "
          f"(+{rules['ambient']['luminance']} of white) body ≥ {ro['body']['ambient']}:1, label ≥ "
          f"{ro['label']['ambient']}:1; chapter ΔE00 ≥ {rules['cvd']['deltaE00']} "
          f"({', '.join(rules['cvd']['visions'])}). APCA = lowest body |Lc|, reported only.")
    for p in problems:
        print("  ✗", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
