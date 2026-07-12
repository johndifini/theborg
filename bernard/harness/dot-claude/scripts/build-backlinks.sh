#!/usr/bin/env bash
# build-backlinks.sh — recommendation ①: backlink + timeline-spine builder.
#
# Fixes the measured traversal gap: ~115/177 journal entries had zero inbound
# links, so Bernard (who walks in-file [[wikilinks]], not GBrain) could not reach
# them. This injects a managed "## Mentioned In" body-link section into every
# entity page and (re)builds wikis/health/wiki/timeline.md — both plain markdown,
# so they reach the mirror. Pure-mechanical, deterministic, idempotent: no model.
#
# Default = dry-run (safe to run anytime). --apply writes, reindexes GBrain so the
# new body links become graph edges, and (with --sync) refreshes the mirror.
# Scheduled idea: daily, after daily-ingest. Manual: bash .claude/scripts/build-backlinks.sh --apply
set -uo pipefail

WIKI="/Users/lashawsalta/life-wiki"
LOGDIR="$WIKI/.claude/logs"
PY="$WIKI/.claude/scripts/lib/backlink_timeline.py"
TIMELINE="$WIKI/wikis/health/wiki/timeline.md"
GBRAIN="$WIKI/.claude/scripts/gbrain"
mkdir -p "$LOGDIR"
source "$WIKI/.claude/scripts/lib/wikilog.sh"
wikilog_open "build-backlinks"
LOG="$WIKILOG_BUF"
trap 'wikilog_flush' EXIT

APPLY=0; SYNC=0
for a in "$@"; do
  case "$a" in
    --apply) APPLY=1 ;;
    --sync)  SYNC=1 ;;
    *) echo "unknown arg: $a" >&2; exit 2 ;;
  esac
done

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }
notify() { /usr/bin/osascript -e "display notification \"$1\" with title \"Life Wiki Backlinks\" sound name \"Ping\"" 2>/dev/null || true; }

log "=== build-backlinks started (apply=$APPLY sync=$SYNC) ==="

# Shared write-lock — only for --apply, which rewrites pages. Supersedes the old
# pgrep-based synthesis guard: now defers for ANY writer (sibling jobs AND
# interactive sessions), not just a running synthesis pass. Dry-run needs no lock.
if [[ "$APPLY" -eq 1 ]]; then
  source "$WIKI/.claude/scripts/lib/wiki-lock.sh"
  if ! wiki_lock_acquire "build-backlinks"; then
    log "wiki-write lock held by '$(wiki_lock_holder)' (since $(wiki_lock_since)) — deferring. Exit."
    exit 0
  fi
  trap 'wiki_lock_release; wikilog_flush' EXIT
  OUT=$(python3 "$PY" --wiki-root "$WIKI" --timeline-out "$TIMELINE" --apply 2>&1)
else
  OUT=$(python3 "$PY" --wiki-root "$WIKI" --timeline-out "$TIMELINE" 2>&1)
fi
RC=$?
printf '%s\n' "$OUT" >> "$LOG"
if [[ "$RC" -ne 0 ]]; then
  log "ERROR: builder failed rc=$RC"; notify "Backlink builder FAILED — see log"; exit 1
fi

if [[ "$APPLY" -eq 1 ]]; then
  # Make the new body links traversable edges in GBrain (best-effort; never fatal).
  if [[ -x "$GBRAIN" ]]; then
    "$GBRAIN" import "$WIKI/wikis/" --no-embed >> "$LOG" 2>&1 || log "warn: gbrain import failed"
    "$GBRAIN" extract links --source db >> "$LOG" 2>&1 || log "warn: gbrain extract links failed"
  fi
  if [[ "$SYNC" -eq 1 ]]; then
    bash "$WIKI/.claude/scripts/vps-mirror-sync.sh" >> "$LOG" 2>&1 || log "warn: mirror sync failed"
  fi
fi

log "=== build-backlinks finished: $OUT ==="
echo "$OUT"
