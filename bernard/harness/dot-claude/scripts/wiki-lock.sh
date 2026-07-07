#!/usr/bin/env bash
# wiki-lock.sh — CLI for the shared wiki write-lock (see lib/wiki-lock.sh).
#
# Interactive agents take this lock during write-heavy work (ingest, synthesis,
# backlink rebuilds, multi-file edits) so the scheduled write jobs DEFER instead
# of rewriting files mid-session. Humans can inspect or force-clear it.
#
# Usage:
#   bash .claude/scripts/wiki-lock.sh acquire "ingest (claude session)"
#   bash .claude/scripts/wiki-lock.sh release
#   bash .claude/scripts/wiki-lock.sh status
#   bash .claude/scripts/wiki-lock.sh clean      # force-remove; only if no writer is active
#
# Exit codes: acquire -> 0 got it, 3 held by another. Others -> 0 ok, 2 usage.
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/lib/wiki-lock.sh"

cmd="${1:-status}"; shift || true
case "$cmd" in
  acquire)
    desc="${1:-interactive session}"
    if wiki_lock_acquire "$desc"; then
      echo "wiki-write lock ACQUIRED by '$desc' (TTL ${WIKI_LOCK_TTL}s)."
      echo "Release when done:  bash .claude/scripts/wiki-lock.sh release"
      exit 0
    else
      echo "wiki-write lock HELD by '$(wiki_lock_holder)' since $(wiki_lock_since) — NOT acquired." >&2
      echo "If you are sure no writer is active:  bash .claude/scripts/wiki-lock.sh clean" >&2
      exit 3
    fi ;;
  release)
    wiki_lock_release; echo "wiki-write lock released." ;;
  status)
    if wiki_lock_active; then
      echo "HELD by '$(wiki_lock_holder)' since $(wiki_lock_since)"
      echo "  (lock dir: $WIKI_LOCK_DIR, TTL ${WIKI_LOCK_TTL}s)"
    else
      echo "FREE — no fresh wiki-write lock held."
    fi ;;
  clean)
    wiki_lock_release; echo "wiki-write lock force-cleaned." ;;
  *)
    echo "usage: wiki-lock.sh {acquire [desc]|release|status|clean}" >&2; exit 2 ;;
esac
