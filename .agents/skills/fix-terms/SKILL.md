---
name: fix-terms
description: >
  Normalizes Traditional-Chinese academic terminology for Taiwan IR /
  strategic-studies writing. Use for /fix_terms, when a draft or deck contains
  mainland usage (質量→品質, 信息→資訊, 優化→最佳化), or to lint terminology before
  submission. Scans and proposes (位置 → 原詞 → 建議) rather than blind-replacing:
  rules are context-aware, a mandatory-translation list overrides (制腦權, 造謠,
  錯誤資訊, 智能合約), and quotations are left verbatim.
---

# fix-terms — terminology & cross-strait usage校正

Lints Chinese academic prose into **Taiwan academic usage**. Two rule sets, then
a do-no-harm constraint. Reusable across every paper type *and* presentation
decks.

## 1. Mandatory override list (最高優先級指定翻譯)

These translations have absolute priority — **never** use another rendering:

| English | 指定譯名 |
| :--- | :--- |
| Command of thinking | **制腦權** |
| Disinformation | **造謠** |
| Misinformation | **錯誤資訊** |
| Smart contract | **智能合約** |

## 2. Cross-strait correction (兩岸用語校正)

Convert mainland-China usage to Taiwan academic usage.

- **General:** 質量→品質、信息→資訊、項目→專案/項目（視語境）、優化→最佳化、
  魯棒性→穩健性。
- **Context-aware (語境敏感):**
  - **mapping** → 數學/戰略語境「映射」；UI/功能語境「對應」。
  - **object** → 程式語境「物件」；一般語境「對象」或「實體」。

## 3. How to apply

- **Scan and propose, don't silently rewrite.** List the suggested corrections
  (`位置 → 原詞 → 建議`) so the user can confirm, especially for context-sensitive
  terms where the right choice depends on meaning.
- **Respect quotations and do-not-misphrase notes.** A term inside a direct quote
  or flagged by a source as verbatim is a hard constraint — do not "correct" it
  (house-style `reference/content-integrity.md` rules 4–5). Flag the conflict
  instead.
- Keep output in **Traditional Chinese** (the corpus default).

Backs the `/fix_terms` macro.
