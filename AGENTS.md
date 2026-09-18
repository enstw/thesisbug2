# AGENTS.md

thesisbug2 is an AI-agent framework for Traditional Chinese academic coursework. It is mounted as a git submodule at `.framework/` inside one private repository per course. This repository is the framework only; it never contains coursework.

## Current state

The repository is at the design stage. [`docs/DESIGN.md`](docs/DESIGN.md) is the source of truth for the architecture and for what is decided versus open. No skills, scripts, or templates have been ported yet. Read the design document before proposing or making changes.

The predecessor is `thesisbug-template` (private), usually checked out beside this repo at `../thesisbug-template`. Skills, scripts, and templates are ported from there.

## Rules for working in this repository

- **This repo is public; the predecessor is private.** Before copying anything in, clear it against `docs/DESIGN.md` § Audit required before each port. Personal context, coursework content, thesis-specific wording, and fonts or images without redistribution rights stay out. Port by copying files into new commits; never import the predecessor's git history, because its work branches contain private coursework.
- **Keep coursework paths out of the framework.** Framework code locates a unit by walking up to the nearest `WORK.json` and reads shared sources from the course's `library/`. A hard-coded `work/` path is a bug here.
- **Update the design document with the change.** When a decision in `docs/DESIGN.md` changes, edit the document in the same commit, so the design and the code cannot drift apart.
- **Explain rules when you add them.** An instruction added to a skill, a protocol, or this file carries its reason in the same sentence. Current models follow instructions literally and generalise from the reason; a bare prohibition gets applied too broadly or too narrowly.
- **Skill descriptions stay at roughly 300–500 characters**, third person, stating what the skill does and when to use it. Every agent loads all descriptions at startup, and long ones get truncated at a point the author did not choose. The hard limit is 1,024.
- **Diagrams are Mermaid** in fenced blocks inside the Markdown, so the rendered diagram cannot drift from its source.
