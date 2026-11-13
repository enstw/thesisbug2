---
name: read-check
description: >
  Paragraph-level cold read for manuscripts written with AI help: isolated
  readers, each given one paragraph and nothing else, pick the fragments that
  are hard to read, so the manuscript's own coined terms and over-compressed
  phrasing surface. Use for /check_read, when the author says the text 讀起來
  像 AI / AI 味 / 難讀 / 自造詞 / 太濃縮, before a rewrite pass, and to accept one.
  ./fw read-check writes the prompts and builds the report; the readers only
  pick, and nothing is rewritten.
---

# read-check — 段落冷讀挑錯 (isolated paragraph read)

A manuscript drafted over many sessions by an agent that holds the whole
argument acquires a private vocabulary. The drafting agent coins a short name
because the definition is in its context. Once the name is in the text, every
later agent — drafting, editing or reviewing — meets it with that same context,
reads it without effort, reuses it and builds compounds on it. Nobody in the
loop is without the context except the person the manuscript is for. So the
text gets denser with each pass while every check passes, and the author, who
has also read it many times, stops seeing it.

Two findings fix the design:

- **The same reader misses a coined term when it sees the neighbouring
  paragraphs and catches it when it sees one paragraph.** In the run behind
  this skill, two models given twenty paragraphs in one request flagged none
  of a term's seven occurrences, and given the same paragraphs one per request
  both flagged all seven. (The question also changed between the two runs, from
  "coined terms" to "hard to read", so the two causes are not separated.) The
  surrounding text teaches the reader the term, which is why a chapter-level
  cold read (flow-check) does not find a term the chapter itself repeats.
- **A reader who can explain a term has stopped being a test of it.** An agent
  that reconstructs the meaning from context then defends the wording. "The
  manuscript already uses it" is how the term spread, so it is never a reason
  to keep one.

## Roles

| Role | Sees | Does |
| :--- | :--- | :--- |
| Reader (isolated) | one paragraph | picks hard fragments, verbatim; nothing else |
| Author | the glossary, then the report | approves the glossary; decides what each picked fragment becomes |
| Rewriter (has context) | manuscript, sources, decisions | rewrites what the author accepted, through safe-edit |

The reader **does not explain what it thinks a fragment means and does not
suggest a rewrite.** Its guess at the meaning is unreliable — that is the
finding, not a service — and a rewrite written without the argument changes
what the sentence claims. The rewriter needs the context to keep the claim; for
the same reason the rewriter cannot be the one who accepts the result. Accepting
is a fresh run of the readers on the rewritten paragraphs.

## The glossary comes first

The manuscript's glossary — its definitions section (名詞定義) or
`<unit>/glossary.md` — is the list of special terms the manuscript may use.
**Only a term in the glossary may stay as a special term; everything else is
written in the field's ordinary vocabulary.** This turns "keep it unless
someone objects" into "replace it unless the author approved it", which is
what stops new coinages from accumulating. Review the glossary with the author
before any reader runs and before anything is rewritten:

- **An entry needs an anchor outside the manuscript**: the source-language
  original and a cited work in which the field uses the term. A gloss in
  another language proves nothing by itself, because an agent that coins a
  term also coins its translation. The exception is a concept of the
  manuscript's own that the argument cannot do without (often the one in the
  title); the author approves each of those by name.
- **An agent never adds an entry by itself.** Adding one is the author's
  decision, recorded in `DECISIONS.md`, because a glossary the drafter can
  extend turns every coinage into an approved term.
- **Every entry is defined where the term first appears**, and the list stays
  short: each entry is something the reader has to learn.

Ordinary vocabulary cannot be listed, so the readers below are what detects a
term that is neither ordinary nor approved.

## Procedure

1. **Write the prompts.** One file per paragraph, as a reader of the finished
   document sees it (citations shown as `[註]`, emphasis marks gone; headings,
   tables, code and block quotations are not sent):

   ```bash
   ./fw read-check prompts <unit> --out <unit>/gpt-review/<yyyy-mm-dd>-read-check \
       --reader "<who the manuscript is for>" [--sample 20] [--files 03-theory.qmd]
   ```

   `--reader` names the real audience from `COURSE.md` (for example
   「台灣的政治學／國際關係教授」), because what counts as an established term
   depends on who reads. Start with `--sample` (seeded, at least one paragraph
   per file) to see how much the readers pick before paying for the whole
   manuscript.
