#!/usr/bin/env python3
"""Create a course repository that mounts the thesisbug2 framework.

    course-init.py [<slug>] [options]

Asks for whatever it was not given (when run in a terminal), then:

  1. creates <parent>/<slug>/ and `git init`s it
  2. mounts the framework as a shallow git submodule at .framework/
  3. writes the course skeleton — AGENTS.md, COURSE.md, STATUS.md,
     .gitignore, ./fw, library/, notes/, units/ — with your answers filled in
  4. sets up the agent directives: CLAUDE.md / GEMINI.md pointers, and
     .claude/skills + .agents/skills symlinked into the framework's skills
  5. commits, creates a PRIVATE GitHub repository, pushes, and tags it with
     the `thesisbug-course` topic

Standard library only, so it can run before anything is installed:
install.sh downloads and runs this file. Every prompt has a flag, so an agent
can run it non-interactively (pass --yes to accept defaults for the rest).
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

FRAMEWORK_URL = "https://github.com/enstw/thesisbug2.git"
TOPIC = "thesisbug-course"
CITATIONS = ("apa", "apa-zh", "chicago-fullnote")
POINTER = "See [AGENTS.md](AGENTS.md).\n"


def run(cmd: list[str], cwd: Path | None = None, check: bool = True, quiet: bool = False):
    r = subprocess.run(cmd, cwd=cwd, text=True, capture_output=quiet)
    if check and r.returncode:
        if quiet:
            sys.stderr.write(r.stdout + r.stderr)
        sys.exit(f"failed: {' '.join(cmd)}")
    return r


def ask(label: str, default: str = "", choices: tuple[str, ...] = ()) -> str:
    hint = f" ({'/'.join(choices)})" if choices else ""
    shown = f" [{default}]" if default else ""
    while True:
        try:
            value = input(f"{label}{hint}{shown}: ").strip() or default
        except EOFError:
            sys.exit("\nno terminal to ask on — pass the value as a flag, or --yes for defaults")
        if not choices or value in choices:
            return value
        print(f"  choose one of: {', '.join(choices)}")


def gh_user() -> str | None:
    if not shutil.which("gh"):
        return None
    r = run(["gh", "api", "user", "-q", ".login"], check=False, quiet=True)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def main() -> None:
    ap = argparse.ArgumentParser(description="Create a course repo on the thesisbug2 framework.")
    ap.add_argument("slug", nargs="?", help="directory and GitHub repo name, e.g. 1142-asia-pacific-security")
    ap.add_argument("--title", help="course name as people say it, e.g. 亞太安全專題")
    ap.add_argument("--term", help="e.g. 114 學年度第 2 學期")
    ap.add_argument("--instructor")
    ap.add_argument("--author", help="your name as it should appear on submitted work")
    ap.add_argument("--institution", help="institution / programme")
    ap.add_argument("--field", help="discipline, used by review prompts, e.g. 國際關係")
    ap.add_argument("--citation", choices=CITATIONS)
    ap.add_argument("--parent", help="where to create the course directory (default: ~/homework)")
    ap.add_argument("--owner", help="GitHub owner (default: the authenticated gh user)")
    ap.add_argument("--no-github", action="store_true", help="create the local repo only")
    ap.add_argument("--framework-url", default=FRAMEWORK_URL, help=argparse.SUPPRESS)
    ap.add_argument("--yes", action="store_true", help="don't prompt; use defaults for anything not given")
    a = ap.parse_args()

    interactive = sys.stdin.isatty() and not a.yes

    def field(value: str | None, label: str, default: str = "", choices: tuple[str, ...] = ()) -> str:
        if value:
            return value
        return ask(label, default, choices) if interactive else default

    # ── preflight ────────────────────────────────────────────────────────────
    if not shutil.which("git"):
        sys.exit("git is not installed")
    user = None
    if not a.no_github:
        user = gh_user()
        if not user:
            sys.exit("GitHub CLI is not installed or not logged in. Run `gh auth login` first, "
                     "or pass --no-github to create the course locally only.")

    # ── 1. the fields ────────────────────────────────────────────────────────
    slug = field(a.slug, "Course slug — directory and repo name, e.g. 1142-asia-pacific-security")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", slug or ""):
        sys.exit("the slug must be lowercase ASCII letters, digits, '-', '.', '_' — it becomes a "
                 "directory name, a GitHub repo name, and part of every path in the course")
    title = field(a.title, "Course name", slug)
    term = field(a.term, "Term", "")
    instructor = field(a.instructor, "Instructor", "")
    default_author = run(["git", "config", "user.name"], check=False, quiet=True).stdout.strip()
    author = field(a.author, "Your name on submitted work", default_author)
    institution = field(a.institution, "Institution / programme", "")
    discipline = field(a.field, "Field (for review prompts)", "")
    citation = field(a.citation, "Citation style", "apa", CITATIONS)
    parent = Path(field(a.parent, "Create it under", "~/homework")).expanduser()
    owner = a.owner or user

    course = parent / slug
    if course.exists():
        sys.exit(f"{course} already exists")
    if owner and run(["gh", "repo", "view", f"{owner}/{slug}"], check=False, quiet=True).returncode == 0:
        sys.exit(f"GitHub already has {owner}/{slug} — pick another slug")

    # ── 2. local repo + framework submodule ──────────────────────────────────
    course.mkdir(parents=True)
    run(["git", "init", "-q", "-b", "main"], cwd=course)
    print(f"mounting the framework at {course}/.framework …")
    # Shallow: every course clones the framework, and its history (fonts
    # included) would otherwise be paid for once per course.
    local = not a.framework_url.startswith(("http://", "https://", "git@", "ssh://"))
    allow = ["-c", "protocol.file.allow=always"] if local else []
    run(["git", *allow, "submodule", "add", "--depth", "1", a.framework_url, ".framework"],
        cwd=course, quiet=True)
    run(["git", "config", "-f", ".gitmodules", "submodule..framework.shallow", "true"], cwd=course)
    # An ordinary `git pull` of the course then also moves .framework/ to the
    # commit the course pins.
    run(["git", "config", "submodule.recurse", "true"], cwd=course)

    # ── 3. skeleton ──────────────────────────────────────────────────────────
    skeleton = course / ".framework" / "assets" / "course-skeleton"
    if not skeleton.is_dir():
        sys.exit(f"the framework at {a.framework_url} has no assets/course-skeleton/")
    todo = "[待完成]"
    values = {"{{COURSE}}": title}
    course_rows = {
        "| Term |": term, "| Instructor |": instructor, "| Author |": author,
        "| Institution / programme |": institution, "| Field |": discipline,
        "| Citation style |": f"`{citation}`",
    }
    for name in ("AGENTS.md", "COURSE.md", "STATUS.md"):
        text = (skeleton / name).read_text(encoding="utf-8")
        for token, value in values.items():
            text = text.replace(token, value)
        if name == "COURSE.md":
            lines = []
            for line in text.splitlines():
                for prefix, value in course_rows.items():
                    if line.startswith(prefix) and value:
                        line = f"{prefix} {value} |"
                lines.append(line)
            text = "\n".join(lines) + "\n"
        (course / name).write_text(text, encoding="utf-8")
    shutil.copy2(skeleton / "gitignore", course / ".gitignore")
    shutil.copy2(skeleton / "fw", course / "fw")
    os.chmod(course / "fw", 0o755)
    for d in ("library/refs", "notes", "units"):
        (course / d).mkdir(parents=True)
        (course / d / ".gitkeep").touch()

    # ── 4. agent directives ──────────────────────────────────────────────────
    # AGENTS.md is canonical; per-agent files only point at it. Both skill
    # directories are symlinks into the submodule, so a framework update
    # updates every agent's skills at once.
    (course / "CLAUDE.md").write_text(POINTER, encoding="utf-8")
    (course / "GEMINI.md").write_text(POINTER, encoding="utf-8")
    for agent_dir in (".claude", ".agents"):
        (course / agent_dir).mkdir()
        os.symlink("../.framework/.agents/skills", course / agent_dir / "skills")

    # ── 5. commit, GitHub ────────────────────────────────────────────────────
    run(["git", "add", "-A"], cwd=course)
    run(["git", "commit", "-q", "-m", f"init: course {slug} on thesisbug2"], cwd=course)
    url = None
    if not a.no_github:
        print(f"creating private GitHub repo {owner}/{slug} …")
        desc = f"{title} — coursework ({term})" if term else f"{title} — coursework"
        run(["gh", "repo", "create", f"{owner}/{slug}", "--private", "--source", ".",
             "--remote", "origin", "--push", "--description", desc], cwd=course, quiet=True)
        run(["gh", "repo", "edit", f"{owner}/{slug}", "--add-topic", TOPIC], cwd=course,
            check=False, quiet=True)
        url = f"https://github.com/{owner}/{slug}"

    blanks = (course / "COURSE.md").read_text(encoding="utf-8").count(todo)
    print(f"""
done — {course}
{('GitHub:  ' + url + '  (private)') if url else 'GitHub:  skipped (--no-github)'}

next:
  cd {course}
  {'fill the ' + str(blanks) + ' remaining [待完成] slots in COURSE.md' if blanks else 'review COURSE.md'}
  ./fw unit-init --type paper --name <short-name> --title "…" --author "{author or '…'}"
  start your agent here — it reads AGENTS.md first

created {dt.date.today().isoformat()} · framework pinned at {run(['git', '-C', '.framework', 'rev-parse', '--short', 'HEAD'], cwd=course, quiet=True).stdout.strip()}""")


if __name__ == "__main__":
    main()
