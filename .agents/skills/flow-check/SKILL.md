---
name: flow-check
description: >
  Discourse-coherence gate for long-form manuscripts: finds places where every
  sentence is correct but the argument jumps (跳躍感). Use for /check_flow, when
  the user mentions 連貫 / 不連貫 / 跳躍 / 逆向大綱 / coherence / 銜接, after a batch of
  incremental insertions, or before a milestone, 口試, or submission. Runs reverse
  outline, connective naming, a fresh-context cold read, cross-chapter
  consistency, and git-seam targeting; outputs a severity-ranked 跳躍點清單 with
  proposed bridge sentences and rewrites nothing.
user-invocable: true
---

# flow-check — 篇章連貫檢查 (discourse coherence gate)

LLM-generated prose is locally fluent but globally unplanned: each sentence is
conditioned on its neighbours, while "does this paragraph's role in the
chapter's argument hold" is maintained by no one. Incremental revision makes
it worse — every 入章-style insertion splices fluent text between two
sentences that were originally written as one continuous move, leaving a seam
that is invisible sentence-by-sentence. This skill finds those seams and
ranks them; it changes nothing by itself.

## The five checks

Run 1–3 **per chapter** (parallel agents), 4 **once across chapters**, 5
**first** whenever git history is available (cheapest, highest hit rate).

1. **逆向大綱 (reverse outline).** Compress every paragraph to one sentence:
   "this paragraph's claim is X." Then read *only the outline*. Flag: adjacent
   claims that don't connect, a claim unrelated to its section heading, the
   same claim appearing twice.
2. **銜接命名 (connective naming).** For each adjacent paragraph pair, force
   an answer: "the implied connective between ¶N's end and ¶N+1's start is
   ___ (因此／然而／此外／例如／回到⋯⋯)." Cannot name one → seam. This is
   objective where "does it read smoothly" is not.
3. **冷讀 (cold read).** A fresh-context subagent reads the chapter text and
   nothing else, marking: places it had to re-read, terms/entities appearing
   without introduction, abrupt topic shifts. **Isolation is the invariant**:
   the cold reader gets no outline, no other chapters, no conversation
   history — a reader with full context cannot feel the jumps because their
   brain silently supplies the missing bridges. (This is also why the author
   agent must not grade its own chapter.) "Fresh" means *spawned empty*: a
   context-inheriting subagent (Claude Code's `fork` agent type, a resumed
   session, a teammate that saw the drafting) carries the bridges with it and
   is disqualified — use a plain new agent whose whole prompt is the chapter
   text plus the marking instructions. A bigger context window changes none
   of this: the point is what the reader has *not* seen.
4. **跨章一致 (cross-chapter consistency).** One agent over the per-chapter
   *outlines* from layer 1 (not full text): terminology drift on core
   concepts (the manuscript's own coinages — is the same mechanism named the
   same way in every chapter?), theory-chapter concepts actually used in the
   case chapters, comparison-chapter dimensions matching case-chapter section
   structure, and every 「如第X章所述」-style reference resolving to something
   that exists and says what is claimed.
5. **git 接縫定位 (seam targeting).** `git log --stat -- <manuscript files>`
   to list late insertions and heavily-patched spots; check the ±3 sentences
   around each insertion point before anything else. Seams concentrate here.

## Output: 跳躍點清單

One severity-ranked list, `章:節/段 → 類型 → 說明 → 建議橋接句`:

| 類型 | Meaning |
| :--- | :--- |
| **斷裂** | adjacent paragraphs with no nameable connective |
| **接縫** | insertion seam — flow breaks exactly at a patched-in block |
| **漂移** | the manuscript's own term/register changes across chapters |
| **未介紹** | entity/term used before it is introduced |
| **失指** | 「如第X章」-style cross-reference that doesn't resolve or misstates |
| **重複** | same content re-introduced as if new |

Each 建議橋接句 is a proposal for the author to confirm — same
scan-and-propose discipline as fix-terms. **A bridge sentence must not alter
any cited claim** (house-style `reference/content-integrity.md`): if the only
way to connect two paragraphs changes what a source is made to say, report
the gap as structural instead of papering over it.

## Orchestration

Fan out one agent per chapter doing layers 1–3 (the cold read as its own
clean-context agent), then one synthesizer doing layer 4 over the collected
outlines, deduplicating, and ranking. For a single-file paper, treat top-level
sections as the chapters. Findings from layer 5 seed the per-chapter agents
("check these spots first").

## What it does NOT do

No fact checking, no citation form (**cite-check**), no whether-a-source-
backs-the-claim (**source-kit** § Source review), no cross-strait usage
(**fix-terms** — that lints against a fixed external rule list; flow-check
lints the manuscript's *internal* consistency with itself). Run order for a
full lint pass: **fix-terms → flow-check → cite-check** (cite-check stays
last as the mechanical gate).

Backs the `/check_flow` macro.
