# 複述測驗 (comprehension test)

`#debug` measures whether the audience can *see* a slide; this test measures
whether they can *understand* it. A deck built by condensing a manuscript
fails in a way no layout check sees: each line is a correct cut of a cited
sentence, but the cut removed the event and kept its qualifier, so a reader
without the manuscript cannot say what happened. The author cannot catch this
by rereading, because the author's context silently supplies the missing
subject, object or definition.

## The defects it catches

1. **Fragment** — a subject, verb or object is gone; the audience cannot say
   who did what to whom (「某甲的單方指控」 without what was alleged, or
   against whom).
1. **Qualifier before claim** — 「單方」「未證實」「推估」 arrive before the
   claim they qualify, or the claim never appears.
1. **Mixed levels** — one line or list mixes kinds of thing: what happened
   with how strong the evidence is, a fact with the author's judgement, an
   event type with a source type, a method with a person.
1. **Undefined or renamed term** — a term or alias appears with no
   definition, or one thing goes by several names across slides, so each new
   name looks like a new thing.
1. **Telegraph style** — colons, arrows, `≠` and enumeration commas stand in
   for the relation the reader has to reconstruct.

A sixth result only the paraphrase exposes: **misreading** — the reader
understands something, but not what the presenter meant (two storylines that
share a word, an example placed next to the wrong case).

## Procedure

1. Extract the visible text:
   `./fw deck-text <talk> --out <unit>/gpt-review/<yyyy-mm-dd>-deck-text.md`.
   Speaker notes, `data-label`, the storyboard and the manuscript are left
   out on purpose, because each of them restores what the slide dropped.
1. Give that file — and nothing else — to an isolated reader: a fresh-context
   subagent, or a separate session with no access to the unit. Use the
   prompt below. Isolation is the invariant, as in flow-check's cold read: a
   reader that has seen the notes or the conversation cannot feel the gap, so
   a same-context reread is never reported as this test. With no isolated
   reader available, mark the test pending.
1. Optionally add an editor's pass: `gpt-review` in challenge mode, reading
   the extracted text first and the manuscript second, classifying each line
   by the five defects and proposing a rewrite drawn only from the
   manuscript. The two passes find different things — the editor sees
   structure, the paraphrase sees misreadings — so merge them into one table
   with who found each item.
1. The author decides. A rewrite that the manuscript already supports changes
   the slide only; a defect that lives in the manuscript itself (an undefined
   term, a category mixing two levels) is fixed upstream first, because the
   deck may not say what the manuscript does not.
1. Re-extract and rerun the paraphrase on the revised deck. The test is done
   when the reader can restate every content slide.

Store both reviewers' output verbatim in `<unit>/gpt-review/`, as for any
external review.

## Paraphrase prompt (isolated reader)

Fill the 〔…〕 slots; send no other file.

```text
你要扮演一位第一次聽這場簡報的〔聽眾身分，例如：研究所同學〕。你對報告的主題完全沒有背景知識，只看得到投影片上的字，聽不到講者說話。

只准讀這一個檔案，不要讀任何其他檔案、不要搜尋、不要上網、不要執行指令：
〔deck-text 檔案路徑〕

檔案是全部投影片上台下看得到的文字，依序排列。請依序讀；讀到第 N 張時，只能用第 0 到 N 張已出現的資訊來理解，不能用後面的投影片回頭補。

對每一張做複述測驗：
1. 複述：用一句完整的話（有主詞、動詞、受詞）寫出你從這張帶走的意思。複述不出來就寫「複述不出來」。
2. 卡住的地方：逐條引用原文，說明為什麼卡住：不知道主詞或受詞是誰；限定語或否定出現在你還不知道主張是什麼的時候；同一行或同一清單混了不同層級的東西；第一次出現、沒解釋的術語或代稱，或同一件事換了名字；電報體（冒號、箭頭、等號、頓號拼成，要自己補關係）；標題和內容接不上。
3. 若你的理解可能和講者想說的不同，標「可能誤解」並說明理由。
4. 沒有卡住的地方就寫「順」。

不要評論版面、配色、字級，也不要評論論點對錯或證據強弱；只回答「沒有背景的觀眾讀得懂嗎」。不要提出改寫。

輸出：用繁體中文，逐張列出（第 N 張：複述／卡住的地方／可能誤解）。最後列出最難懂的 5 張（依嚴重程度排序）與整份反覆出現的三種困擾。
```

## The presenter's own rule

Cover the speaker notes and read only this slide and the ones before it: can
you say who did what to whom, and whose claim it is? If not, state the whole
event first, then its evidential strength, then your judgement — each on its
own line.
