# Agent guide — working in a course repo

You are in a course repository that mounts the thesisbug2 framework at `.framework/`. This file is the framework's half of your instructions; the course's own `AGENTS.md`, `COURSE.md`, and `STATUS.md` are the other half, and they win where they are more specific.

## Starting a session

1. **Update thesisbug2 first:** run `./fw update` from the course root at the start of every agent session, then re-read this guide from the updated `.framework/`. This keeps shared instructions and tools current across agents and machines. The update may commit only the framework pin locally; it does not authorize a push. (A course whose `.gitmodules` sets `ignore = all` on the submodule has opted out of tracking the pin; there the update pulls and commits nothing.) If the update fails, report what failed and continue with the available checkout without resetting, stashing, or discarding local work. If the course's `AGENTS.md` already triggered the update this session, do not repeat it.
1. Read `COURSE.md` (who the instructor is, the citation style, what is graded) and `STATUS.md` (one line per unit).
1. If `COURSE.md` still has `[待完成]` slots, complete it before starting a unit: ask the author for the syllabus (a PDF or a link is enough; use an available PDF/text extraction tool and keep the transcript in `notes/`) and fill the instructor, institution, field, what is graded, and the course notes from it, then confirm what you filled. If extraction is unavailable, retain the unverified slots and report the missing capability. The installer cannot fill these — they come from the syllabus — and every later unit, and every review prompt, reads them from this file.
1. If the request names or implies a unit, read that unit's `WORK.json`, `PROGRESS.md` (where it is, what is open, what it waits on) and `DECISIONS.md` (the requirements and decisions in force) before doing anything else. **Do not read `CHANGELOG.md`, and do not `grep` it either** — an entry can be one line of several thousand characters, so a single hit returns kilobytes. Query it: `./fw log --find <keyword>` returns id, date, title and a short snippet per match (plus matching commit subjects), and `./fw log --show <id>` returns the one entry you need. The same goes for other long files — `refs/<key>.md` transcripts, review reports: grep, or read the section.
1. If the user's first message already says what they want, do that. Ask which unit only when the request could apply to more than one.

## Layout

```
<course>/
├── AGENTS.md  COURSE.md  STATUS.md
├── .framework/        # the framework — read it, run it, do not write coursework into it
├── library/           # references.bib + refs/ shared by two or more units
├── notes/             # lecture notes, transcripts, material that is not cited
└── units/NN-<type>-<topic>/     # one assignment: WORK.json, PROGRESS.md, the manuscript, references.bib, refs/
```

A **unit** is any directory containing `WORK.json`. Skills write unit paths as `<unit>/…` and shared paths as `library/…`.

## Commands

Run everything from the course root through the dispatcher:

```bash
./fw help                              # the commands that exist in this framework version
./fw <command> [<unit>] [options]      # e.g. ./fw check-citations units/03-paper-final
./fw update                            # pull the framework and commit the new pinned version
```

`<unit>` may be a path or a bare unit name. Without it, the unit is the nearest `WORK.json` above your working directory; from the course root `fw` lists the units and stops rather than guessing. A skill may name a command that this framework version does not have yet — `./fw help` is the truth, so say a gate was not run when its command is missing; never report it as passed.

## Skills

The canonical skills are `.framework/.agents/skills/<name>/SKILL.md`, also exposed through `.agents/skills/` and `.claude/skills/`. Use native skill discovery when available; otherwise read the relevant file directly. Names such as `/check_flow` are task aliases, not required slash-command APIs, so an agent without those APIs can follow the same procedure.

Use your environment's file, shell, browser, and delegation capabilities. External skills named below are integrations to discover and read before use, since they are not bundled here. Never assume a vendor home directory or install into the course's skill symlinks, because that would modify the framework submodule. If a capability is missing, finish independent checks and report what remains unverified. `flow-check` specifically requires an isolated reader for its cold read; `gpt-review` requires a suitable second model for a cross-model verdict.

**Image generation is the provider exception:** use Codex, the maintainer's current stable backend. A Codex host can use its native image tool; another host uses the discovered `genimage-img2` Codex wrapper. Report an unavailable backend instead of substituting another image provider. Supplied PNGs and authored HTML capture still work without AI generation.

| Stage | Skill |
| :--- | :--- |
| Choosing a topic | `topic-scout` |
| Finding, fetching, and auditing sources | `source-kit` |
| Multi-spot edits to manuscript text | `safe-edit` |
| Terminology (Traditional Chinese, Taiwan usage) | `fix-terms` |
| Argument flow and coherence | `flow-check` |
| Citation consistency | `cite-check` |
| External cross-model review, at milestones | `gpt-review` |
| Slide decks | `deck-svg` (live HTML) or `deck-image` (one image per slide), on `house-style` and `deck-runtime` |
| Figures, 字數, transcripts | `diagram`, `count-zh`, `yt2sub` |

