# AGENTS.md

thesisbug2 is an AI-agent framework for Traditional Chinese academic coursework. It is mounted as a git submodule at `.framework/` inside one private repository per course. This repository is the framework only; it never contains coursework.

## Current state

[`docs/DESIGN.md`](docs/DESIGN.md) is the source of truth for the architecture and for what is decided. Read it before proposing or making changes.

What exists so far:

- **The 15 agent skills** are ported into `.agents/skills/`, rewritten for the course layout: unit paths are written `<unit>/…`, shared sources `library/…`, and every command is `./fw <command>`. They were cleared against the public-port audit (thesis-specific values replaced with slots to fill; the font ships with its OFL text).
- **`scripts/fw` and the gates behind it** work: `apply-edits`, `check-bib`, `check-citations`, `check-zh-variants`, `count-zh`, `lint-readability`, `plantuml2svg`, `yt2sub`. `scripts/_paths.py` is the only place that knows the course layout (course root, nearest `WORK.json`, `library/`); a script that builds such a path itself is a bug. A script that needs third-party packages declares them in a PEP 723 header and `fw` runs it under `uv`; the rest use the standard library only.
- **Not here yet:** `unit-init`, `build`, `refs` (promote), `refs-snapshot`, `course-init`, and the Quarto templates. Skills already name some of these (`./fw build`, `./fw refs promote`), so do not report one as run until `./fw help` lists it. The roadmap in `docs/DESIGN.md` gives the order.

To try a script without a real course, make a scratch directory with `units/<name>/WORK.json`, symlink this repo in as `.framework`, and add the two-line `fw` shim (`exec "$(dirname "$0")/.framework/scripts/fw" "$@"`).

### Skill evals

`flow-check`, `source-kit`, and `safe-edit` carry `evals/evals.json` (three scenarios each: a query, fixture files, expected behaviours) and invented fixtures with planted defects, described in each `evals/fixtures/README.md`. There is no runner. To check a skill after editing it, build a scratch course repo, copy the fixture in as `units/01-paper-eval/`, copy `.agents/skills/` in **without any `evals/` directory** (leaving it in hands the agent the answers), give a fresh-context agent only the query, and compare what it did — and what `git status` in the scratch repo shows — with `expected_behavior`. Add a scenario when a real session shows a skill failing, rather than guessing at failures in advance.

The predecessor is `thesisbug-template` (private), usually checked out beside this repo at `../thesisbug-template`. Skills, scripts, and templates are ported from there.

## Rules for working in this repository

- **This repo is public; the predecessor is private.** Before copying anything in, clear it against `docs/DESIGN.md` § Audit required before each port. Personal context, coursework content, thesis-specific wording, and fonts or images without redistribution rights stay out. Port by copying files into new commits; never import the predecessor's git history, because its work branches contain private coursework.
- **Keep coursework paths out of the framework.** Framework code locates a unit by walking up to the nearest `WORK.json` and reads shared sources from the course's `library/`. A hard-coded `work/` path is a bug here.
- **Update the design document with the change.** When a decision in `docs/DESIGN.md` changes, edit the document in the same commit, so the design and the code cannot drift apart.
- **Explain rules when you add them.** An instruction added to a skill, a protocol, or this file carries its reason in the same sentence. Current models follow instructions literally and generalise from the reason; a bare prohibition gets applied too broadly or too narrowly.
- **Skill descriptions stay at roughly 300–500 characters**, third person, stating what the skill does and when to use it. Every agent loads all descriptions at startup, and long ones get truncated at a point the author did not choose. The hard limit is 1,024.
- **Diagrams are Mermaid** in fenced blocks inside the Markdown, so the rendered diagram cannot drift from its source.
