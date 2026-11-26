#!/bin/bash
# Model-less maintenance runner for com.theborg.c4po-git-icon-sweep.
#
# ~/theborg is a Google Drive MIRROR root, and Drive syncs Finder custom-folder
# icons as `Icon\r` files (an empty data fork; the image lives in the resource
# fork). On 2026-10-26 Drive downloaded 238 of them into .git, plus more in each
# repos/*/.git. Git reads every name under .git/refs as a ref, so
# `.git/refs/Icon\r` broke fetch with "fatal: bad object refs/Icon?".
#
# Drive can deliver them again at any time, and nothing in Drive excludes a
# subdirectory of a mirror root, so the guard is a frequent sweep rather than a
# one-time cleanup. Deleting in a mirror root also deletes the cloud copy, so
# a sweep does not fight Drive in a loop unless something re-creates them.
#
# Scope is deliberately narrow: only regular, empty files named exactly
# `Icon<CR>`, only inside the workspace .git and repos/*/.git. Working-tree Icon
# files are left alone (untracked noise, not corruption).
#
# A removal from a refs directory (`<git dir>/refs/` or a linked worktree's
# `<git dir>/worktrees/<name>/refs/`) is logged by path on its own line: that is
# the case that breaks fetch until the next sweep, so the log says where it
# landed rather than only counting it. Reflog copies under `logs/refs/` count as
# ordinary removals.
set -uo pipefail

BORG_ROOT="${BORG_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
LOG="$BORG_ROOT/c4po/.claude/scheduled/logs/c4po-git-icon-sweep.log"
ICON=$'Icon\r'

git_dirs=("$BORG_ROOT/.git")
shopt -s nullglob
for d in "$BORG_ROOT"/repos/*/.git; do
  [[ -d "$d" ]] && git_dirs+=("$d")
done
shopt -u nullglob

removed=0
refs_removed=0
failed=0
for gd in "${git_dirs[@]}"; do
  [[ -d "$gd" ]] || continue
  while IFS= read -r -d '' f; do
    if rm -f -- "$f"; then
      removed=$((removed + 1))
      case "$f" in
        "$gd"/refs/*|"$gd"/worktrees/*/refs/*)
          refs_removed=$((refs_removed + 1))
          echo "$(date '+%F %T') removed from refs: ${f#"$BORG_ROOT"/}" | tr -d '\r' >> "$LOG"
          ;;
      esac
    else
      failed=$((failed + 1))
      echo "$(date '+%F %T') failed to remove: $f" >> "$LOG"
    fi
  done < <(find "$gd" -type f -name "$ICON" -size 0 -print0 2>/dev/null)
done

# Log only when there was something to do, so a 15-minute cadence does not
# grow the log with no-op lines.
if (( removed > 0 )); then
  echo "$(date '+%F %T') removed $removed Icon file(s) from ${#git_dirs[@]} git dir(s), $refs_removed from refs" >> "$LOG"
fi
(( failed == 0 ))
