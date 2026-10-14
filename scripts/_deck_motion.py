"""Motion variations for the storyboard's 動態 column and the compiler.

One catalogue, read by three users: `deck-compile` turns a code into the
`data-beat`/`data-fx`/`data-enter` attributes deck-motion.js plays,
`deck-motion-pick` offers the same codes to Jev (or to the author) as options,
and `deck-plan/reference/motion-catalog.md` documents them for humans — a test
checks the document names every code here, so the three cannot drift.

A code that `compile` cannot apply (it needs hand-drawn SVG or hand-placed
ids) is still a valid storyboard entry: the compiler keeps the slide static and
warns, so the author's intent survives in the storyboard and the deck-svg
author adds the attributes by hand.
"""

from __future__ import annotations

import re

# code → what the audience sees (what), why to pick it (pros), what it costs (cons);
# compile: deck-compile can add the attributes itself; applies: "*" or the layout codes it fits.
VARIATIONS: dict[str, dict] = {
    "M-STEP": dict(name="逐拍出現", compile=True, applies="*",
                   what="版型原本的進場順序（.rise d1–d4）改成一拍一組：標題與導語隨頁出現，每張卡、節點或階層按一次出一個，收束框最後",
                   pros="最省、最通用；講者自己控制節奏，台下跟著講到的那一格看",
                   cons="每張卡都要按一次，卡多的頁會按很多下"),
    "M-POP": dict(name="彈入", compile=True, applies="*",
                  what="同 M-STEP，但卡片、節點、階層用縮放彈入（pop）而不是上浮",
                  pros="方塊類元素更有份量，適合流程節點與時間軸",
                  cons="段落文字不適合；連續幾頁都彈會膩"),
    "M-TYPE": dict(name="導語逐字打出", compile=True, applies="*",
                   what="導語（lead／副標／一句話）逐字打出，其餘同 M-STEP",
                   pros="一句話的頁面有節奏，台下會跟著讀",
                   cons="長句打太久；只能用在純文字元素"),
    "M-CHARS": dict(name="標題逐字彈入", compile=True, applies="*",
                    what="標題逐字彈入，其餘同 M-STEP",
                    pros="封面、分節頁、結論頁有力",
                    cons="標題長就吵；一份簡報三次以內"),
    "M-LINES": dict(name="標題行遮罩", compile=True, applies="*",
                    what="標題整行從遮罩下升起，其餘同 M-STEP",
                    pros="克制，適合正式場合與多行標題",
                    cons="單行短標題看不出差別"),
    "M-COUNT": dict(name="數字遞增", compile=True, applies=["L-STAT-HERO"],
                    what="大數字從 0 遞增到位（保留前後綴與千分位），其餘同 M-STEP",
                    pros="數字頁的標準做法，數字大小一眼有感",
                    cons="只對純數字有效；比較兩個口徑不同的數字時遞增會誤導"),
    "M-SCRAMBLE": dict(name="數字解碼", compile=True, applies=["L-STAT-HERO"],
                       what="大數字從亂碼解出，其餘同 M-STEP",
                       pros="比遞增更有懸念，適合全場只有一個關鍵數字",
                       cons="一份簡報用一次就夠；台下要等它解完"),
    "M-PUSH": dict(name="推進轉場", compile=True, applies="*",
                   what="進這頁時前一頁往左推出（其餘同 M-STEP）",
                   pros="同一主題連續幾頁（時間軸上下半年、同一表格的兩段）有延續感",
                   cons="連用會暈；主題換了就不要推"),
    "M-ZOOM": dict(name="推入轉場", compile=True, applies="*",
                   what="前一頁放大推入這一頁（從畫面中心；手寫 data-zoom-from 可改成從前一頁的某個元素推入；其餘同 M-STEP）",
                   pros="從總覽進到細節，告訴台下「現在看的是剛才那一格」",
                   cons="一份簡報一兩次；只有真的從上一頁某處進來才用"),
    "M-DRAW": dict(name="畫線", compile=False, applies="*",
                   what="SVG 線條自己畫出來（流程箭頭、時間軸軌道、自繪圖）",
                   pros="自繪圖的標準做法，線畫到哪台下看到哪",
                   cons="版型目錄的流程與時間軸是 DOM 不是 SVG；要手寫 SVG 並標 data-fx=\"draw\""),
    "M-PACKET": dict(name="流動封包", compile=False, applies="*",
                     what="一個元素沿 SVG 路徑循環移動（data-along），例如資料流上的封包",
                     pros="資料流一看就懂，講到「轉送」時畫面在動",
                     cons="要手寫 SVG 路徑與封包元素"),
    "M-CONTINUE": dict(name="跨頁延續", compile=False, applies="*",
                       what="同 data-id 的元素從前一頁的位置滑過來，例如圖裡的小字長成下一頁的大數字",
                       pros="兩頁之間有因果，台下不用重新找",
                       cons="兩頁都要手標 data-id"),
    "M-REGROUP": dict(name="版面重排", compile=False, applies="*",
                      what="同一批卡片換 class 重排，從舊位置飛到新位置（data-relayout）：時間順序 ⇄ 依類型分組",
                      pros="「同樣的事實換個分類看」一頁講完",
                      cons="要手寫兩套版面 class"),
    "M-MORPH": dict(name="圖形變形", compile=False, applies="*",
                    what="SVG path 變形成另一個形狀（data-morph），例如標籤變成鏈條",
                    pros="概念轉換很直觀",
                    cons="要手畫兩個以上的形狀"),
    "M-NONE": dict(name="靜態", compile=True, applies="*",
                   what="不標拍，沿用版型原本的進場動畫（整頁一次出現）",
                   pros="分節頁、引文頁、一句話的頁不需要拍；省按鍵",
                   cons="—"),
}

