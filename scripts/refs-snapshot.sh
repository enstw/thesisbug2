#!/usr/bin/env bash
# refs-snapshot — keep citation-source originals (*.pdf / *.epub / *.html) out of
# git and in a GitHub Release, pinned by a sha256 manifest that IS in git.
#
# One release per course repo (tag: refs). The manifest, library/refs/MANIFEST.tsv,
# covers both tiers — every units/*/refs/ and library/refs/ — with paths relative
# to the course root. A release asset is named after the file alone (<key>.pdf):
# keys are unique across the course, so promoting a source to library/ changes
# its path in the manifest but not its asset, and nothing is re-uploaded.
#
#   ./fw refs-snapshot push            upload new/changed originals, regenerate the manifest
#   ./fw refs-snapshot pull [pat...]   materialize originals locally (all, or paths matching pat)
#   ./fw refs-snapshot status          local tree vs manifest
#   ./fw refs-snapshot forget <path>   drop a manifest row on purpose (the asset stays)
#
# Requires: gh (authenticated), shasum. Compatible with macOS bash 3.2.
set -euo pipefail

REPO_ROOT="${FW_COURSE_ROOT:-$(git rev-parse --show-toplevel)}"
REFS_DIR="$REPO_ROOT"                       # manifest paths are relative to the course root
MANIFEST="$REPO_ROOT/library/refs/MANIFEST.tsv"

die() { echo "refs-snapshot: $*" >&2; exit 1; }
usage() { sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; }

# Asking for help must never reach a subcommand: `push --help` used to run a
# real push, uploading every new original and rewriting the manifest.
for arg in "$@"; do
  case "$arg" in -h|--help|help) usage; exit 0;; esac
done

command -v gh >/dev/null || die "gh CLI not found"
[ -d "$REPO_ROOT/units" ] || [ -d "$REPO_ROOT/library" ] || die "not a course repo: $REPO_ROOT"

# Scope: originals under any refs/ directory of either tier. Transcripts (*.md)
# and audit logs (audit/*.jsonl) stay in git and are not in scope.
scope_files() {
  ( cd "$REPO_ROOT" && find units library -type f -path '*/refs/*' \
      \( -name '*.pdf' -o -name '*.epub' -o -name '*.html' -o -name '*.htm' -o -name '*.docx' \) 2>/dev/null \
      | sort )
}

sha() { shasum -a 256 "$1" | awk '{print $1}'; }

# Asset name = the file's basename. Keys are unique across the course, so this
# cannot collide unless the same original sits in two places — which is the
# duplicate-source situation `./fw refs promote` exists to resolve.
encode() { basename "$1"; }

check_unique_assets() {
  local dup
  dup=$(scope_files | while read -r f; do basename "$f"; done | sort | uniq -d)
  [ -z "$dup" ] || die "the same original exists in two places: $dup — resolve with ./fw refs promote before pushing"
}

# Tag recorded in the manifest (what pull reads; what the last push targeted).
manifest_tag() {
  [ -f "$MANIFEST" ] || return 0
  awk -F'\t' '!/^#/ && NF>=4 {print $4; exit}' "$MANIFEST"
}

# One release per course repo. Override with REFS_SNAPSHOT_TAG.
resolve_tag() { echo "${REFS_SNAPSHOT_TAG:-refs}"; }

manifest_sha() {  # manifest_sha <relpath> → sha256 or empty
  [ -f "$MANIFEST" ] || return 0
  awk -F'\t' -v p="$1" '!/^#/ && $1==p {print $2; exit}' "$MANIFEST"
}

manifest_sha_by_name() {  # manifest_sha_by_name <basename> → sha256 or empty
  [ -f "$MANIFEST" ] || return 0
  awk -F'\t' -v n="$1" '!/^#/ { m=$1; sub(/.*\//,"",m); if (m==n) {print $2; exit} }' "$MANIFEST"
}

ensure_release() {
  local tag="$1"
  if ! gh release view "$tag" --json tagName >/dev/null 2>&1; then
    echo "creating release $tag"
    gh release create "$tag" --title "$tag" \
      --notes "Citation-source originals for this course — managed by ./fw refs-snapshot. Bytes are pinned by library/refs/MANIFEST.tsv in git; do not edit assets by hand." \
      >/dev/null
  fi
}

