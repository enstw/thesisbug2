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

# code → what the audience sees (what), what the effect buys (pros), what it needs and what it costs (cons);
# compile: deck-compile can add the attributes itself; applies: "*" or the layout codes it fits.
#
# The wording describes the EFFECT only — timing, key presses, what it needs to work, when it fails —
# and never names a page type ("covers", "section breaks", "number slides"). The picker hands Jev the
# page's facts (position, title length, item count, number present, minutes, neighbours) next to these
# descriptions and lets it judge; a "suits covers" hint here would be an answer key, and two answer keys
# that both apply to one page produced a coin-flip on the finale of the first live run (2026-10-14).
# The same wording serves an author or agent choosing by hand; a test keeps page-type names out.
VARIATIONS: dict[str, dict] = {
    "M-STEP": dict(name="逐拍出現", compile=True, applies="*",
                   what="標題與導語隨頁出現；之後每按一次出現一組（一張卡、一個節點或一層），每組上浮 0.6 秒；收束框是最後一拍。按鍵次數＝組數＋1",
                   pros="台下只看得到講到的那一格；動作最小，任何版型都能用",
                   cons="組越多按越多次；頁上只有一組或沒有組時，和 M-NONE 幾乎看不出差別"),
    "M-POP": dict(name="彈入", compile=True, applies="*",
                  what="同 M-STEP 的拍序，但每組從 82% 縮放彈到 100%（0.6 秒），不是上浮",
                  pros="有邊框或底色的方塊（卡、節點、階層）出現時更有份量",
                  cons="需要頁上有方塊狀的元素才看得出差別；段落文字彈入會抖；連續幾頁都彈會看膩"),
    "M-TYPE": dict(name="導語逐字打出", compile=True, applies="*",
                   what="導語（lead、副標或一句話）逐字打出 1.6 秒，其餘同 M-STEP",
                   pros="台下跟著字一個一個讀，那一句被放慢、被讀完",
                   cons="需要頁上有一句純文字導語；句子超過約 25 字就打太久；台下等它打完才會看別處"),
    "M-CHARS": dict(name="標題逐字彈入", compile=True, applies="*",
                    what="標題的字依序彈入（每字錯開 0.04 秒，整個約 0.7 秒），其餘同 M-STEP",
                    pros="短標題單獨出現時有重量，台下的目光停在它上面",
                    cons="需要標題短（約 12 字內），長標題逐字彈就吵；同一份簡報第三次用就不稀奇了"),
    "M-LINES": dict(name="標題行遮罩", compile=True, applies="*",
                    what="標題整行從遮罩下升起（每行錯開 0.1 秒，約 0.7 秒），其餘同 M-STEP",
                    pros="動作小而正式；多行標題一行一行出現，讀的順序清楚",
                    cons="單行短標題幾乎看不出和 M-STEP 的差別"),
    "M-COUNT": dict(name="數字遞增", compile=True, applies=["L-STAT-HERO"],
                    what="大數字從 0 遞增到位（1.2 秒，保留前後綴與千分位），其餘同 M-STEP",
                    pros="數字的大小被看見，不只是被讀到",
                    cons="需要頁上有一個純數字；並列兩個口徑不同的數字時，遞增會讓人誤以為可以相比"),
    "M-SCRAMBLE": dict(name="數字解碼", compile=True, applies=["L-STAT-HERO"],
                       what="大數字從亂碼解出（1.2 秒），其餘同 M-STEP",
                       pros="解出前台下不知道數字多大，有懸念；比遞增更搶眼",
                       cons="需要頁上有一個純數字；台下要等它解完才讀得到；同一份簡報第二次用就沒有懸念（全場只保留一次）"),
    "M-PUSH": dict(name="推進轉場", compile=True, applies="*",
                   what="進這頁時前一頁往左推出、這頁從右滑入（0.5 秒），之後同 M-STEP",
                   pros="兩頁像同一條內容的前後段，台下感覺「接著看」",
                   cons="兩頁內容不相連時，推進暗示了不存在的連續；連續幾頁都推會暈（不會連續兩頁用）"),
    "M-ZOOM": dict(name="推入轉場", compile=True, applies="*",
                   what="前一頁放大 2.6 倍淡出、這頁從 96% 放大進來（0.8 秒；手寫 data-zoom-from 可改成從前一頁的某個元素放大），之後同 M-STEP",
                   pros="台下讀到「現在看的是剛才那一格的細節」",
                   cons="這頁不是前一頁某處的細節時，放大會誤導；動作大，全場最多兩次"),
    "M-DRAW": dict(name="畫線", compile=False, applies="*",
                   what="SVG 線條沿著路徑畫出來（流程箭頭、時間軸軌道、自繪圖），線畫到哪台下看到哪",
                   pros="自繪圖的結構依講述的順序出現",
                   cons="要手寫 SVG 並標 data-fx=\"draw\"；版型目錄的流程與時間軸是 DOM 不是 SVG，用不上"),
    "M-PACKET": dict(name="流動封包", compile=False, applies="*",
                     what="一個元素沿 SVG 路徑循環移動，例如資料流上的封包",
                     pros="講到「資料往哪裡去」時畫面正在流",
                     cons="要手寫 SVG 路徑與封包元素並標 data-along"),
    "M-CONTINUE": dict(name="跨頁延續", compile=False, applies="*",
                       what="同 data-id 的元素從前一頁的位置滑到這頁的位置（0.8 秒），例如圖裡的小字長成這頁的大數字",
                       pros="台下不用在新頁重新找；兩頁的因果用位置接起來",
                       cons="要手標兩頁的 data-id；兩頁沒有共同的元素就沒有東西可接"),
    "M-REGROUP": dict(name="版面重排", compile=False, applies="*",
                      what="同一批卡片換 class 重排，從舊位置飛到新位置（data-relayout），例如時間順序 ⇄ 依類型分組",
                      pros="同樣的事實換個分類看，在同一頁完成",
                      cons="要手寫兩套版面 class"),
    "M-MORPH": dict(name="圖形變形", compile=False, applies="*",
                    what="SVG path 變形成另一個形狀（data-morph），例如標籤變成鏈條",
                    pros="一個概念變成另一個概念，變形的過程本身就是說明",
                    cons="要手畫兩個以上的形狀"),
    "M-NONE": dict(name="靜態", compile=True, applies="*",
                   what="不標拍，整頁隨版型原本的進場動畫一次出現；按一次就換下一頁",
                   pros="零按鍵；台下一眼看到整頁，自己決定先看哪裡",
                   cons="頁上有好幾組內容時，台下會先把全部讀完，不會跟著講者"),
}

# Most restrained first: fewer key presses, smaller movement. The picker falls back to the more
# restrained of Jev's top two when the race is close, and prints that it did; an author choosing
# by hand applies the same tie-break.
RESTRAINT = ["M-NONE", "M-STEP", "M-LINES", "M-COUNT", "M-TYPE", "M-POP", "M-CHARS", "M-SCRAMBLE", "M-PUSH", "M-ZOOM",
             "M-DRAW", "M-CONTINUE", "M-PACKET", "M-REGROUP", "M-MORPH"]

# Words that would turn an option into an answer key; a test keeps them out of what/pros/cons.
PAGE_TYPE_WORDS = ["封面", "分節", "結論", "引文", "一句話的頁", "數字頁", "適合"]


def more_restrained(a: str, b: str) -> str:
    """The more restrained of two codes (unknown codes count as least restrained)."""
    rank = {c: i for i, c in enumerate(RESTRAINT)}
    return a if rank.get(a, len(RESTRAINT)) <= rank.get(b, len(RESTRAINT)) else b


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