CODE_RE = re.compile(r"\bM-[A-Z]+\b")


def split_codes(cell: str) -> list[str]:
    """The codes in a storyboard cell: `M-POP M-PUSH`, `M-POP、M-PUSH` or `—`."""
    return CODE_RE.findall(cell or "")


def options_for(layout: str) -> dict[str, dict]:
    """The compile-able variations that fit a layout code (for the picker and the author)."""
    out = {}
    for code, v in VARIATIONS.items():
        if not v["compile"]:
            continue
        if v["applies"] == "*" or layout in v["applies"]:
            out[code] = v
    return out


# ---- applying codes to the compiler's HTML ------------------------------------------------
# The renderers encode the reveal order as `.rise` + `.d1`–`.d4`, so a beat is read off the class:
# no dN → beat 0 (with the slide), dN → beat N. Elements keep the classes; the engine strips them at run time.

_TAG_RE = re.compile(r"<(h1|h2|h3|p|div|ul|blockquote|section)\b([^>]*)>")
_CLASS_RE = re.compile(r'\bclass="([^"]*)"')
_BLOCKS = re.compile(r"\b(card|tl|flownode|tier|stat-hero__stat|term|example|confront__side|confront__vs|marks|matrix-deepdive__note|split-anchor__hero|bento__hero)\b")
_LEADS = re.compile(r"\b(lead|hero__sub|onesentence)\b")
_TITLES = re.compile(r"\b(kicker|rise)\b")


def _add(attrs: str, extra: str) -> str:
    return attrs.rstrip() + " " + extra


def apply_motion(html: str, codes: list[str]) -> tuple[str, list[str]]:
    """Add deck-motion attributes to one rendered slide for the given codes.

    Returns the HTML and warnings (unknown codes, codes the compiler cannot apply).
    """
    warnings: list[str] = []
    codes = [c for c in codes if c]
    unknown = [c for c in codes if c not in VARIATIONS]
    for c in unknown:
        warnings.append(f"動態 {c} 不在目錄裡（見 deck-plan/reference/motion-catalog.md）")
    manual = [c for c in codes if c in VARIATIONS and not VARIATIONS[c]["compile"]]
    for c in manual:
        warnings.append(f"動態 {c} 要手寫屬性（{VARIATIONS[c]['cons']}），編譯時略過")
    active = [c for c in codes if c in VARIATIONS and VARIATIONS[c]["compile"] and c != "M-NONE"]
    if not active:
        return html, warnings

    def tag(m: re.Match) -> str:
        name, attrs = m.group(1), m.group(2)
        if name == "section":
            if "M-PUSH" in active and 'data-enter=' not in attrs:
                attrs = _add(attrs, 'data-enter="push"')
            elif "M-ZOOM" in active and 'data-enter=' not in attrs:
                attrs = _add(attrs, 'data-enter="zoom"')
            return f"<{name}{attrs}>"
        if "data-beat=" in attrs:
            return m.group(0)
        cm = _CLASS_RE.search(attrs)
        cls = cm.group(1) if cm else ""
        if not re.search(r"\brise\b", cls):
            return m.group(0)
        dm = re.search(r"\bd([1-4])\b", cls)
        beat = int(dm.group(1)) if dm else 0
        extra = f'data-beat="{beat}"'
        if "M-POP" in active and name == "div" and _BLOCKS.search(cls):
            extra += ' data-fx="pop"'
        elif "M-TYPE" in active and name == "p" and _LEADS.search(cls):
            extra += ' data-fx="type" data-dur="1.6"'
        elif name in ("h1", "h2") and _TITLES.search(cls):
            if "M-CHARS" in active:
                extra += ' data-fx="chars" data-dur=".7"'
            elif "M-LINES" in active:
                extra += ' data-fx="lines" data-dur=".7"'
        return f"<{name}{_add(attrs, extra)}>"

    html = _TAG_RE.sub(tag, html)
    if "M-COUNT" in active or "M-SCRAMBLE" in active:
        fx = "count" if "M-COUNT" in active else "scramble"
        html = re.sub(r'<div class="stat-hero__num">', f'<div class="stat-hero__num" data-beat="1" data-fx="{fx}" data-dur="1.2">', html)
    return _compact_beats(html), warnings


def _compact_beats(html: str) -> str:
    """Renumber beats so they are consecutive: a verdict sits on d4 whatever the card count,
    and an empty beat would be a key press on which nothing happens."""
    used = sorted({int(b) for b in re.findall(r'data-beat="(\d+)"', html)})
    first = 0 if used and used[0] == 0 else 1   # beat 0 is "with the slide": a slide with no beat-0 element keeps its first press
    order = {b: i + first for i, b in enumerate(used)}
    return re.sub(r'data-beat="(\d+)"', lambda m: f'data-beat="{order[int(m.group(1))]}"', html)
