# Stable summary template — `<unit>/notes/<key>.md`

The skeleton a stable per-source summary (SKILL.md §5) follows. Copy the block
below into `notes/<key>.md` and fill it in Traditional Chinese. Every factual
line carries a page or paragraph locator. Keep the section order: the first two
sections let a reader judge the work in a minute, and the later ones carry the
detail a citation is checked against.

Two rules hold throughout:

- **Mark what is not the author's.** A line that is the summarizer's reading
  (a writing observation, a characterization of the author's contribution)
  says so, because a later agent may otherwise cite it as the source's claim.
- **Spell out every abbreviation at its first use** as 全名（縮寫）, in this
  file, even when another file already did: each file is read on its own.

```markdown
# 作者（年）〈題名〉完整摘要

- 引用鍵：`<key>`；版本與頁碼範圍：〔期刊卷期／書的版次，頁 x–y〕
- 原文：`refs/<key>.md`（或 `.pdf`）；身分稽核：genuine（見 `refs/audit/<key>.jsonl`）

## 論文骨架：問題、假說與論證

把全文拆成研究論文的構件，看這篇是怎麼搭起來的；細節見後面各節。最後一項是整理者的觀察，不是作者的主張。

- **研究問題**：〔作者要回答的問題；能引原句就引〕（p.）
- **對話對象與缺口**：〔回應哪個理論或文獻，它解釋不了什麼〕（p.）
- **核心主張與假說**：〔主張；文中明寫的假說逐條引出，並註明是否經過檢驗〕（p.）
- **論證步驟**（作者的順序）：
  1. 〔導論做了什麼〕（pp.）
  1. 〔各節依序一行〕（pp.）
- **證據與方法**：〔理論推演、個案、統計、文件分析……例子是說明用還是系統檢驗〕（p.）
- **結論與貢獻**：〔結論；作者自述的貢獻〕（p.）
- **範圍與作者自陳的限制**：〔作者自己劃的界線與承認的弱點〕（p.）
- **寫作上可以觀察的地方**（整理者的觀察，不是作者的主張）：
  1. 〔怎麼開場、怎麼定位缺口、怎麼安排路標、怎麼收束〕（p.）

## 作者與學術位置

- **作者**：〔原文刊出的職稱與單位，以原文頁面為準〕（p.）；〔研究經費或計畫，若原文註明〕
- **相關前作**：〔原文自引的作者前作〕（參考文獻頁）
- **在領域中的位置**：〔所屬學派或研究脈絡、主要貢獻；出自其他文獻時引該文獻並附頁碼，原文以外的簡歷另立來源〕
- 〔整理者對貢獻的概括，標明「整理者的概括」〕

## 這篇在回答什麼問題

〔背景與問題意識〕

## 讀這篇之前要知道的理論

〔理解本文需要的前提理論與概念，各附出處〕

## 論證怎麼走

### 〔原文章節標題〕（pp. x–y）

〔依作者順序，含機制、範圍與例子〕

## 表格與圖

〔原文的表與圖；整理者自製的整理表標「整理表」並附所整理的頁碼〕

## 關鍵概念與定義

- **名詞（縮寫）**：〔作者的定義或用法，附頁碼；作者未定義的，標「整理者的白話」〕

## 方法與證據

〔資料、個案選擇、證據的強度與限制〕

## 結論與作者的立場

〔結論、作者的規範立場、未解決的問題〕

## 可以拿來討論的爭點

〔原文留下的爭點與可能的反駁，標明哪些是整理者提出的〕
```

What does **not** go in this file: the week's theme, comparisons with other
readings, the presenter's position, and anything sized to one talk. Those are
task choices and belong in the task Model (`guide.qmd` or the manuscript),
which selects from this summary and cites the original.
