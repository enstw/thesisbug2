# Content-integrity rules (cited / graded academic work)

These travel with the **content**, not the engine — honor them in any deck or
paper that renders sourced claims (deck-svg, deck-image, deck-beamer,
and the paper engines all quote this one file).

1. **Disputed claims stay disputes.** If two sides tell conflicting stories,
   present it as a 羅生門 / dispute — never collapse it into a single established
   fact.
2. **Speculation is labeled.** Analyst or media speculation that isn't officially
   confirmed must read as speculation, not fact.
3. **Citations stay attached to their claims.** Keep the source on the slide/line
   it supports (the deck `cite` field, a beamer footnote, a paper `[@key]`).
   This is graded work — an unsourced claim is a defect.
4. **Respect "do-not-misphrase" notes** from the source as hard constraints on
   copy. If a source flags wording that must not be paraphrased, treat it as a
   verbatim constraint.
5. **Match the source language.** This corpus is tuned for Traditional Chinese;
   keep the deck/paper language consistent with the source unless asked otherwise.

6. **Borrowed wording is marked, everything else is reworded.** When you
   summarise or restate a source from `<unit>/refs/<key>.md`, either quote it
   (「…」 or a block quote, with `[@key, p. N]`) or put it fully in your own
   sentence structure and vocabulary. A sentence lifted from the transcript
   with a citation but no quotation marks is still plagiarism under a
   similarity check, and a translated sentence that keeps the source's clause
   order counts as lifted. Current models drift toward reproducing source
   passages unmarked when a transcript is open in context, so check this
   deliberately after any source-heavy paragraph.

   <example>
   (Illustrative key and text — not a real source.)
   Source (`refs/chen2024.md`, [Page 12]): 「認知作戰的核心不在於說服，而在於
   使對手喪失判斷真偽的能力。」

   Wrong — lifted, cited but unmarked:
   認知作戰的核心不在於說服，而在於使對手喪失判斷真偽的能力 [@chen2024, p. 12]。

   Right — reworded, with one short marked phrase:
   陳氏主張認知作戰的目標是侵蝕判斷力而非改變立場，亦即讓對手「喪失判斷真偽
   的能力」[@chen2024, p. 12]。

   Why: the claim and locator are identical in both; only the second makes
   clear which words are the source's and which are the author's.
   </example>

If a requested change would violate one of these (e.g. stating a disputed claim
as fact to make a slide cleaner), surface the conflict instead of silently
complying.