1. **Hand each prompt to an isolated reader and save its answer as it came**
   to `<out>/picks/<reader-name>/<id>.json`. Isolation is the invariant: a
   reader gets one prompt file and nothing else — no other paragraph, no unit
   files, no conversation. Use a fresh-context subagent per paragraph, or an
   external model through whatever review integration the host has (select and
   record the model as gpt-review § Step 0 does), started outside the course
   directory so it cannot open the manuscript. Do not batch paragraphs into one
   request to save calls, because the batch is the context that hides the
   terms. A lighter model or a lower reasoning effort is enough, since
   reconstructing the meaning is exactly what the reader is not supposed to
   do; in the maintainer's runs it picked at least as much. Two readers from different model families are better
   than one, and the report shows where they agree. Name each reader directory
   after the model and effort. With no isolated reader available, leave the
   prompts in place and report the check as pending; a same-context reread is
   never this check.
1. **Build the report:** `./fw read-check collect <out> --glossary <file>`
   (the file holding the definitions: an entry is a block opening with
   `**term（original）**：`). Fragments that do not
   occur verbatim in their paragraph are dropped and counted, and an answer
   that is not a JSON array of strings is listed to be asked again.
   `report.md` opens with the fragments ranked by how many readers picked them
   and how often each occurs across the whole manuscript: a fragment in dozens
   of places and many files is a term the manuscript grew itself. `picks.json`
   holds every kept fragment with its character offsets and readers. The
   詞彙表 column names the entry that covers a fragment; a blank means the
   fragment is not an approved term, and a compound built on an approved name
   counts as a new term. A second table lists the entries the readers still
   picked: check first that each is defined where it first appears, then
   whether the field really uses it.
1. **The author decides.** The report is a worklist, not a gate, and the
   readers over-pick: a paragraph read alone also trips on things the previous
   page settled. A fragment outside the glossary is replaced with the field's
   ordinary wording everywhere it occurs, unless the author decides it belongs
   in the glossary; a fragment that is only an awkward phrase is reworded. A
   term the author also misread goes first.
1. **Rewrite, then run the readers again** on the changed paragraphs
   (`--files`, or the same `--sample` and `--seed`). A rewrite is accepted when
   the readers stop picking the fragment and the author agrees it reads well;
   the rewriter's own judgment does not count. Land edits with **safe-edit** and
   keep `house-style` `reference/content-integrity.md`: citations, quotations,
   hypothesis labels and every qualifier that states how strong the evidence is
   stay as they were, because the cheapest way to satisfy a reader is to delete
   the hedge it tripped on.

## Calibrate the readers against people

Two models checking each other converge on what models find fluent, which is
how the manuscript got here. Before trusting a reader on the whole manuscript,
compare its picks on a sample with a human's:

- **The author's own marks.** Have the author mark the same sample without
  seeing the readers' picks, then count overlap, misses and extras. Do not show
  the report first; the comparison is void once the author has seen it.
- **A person outside the project**, when one is available: where they gave up
  is the strongest evidence there is, and they can say that a passage is
  unreadable even when they cannot say which words are jargon — the readers
  supply that half.

Readers do not know the author's taste. Words the author dislikes for reasons
of style (a regional usage, a habitual abbreviation) may never be picked, so
keep the author's own word list in `DECISIONS.md` and scan for it directly.

## What it does NOT do

No argument flow (**flow-check**; its cold read gives the reader a whole
chapter and asks about jumps), no cross-strait usage against the fixed list
(**fix-terms**), no judgment of the argument (**gpt-review**), no rewriting.
This check replaces the former `lint-readability` pattern counter and
safe-edit's readability ratchet: a count that nobody compared with a human
reading became a target, and a rule such as "no long run without a pause" is
satisfied by a comma that makes the sentence worse. Lint order for a
manuscript: **fix-terms → read-check → flow-check → cite-check**, since
flow-check's bridge sentences should be written in the wording that survives
this check.

Backs the `/check_read` macro.
