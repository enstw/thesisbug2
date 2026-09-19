![thesisbug2](.github/banner.png)

# thesisbug2

AI-agent framework for Traditional Chinese academic coursework — one repo per course, shared skills, audited sources.

> **Status: early port.** The architecture in [`docs/DESIGN.md`](docs/DESIGN.md) is settled, the 15 agent skills are in `.agents/skills/`, and `scripts/` has the `fw` dispatcher, `unit-init`, `build`, and the checking gates, with the Quarto templates in `assets/templates/`. Everything a skill names now exists; what remains is a first real course. The [roadmap](#roadmap) shows what exists.

## What it is

thesisbug2 is the working environment an AI coding agent (Claude Code, Codex, Antigravity) needs to help write graded academic work in Traditional Chinese: Quarto/XeLaTeX templates for papers, journal articles, theses, homework, and slide decks; agent skills for choosing a topic, acquiring and auditing sources, checking citations, terminology, and argument flow, and getting an external review; and gates that fail the build when a citation is not backed by a verified local full text.

It is the second generation of a private template that modelled each piece of coursework as a git branch of the template itself. That design meant cherry-picking every framework fix into every live branch, left successive assignments of one course unrelated to each other, and mixed framework files with coursework. thesisbug2 splits the two:

```mermaid
flowchart LR
    F["thesisbug2<br>framework (public)"]
    C["one private repo per course"]
    U["units/01-homework …<br>units/02-presentation …<br>units/03-paper …"]
    L["library/<br>sources shared across units"]
    F -- "submodule at .framework/" --> C
    C --> U
    C --> L
```

- **The framework is this repository.** A course mounts it as a git submodule at `.framework/`. Updating is a pull; coursework never writes into it, so an update cannot conflict with your writing.
- **One repository per course.** Every assignment is a *unit* directory under `units/`. Units of the same course share a source `library/`, so a source fetched and audited for the midterm is ready for the final.
- **The framework version is pinned per course.** A unit handed in last semester still rebuilds to the same PDF.

## Install

### Requirements

| Tool | Why | macOS |
| :--- | :--- | :--- |
| git, [GitHub CLI](https://cli.github.com/) (`gh auth login` done) | course repos are private GitHub repositories | `brew install git gh` |
| [Quarto](https://quarto.org/) + TinyTeX | PDF builds through XeLaTeX | `brew install quarto && quarto install tinytex` |
| librsvg | embeds SVG figures in PDF output | `brew install librsvg` |
| [uv](https://docs.astral.sh/uv/) | runs the Python scripts and their dependencies without a manual venv | `brew install uv` |
| An agent CLI: Claude Code, Codex, or Antigravity | the skills are written for these | see each vendor |

macOS and Linux only. Course repos rely on symlinks committed to git, which Windows handles only in developer mode, so Windows is not supported.

### Create a course

With the GitHub CLI logged in (`gh auth login`), one command creates a course:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/enstw/thesisbug2/main/install.sh)
```

It asks for the course details, then does the rest:

1. **Collects the fields** — course slug (directory and repo name, e.g. `1142-asia-pacific-security`), course name, term, instructor, your name as it appears on submitted work, institution, field, and citation style (`apa`, `apa-zh`, `chicago-fullnote`).
1. **Creates the repository** — `~/homework/<slug>/`, `git init`, first commit, then a **private** GitHub repository under your account, pushed and tagged with the `thesisbug-course` topic.
1. **Mounts the framework** — this repository as a shallow git submodule at `.framework/`, with `submodule.recurse` on so a plain `git pull` keeps it at the version the course pins.
1. **Sets up the agent directives** — `AGENTS.md` (pointing agents at the framework's guide, `COURSE.md`, and `STATUS.md`), `CLAUDE.md` and `GEMINI.md` pointers, and `.claude/skills` + `.agents/skills` linked to the framework's skills, plus `COURSE.md`, `STATUS.md`, `./fw`, `library/`, `notes/`, `units/`.

Every question has a flag, so an agent or a script can run it without prompts:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/enstw/thesisbug2/main/install.sh) \
  1142-asia-pacific-security --title "亞太安全專題" --term "114-2" \
  --author "Your Name" --field "國際關係" --citation apa-zh --yes
```

`--no-github` creates the course locally only; `--parent <dir>` puts it somewhere other than `~/homework`; `--help` lists the rest. Already have the framework cloned? `scripts/course-init.py` is the same program.

### Start a unit

```bash
cd ~/homework/1142-asia-pacific-security
./fw unit-init --type paper --name final --title "…" --author "…"     # add --citation apa-zh for APA-zh-TW
./fw build final                                                        # → _output/NN-paper-final.pdf
```

Types: `preparation`, `homework`, `paper`, `journal`, `thesis`, `presentation` (`--variant thesis|reading-guide`). `unit-init` runs one build so you know the unit renders before you start writing.

### Update the framework inside a course

```bash
./fw update        # pulls .framework/ and commits the new pinned version
```

### Clone a course on another machine

```bash
git clone --recurse-submodules https://github.com/<you>/1142-asia-pacific-security
```

This one works with plain git today: the submodule brings the framework back at the pinned version.

## Course repository layout

```
<course>/
├── AGENTS.md          # course context; points agents at .framework/AGENTS.md
├── COURSE.md          # instructor, citation style, requirements, schedule
├── STATUS.md          # one line per unit
├── .framework/        # this repository, as a submodule
├── library/           # references.bib + refs/ shared by two or more units
├── notes/             # lecture notes, transcripts
└── units/
    ├── 01-homework-<topic>/
    ├── 02-presentation-<topic>/
    └── 03-paper-<topic>/      # WORK.json, PROGRESS.md, paper.qmd, references.bib, refs/
```

A new source lands in the unit that fetched it. When a second unit wants to cite it, `refs promote <key>` moves it, with its audit history, into `library/`. The full rules are in [`docs/DESIGN.md`](docs/DESIGN.md) § Sources.

## Roadmap

- [x] Architecture written down — [`docs/DESIGN.md`](docs/DESIGN.md)
- [x] Design reviewed and settled
- [x] Agent skills ported and cleared for publication
- [x] Quarto templates, CSL files, fonts ported
- [x] Writing protocols ported, generalised — identity and field come from the course's `COURSE.md`
- [x] `fw` dispatcher and the gates: citations and source backing across both tiers, batch edits, readability, 簡繁 variants, 字數
- [x] `unit-init` and `build` (two-tier bibliography, APA-zh 中文／西文 grouping by `langid`)
- [x] `install.sh` / `course-init`: one command from nothing to a private course repo with the framework mounted
- [x] `refs where` / `refs promote`, `refs-snapshot` (push and pull not yet exercised against a real release)
- [ ] First real course run on the framework

## Contributing

Issues and pull requests are welcome. The architecture and its reasons are in [`docs/DESIGN.md`](docs/DESIGN.md); agents working on the framework start from [`AGENTS.md`](AGENTS.md).

## License

MIT — see [`LICENSE`](LICENSE), with two exceptions that keep their own licenses: the bundled ENS Font is under the SIL Open Font License 1.1 ([`OFL.txt`](.agents/skills/house-style/assets/fonts/OFL.txt) beside the font files), and citation style files, once ported, remain CC-BY-SA as stated in each file's header.
