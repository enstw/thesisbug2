#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["opencc-python-reimplemented"]
# ///
# -*- coding: utf-8 -*-
"""check-zh-variants — 簡繁與異體碼位的源頭檢查。

掃描 unit 目錄下的寫作源檔（chapters/*.qmd 與頂層 *.qmd），在「源頭」抓出兩類
碼位問題，而不是事後從 PDF 文字層倒推：

  1. 異體／相容碼位（無條件檢查，零依賴）：視覺上與臺灣標準字形難以分辨、
     但碼位不同的字——内(≠內)、爲(≠為)、録(≠錄)、値(≠值)、硏(≠研)、
     緖(≠緒)……以及 Unicode 相容表意文字區（U+F900–FAFF、U+2F800–2FA1F）。
     這批字清單來自 ENSFont cmap 別名分析（2026-07-10）：字型會把它們畫成
     繁體字形，所以肉眼與 PDF 都看不出來，只有掃源碼位能抓到。
  2. 簡體字（可選，需 opencc）：逐字以 s2t 轉換比對，轉換後不同者即簡體
     專用字。經 `./fw check-zh-variants` 執行時由 uv 依檔頭宣告自動備妥 opencc；
     直接以 python3 執行而無 opencc 時，略過此層並提示。

範圍：<unit>/chapters/*.qmd 與 <unit>/*.qmd。refs/ 逐字轉錄（保留來源原文）與
PROGRESS.md（工作日誌得引用原文）不在檢查範圍。引文亦不豁免——本語料庫
的引用體例是「轉字不轉詞」，字級上不應存在簡體字。

Exit code：發現未列白名單的問題碼位時為 1，否則 0。
"""
import sys
import re
from pathlib import Path as _P

sys.path.insert(0, str(_P(__file__).resolve().parent))
from _paths import manuscript_files, resolve_unit  # noqa: E402
import unicodedata
from pathlib import Path

# 臺灣慣用而 s2t 會誤報的字。岳／余／温 常見於人名正字（著錄即作此形），
# 轉換後反而改錯人名，故列入白名單。
WHITELIST = set("台群准托游淀秘后里干岳余温")

# 行內豁免標記：該行刻意示範或討論簡體字形（如 ch4 引用體例補記
# 「采取强制措施」→「採取強制措施」的轉換範例）時，行尾加此註解
PRAGMA = "<!-- zh-source-ok -->"

# 異體／變體碼位 → 臺灣標準字（源自 ENSFont cmap 別名分析）
VARIANTS = {
    "内": "內", "爲": "為", "録": "錄", "値": "值", "硏": "研", "緖": "緒",
    "黄": "黃", "産": "產", "説": "說", "户": "戶", "戸": "戶", "温": "溫",
    "眞": "真", "吿": "告", "宫": "宮", "吕": "呂", "奥": "奧", "靑": "青",
    "兑": "兌", "册": "冊", "删": "刪", "别": "別", "匀": "勻", "卽": "即",
    "呑": "吞", "吴": "吳", "悦": "悅", "愼": "慎", "絶": "絕", "緑": "綠",
    "脱": "脫", "虚": "虛", "閲": "閱", "飮": "飲", "郷": "鄉", "鄕": "鄉",
    "带": "帶", "帯": "帶", "录": "錄", "彦": "彥", "禿": "禿", "税": "稅",
    "粤": "粵", "丢": "丟", "偸": "偷", "僞": "偽", "尙": "尚", "峰": "峰",
    "廐": "廄", "廏": "廄", "曁": "暨", "汚": "污", "涙": "淚", "煙": "煙",
    "眾": "眾", "衞": "衛", "鋭": "銳", "頼": "賴", "顔": "顏", "髙": "高",
}
VARIANTS = {k: v for k, v in VARIANTS.items() if k != v}


def compat_block(ch):
    cp = ord(ch)
    return 0xF900 <= cp <= 0xFAFF or 0x2F800 <= cp <= 0x2FA1F


def load_s2t():
    try:
        from opencc import OpenCC
        return OpenCC("s2t")
    except Exception:
        return None


def scan(root):
    files = manuscript_files(Path(root))
    cc = load_s2t()
    problems = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if PRAGMA in line:
                continue
            for ch in line:
                if ch in WHITELIST:
                    continue
                if ch in VARIANTS:
                    problems.append((f, lineno, ch, f"異體碼位 U+{ord(ch):04X}，臺灣標準作「{VARIANTS[ch]}」"))
                elif compat_block(ch):
                    name = unicodedata.name(ch, "?")
                    norm = unicodedata.normalize("NFC", unicodedata.normalize("NFKD", ch))
                    problems.append((f, lineno, ch, f"相容表意文字 U+{ord(ch):04X}（{name}），應作「{norm}」"))
                elif cc and "一" <= ch <= "鿿":
                    t = cc.convert(ch)
                    if t != ch and len(t) == 1:
                        problems.append((f, lineno, ch, f"疑似簡體 U+{ord(ch):04X}（s2t →「{t}」）"))
    return problems, cc is not None


def main():
    root = resolve_unit(sys.argv[1] if len(sys.argv) > 1 else None)
    problems, full = scan(root)
    if not full:
        print("[i] 未安裝 opencc — 僅執行異體／相容碼位檢查。完整簡體檢查請用：")
        print("    ./fw check-zh-variants <unit>   （由 uv 依檔頭宣告備妥 opencc）")
    if problems:
        for f, lineno, ch, msg in problems:
            print(f"{f}:{lineno}: 「{ch}」 {msg}")
        print(f"\nFAIL — {len(problems)} 處問題碼位")
        sys.exit(1)
    tier = "簡體＋異體＋相容碼位" if full else "異體＋相容碼位"
    print(f"OK — 源頭碼位檢查通過（{tier}）")


if __name__ == "__main__":
    main()
