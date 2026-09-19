#!/usr/bin/env bash
# thesisbug2 — create a course repository.
#
#   bash <(curl -fsSL https://raw.githubusercontent.com/enstw/thesisbug2/main/install.sh)
#   bash <(curl -fsSL …/install.sh) 1142-asia-pacific-security --title "亞太安全專題" --yes
#
# Checks what the course needs, then downloads and runs scripts/course-init.py,
# which asks for the course details, creates the local repo, mounts the
# framework as a submodule, writes the agent directives, and creates a private
# GitHub repository. Arguments are passed through; see `--help`.
set -euo pipefail

RAW="${THESISBUG2_RAW:-https://raw.githubusercontent.com/enstw/thesisbug2/main}"

say()  { printf '%s\n' "$*"; }
fail() { printf 'install: %s\n' "$*" >&2; exit 1; }

# Hard requirements: without these the course cannot be created at all.
command -v git     >/dev/null || fail "git is not installed."
command -v python3 >/dev/null || fail "python3 is not installed."
case " $* " in
  *" --no-github "*) ;;
  *) command -v gh >/dev/null || fail "GitHub CLI is not installed (brew install gh), or pass --no-github."
     gh auth status >/dev/null 2>&1 || fail "GitHub CLI is not logged in. Run: gh auth login" ;;
esac

# Soft requirements: the course is created either way, but builds and some
# gates will not run until these exist — say so now rather than at first build.
missing=()
command -v quarto       >/dev/null || missing+=("quarto        brew install quarto && quarto install tinytex")
command -v uv           >/dev/null || missing+=("uv            brew install uv")
command -v rsvg-convert >/dev/null || missing+=("librsvg       brew install librsvg")
if [ "${#missing[@]}" -gt 0 ]; then
  say "Not installed yet (needed later to build PDFs and run some checks):"
  for m in "${missing[@]}"; do say "  $m"; done
  say ""
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
curl -fsSL "$RAW/scripts/course-init.py" -o "$tmp/course-init.py" \
  || fail "could not download course-init.py from $RAW"

# Read answers from the terminal even when this script itself came through a pipe.
if [ -t 0 ] || [ ! -r /dev/tty ]; then
  python3 "$tmp/course-init.py" "$@"
else
  python3 "$tmp/course-init.py" "$@" < /dev/tty
fi