cmd_push() {
  [ $# -eq 0 ] || die "push takes no arguments (got: $*)"
  local tag old_tag; tag=$(resolve_tag); old_tag=$(manifest_tag)
  check_unique_assets
  ensure_release "$tag"
  local staging; staging=$(mktemp -d)
  # shellcheck disable=SC2064 — expand now: $staging is function-local
  trap "rm -rf '$staging'" EXIT
  local uploaded=0 skipped=0 rows="$staging/rows"
  : > "$rows"
  local rel h bytes
  for rel in $(scope_files); do
    h=$(sha "$REFS_DIR/$rel")
    bytes=$(stat -f%z "$REFS_DIR/$rel" 2>/dev/null || stat -c%s "$REFS_DIR/$rel")
    printf '%s\t%s\t%s\t%s\n' "$rel" "$h" "$bytes" "$tag" >> "$rows"
    # Skip when these bytes are already in THIS release under this asset name —
    # looked up by basename, so a promoted source (new path, same file) is not
    # uploaded again.
    if [ "$(manifest_sha_by_name "$(basename "$rel")")" = "$h" ] && [ "$old_tag" = "$tag" ]; then
      skipped=$((skipped+1))
      continue
    fi
    cp "$REFS_DIR/$rel" "$staging/$(encode "$rel")"
    echo "upload: $rel"
    gh release upload "$tag" "$staging/$(encode "$rel")" --clobber >/dev/null
    rm "$staging/$(encode "$rel")"
    uploaded=$((uploaded+1))
  done
  # Keep rows whose original is not on this machine. Originals are untracked,
  # so a clone that has not pulled every file is the normal case, and a missing
  # file says nothing about whether the source was dropped. Rebuilding from the
  # local tree alone used to delete those rows and orphan their release assets.
  # A promoted source is not missing (refs promote rewrites its path), and a
  # source dropped on purpose leaves through `forget`.
  local kept=0 mrel mrest
  if [ -f "$MANIFEST" ]; then
    while IFS=$'\t' read -r mrel mrest; do
      case "$mrel" in \#*|'') continue;; esac
      [ -f "$REFS_DIR/$mrel" ] && continue
      printf '%s\t%s\n' "$mrel" "$mrest" >> "$rows"
      kept=$((kept+1))
    done < "$MANIFEST"
  fi
  sort -t$'\t' -k1,1 -o "$rows" "$rows"
  {
    echo "# source-originals manifest for the whole course (paths relative to the course root) — bytes live in GitHub Release: $tag"
    echo "# managed by ./fw refs-snapshot; regenerate with: ./fw refs-snapshot push"
    printf '# %s\t%s\t%s\t%s\n' "path" "sha256" "bytes" "release"
    cat "$rows"
  } > "$staging/manifest"
  mkdir -p "$(dirname "$MANIFEST")"; mv "$staging/manifest" "$MANIFEST"
  echo "pushed: $uploaded uploaded, $skipped unchanged, $kept kept (not on this machine), manifest $(grep -cv '^#' "$MANIFEST") entries"
  echo "→ commit library/refs/MANIFEST.tsv if it changed"
}

cmd_pull() {
  local pat
  for pat in "$@"; do
    case "$pat" in -*) die "unknown option for pull: $pat";; esac
  done
  [ -f "$MANIFEST" ] || die "no manifest at library/refs/MANIFEST.tsv"
  local tmpdir; tmpdir=$(mktemp -d)
  # shellcheck disable=SC2064 — expand now: $tmpdir is function-local
  trap "rm -rf '$tmpdir'" EXIT
  local fetched=0 ok=0 failed=0
  while IFS=$'\t' read -r rel want bytes tag; do
    case "$rel" in \#*|'') continue;; esac
    if [ $# -gt 0 ]; then
      local hit=0
      for pat in "$@"; do case "$rel" in *"$pat"*) hit=1;; esac; done
      [ $hit -eq 1 ] || continue
    fi
    if [ -f "$REFS_DIR/$rel" ] && [ "$(sha "$REFS_DIR/$rel")" = "$want" ]; then
      ok=$((ok+1)); continue
    fi
    local asset; asset=$(encode "$rel")
    echo "fetch: $rel  (from $tag)"
    rm -f "$tmpdir/$asset"
    if ! gh release download "$tag" --pattern "$asset" --dir "$tmpdir" 2>/dev/null; then
      echo "  ERROR: asset $asset not found in release $tag" >&2; failed=$((failed+1)); continue
    fi
    if [ "$(sha "$tmpdir/$asset")" != "$want" ]; then
      echo "  ERROR: sha256 mismatch for $rel — refusing to install" >&2; failed=$((failed+1)); continue
    fi
    mkdir -p "$REFS_DIR/$(dirname "$rel")"
    mv "$tmpdir/$asset" "$REFS_DIR/$rel"
    fetched=$((fetched+1))
  done < "$MANIFEST"
  echo "pull: $fetched fetched, $ok already present, $failed failed"
  [ $failed -eq 0 ] || exit 1
}

cmd_forget() {
  [ $# -gt 0 ] || die "forget needs the manifest path of each source to drop"
  [ -f "$MANIFEST" ] || die "no manifest at library/refs/MANIFEST.tsv"
  local rel
  for rel in "$@"; do
    awk -F'\t' -v p="$rel" '!/^#/ && $1==p {f=1} END {exit !f}' "$MANIFEST" \
      || die "not in manifest: $rel"
  done
  local tmp list; tmp=$(mktemp); list=$(mktemp)
  printf '%s\n' "$@" > "$list"
  awk -F'\t' 'NR == FNR { drop[$0] = 1; next } /^#/ || !($1 in drop)' "$list" "$MANIFEST" > "$tmp"
  rm -f "$list"; mv "$tmp" "$MANIFEST"
  for rel in "$@"; do echo "forgot: $rel  (release asset kept)"; done
  echo "→ commit library/refs/MANIFEST.tsv"
}

cmd_status() {
  [ $# -eq 0 ] || die "status takes no arguments (got: $*)"
  [ -f "$MANIFEST" ] || die "no manifest at library/refs/MANIFEST.tsv (run push first)"
  local missing=0 modified=0 ok=0
  while IFS=$'\t' read -r rel want bytes tag; do
    case "$rel" in \#*|'') continue;; esac
    if [ ! -f "$REFS_DIR/$rel" ]; then
      echo "missing:  $rel"; missing=$((missing+1))
    elif [ "$(sha "$REFS_DIR/$rel")" != "$want" ]; then
      echo "MODIFIED: $rel  (sources are immutable — investigate)"; modified=$((modified+1))
    else
      ok=$((ok+1))
    fi
  done < "$MANIFEST"
  local rel
  for rel in $(scope_files); do
    if [ -z "$(manifest_sha "$rel")" ]; then
      echo "new:      $rel  (not in manifest — run push)"
    fi
  done
  echo "status: $ok ok, $missing missing (pull to fetch), $modified modified"
}

case "${1:-}" in
  push)   shift; cmd_push "$@";;
  pull)   shift; cmd_pull "$@";;
  status) shift; cmd_status "$@";;
  forget) shift; cmd_forget "$@";;
  *) usage; exit 2;;
esac