Lint order for a manuscript: **fix-terms → flow-check → cite-check**, with gpt-review after that at milestones. Accepted findings land through safe-edit.

## Sources live in one of two tiers

A source's files exist in exactly one place: the unit that fetched it (`<unit>/refs/`, `<unit>/references.bib`) or, once a second unit wants it, `library/`. Look in `library/` and the other units before fetching anything; keys are unique across the course. `source-kit` has the full procedure, including the append-only audit logs (`refs/audit/<key>.jsonl`) and why a `support` verdict carries the unit's name while an `identity` verdict does not. The state machine is in `.framework/docs/bib-lifecycle.md`.

Raw originals (`*.pdf`, `*.epub`, `*.html`) are never committed. Transcripts and audit logs are.

## Status files are not a log

For a unit explicitly enrolled in the [experimental JSON workflow](workflow.md), `PROGRESS.md` and `DECISIONS.md` are generated views. Use `./fw todo <unit>`, `./fw decision <unit>`, and `./fw workflow <unit> context` to update their sources; finish with `./fw workflow <unit> handoff`. Read each command's `--help` before use. Do not edit generated views or read the entire `.workflow/` store, because that bypasses revision checks and reloads the history. Enrollment is explicit; neither framework updates nor unit creation migrate existing files.

`PROGRESS.md` and `DECISIONS.md` are read at the start of every session, so everything in them costs context each time and is taken as current. An agent's habit is to append a paragraph about what it just did; after a few weeks the live to-do list is a few lines under kilobytes of history, some of it no longer true, and the next agent believes it. So:

- **Finishing something removes it from the live list:** delete its line in a Markdown unit, or mark it done through `todo` in a JSON unit. Use `./fw log <unit> "one line"` only for a milestone worth finding later; completed items are history.
- **A changed rule replaces the current rule** in `DECISIONS.md`, or through `decision revise` in a JSON unit; preserve its predecessor and reason in the appropriate history first, because uncommitted intermediate decisions are not automatically saved by Git.
- **The story of a session goes in its commit messages.** Git already stores it, dated and scoped to the change; a second copy in a status file only rots.
- **Re-measure instead of keeping a number.** A word count or gate result in `PROGRESS.md` carries its date; when it is old, measure again.
- Run `./fw check-progress <unit>` before handoff even when there was no build, because research-only sessions can also accumulate stale state. `./fw build` checks it too, including HTML presentations. The gate checks size and formatting, plus JSON/view consistency when enabled; it cannot establish that a short statement is still true. `--sweep` is for ordinary Markdown units only.

## Communication contract

Each rule has a reason; apply the reason when a case is not listed.

- **Report from evidence.** Before writing a status line into `PROGRESS.md`, `STATUS.md`, a commit message, or a reply, check each claim against a command result or a file you saw this session. Say "not yet verified" where that is the truth. This is graded work: a confident but unverified "all citations backed" is worse than an honest gap, because nobody re-checks a claim that sounds finished.
- **Pause only where the author is genuinely needed:** a destructive or irreversible step (deleting unit content, force-push, rewriting an audit line), a real scope change, or a judgment only the author can make (which topic, whether a disputed claim stays in). Routine reversible steps that follow from the request — running a gate, fetching a source — need no permission. If a question comes up, finish everything that does not depend on the answer, then ask at the end of that turn.
- **Stay inside the request.** Something else worth fixing is a suggestion for the closing summary, not an edit. In manuscript text this matters doubly: unrequested rewording can detach a claim from its `[@key, locator]`.
- **A handed-in unit is frozen.** A later unit that builds on it copies the text it needs and records `"extends"` in its `WORK.json`; it never edits or live-includes the earlier unit, because that would change what already-graded work rebuilds to.
- **Write the closing summary for someone who did not watch.** Outcome first, then what you need from the author. Full sentences; re-introduce any label you coined while working.
- **Reply in the author's language.** Traditional Chinese output uses Taiwan usage; `fix-terms` has the rules.

## The framework directory

`.framework/` is a git submodule pinned to one commit, so a unit handed in last term still rebuilds the same way. Coursework never writes into it. If you find a framework bug while doing coursework, tell the author; when they want it fixed, make the change inside `.framework/` as its own commit, push it to the framework's remote, then `./fw update` in the course. Read `.framework/AGENTS.md` before editing the framework — it is a public repository and the course is private, so nothing from the course may be copied into it.

## Figures

SVG first. Author PlantUML source beside the manuscript and render with `./fw plantuml2svg <in>.plantuml <out>.svg`; commit both. Quarto embeds the SVG in PDF builds and decks embed it directly. Generated raster imagery is only for what SVG cannot express.

## Git

One branch, `main`. Commit coursework to the course repo as you go, one logical change per commit. Tag milestones as `<unit>/<label>`, for example `03-paper-final/draft-v1`. Push only when the author asks.
