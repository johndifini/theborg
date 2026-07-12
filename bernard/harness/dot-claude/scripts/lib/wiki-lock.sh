#!/usr/bin/env bash
# lib/wiki-lock.sh — shared advisory write-lock for the life-wiki working tree.
#
# Sourced by the write-capable scheduled jobs (daily-synthesis, daily-ingest-check,
# build-backlinks --apply) and exposed to interactive agents/humans via the CLI
# wrapper scripts/wiki-lock.sh. Purpose: stop two writers — cron-vs-session or
# agent-vs-agent — from rewriting wiki files at the same moment and corrupting the
# shared git index (the failure that swept an in-progress session into another's
# commit on 2026-06-15).
#
# Properties:
#   - Advisory, single-machine, single-user. NOT a kernel lock.
#   - Atomic acquire via mkdir (POSIX-atomic; no flock dependency — macOS-safe).
#   - Time-based staleness (TTL): a forgotten interactive hold frees itself after
#     WIKI_LOCK_TTL; harness-health also sweeps stale locks. NOT pid-based, because
#     interactive agents take the lock via a transient CLI call whose pid dies
#     immediately (the recorded pid is informational only).
#   - It does NOT stop a raw `git commit` typed in another terminal. The companion
#     defense for that is the explicit-path-staging hard rule in CLAUDE.md.
#
# Public API (source this file, then call):
#   wiki_lock_acquire "<holder desc>"   -> 0 acquired, 1 held by another fresh holder
#   wiki_lock_release                   -> always 0 (idempotent)
#   wiki_lock_active                    -> 0 held(fresh), 1 free; reclaims stale as a side effect
#   wiki_lock_holder / wiki_lock_since  -> echo metadata of the current holder

# Resolve the wiki root from this file's own location:
#   .../life-wiki/.claude/scripts/lib/wiki-lock.sh -> up 3 -> .../life-wiki
_WL_LIB="${BASH_SOURCE[0]}"
WIKI_LOCK_ROOT="${WIKI_LOCK_ROOT:-$(cd "$(dirname "$_WL_LIB")/../../.." && pwd)}"
WIKI_LOCK_DIR="${WIKI_LOCK_DIR:-$WIKI_LOCK_ROOT/.claude/tmp/wiki-write.lock}"
WIKI_LOCK_TTL="${WIKI_LOCK_TTL:-7200}"   # 2 h — generous; covers a long interactive ingest

_wl_now()   { date +%s; }
_wl_mtime() { stat -f %m "$1" 2>/dev/null || echo 0; }

# Stale = lock dir absent, or older than the TTL. (Returns 0 = stale.)
_wl_is_stale() {
  [[ -d "$WIKI_LOCK_DIR" ]] || return 0
  local age=$(( $(_wl_now) - $(_wl_mtime "$WIKI_LOCK_DIR") ))
  (( age > WIKI_LOCK_TTL ))
}

# Is a fresh lock currently held? Side effect: reclaims (removes) a stale lock.
wiki_lock_active() {
  [[ -d "$WIKI_LOCK_DIR" ]] || return 1
  if _wl_is_stale; then rm -rf "$WIKI_LOCK_DIR" 2>/dev/null || true; return 1; fi
  return 0
}

wiki_lock_holder() { cat "$WIKI_LOCK_DIR/holder" 2>/dev/null || echo "unknown"; }
wiki_lock_since()  { cat "$WIKI_LOCK_DIR/ts"     2>/dev/null || echo "unknown"; }

# Acquire. arg1 = holder description. Returns 0 on success, 1 if held by another.
wiki_lock_acquire() {
  local holder="${1:-unknown}"
  mkdir -p "$WIKI_LOCK_ROOT/.claude/tmp" 2>/dev/null || true
  # Reclaim a stale lock first so the mkdir below can win (no-op if fresh/free).
  if _wl_is_stale; then rm -rf "$WIKI_LOCK_DIR" 2>/dev/null || true; fi
  if mkdir "$WIKI_LOCK_DIR" 2>/dev/null; then
    printf '%s\n' "$$"                           > "$WIKI_LOCK_DIR/pid"    2>/dev/null || true
    printf '%s\n' "$holder"                      > "$WIKI_LOCK_DIR/holder" 2>/dev/null || true
    printf '%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" > "$WIKI_LOCK_DIR/ts"     2>/dev/null || true
    return 0
  fi
  return 1   # already held by a fresh holder
}

wiki_lock_release() { rm -rf "$WIKI_LOCK_DIR" 2>/dev/null || true; return 0; }
