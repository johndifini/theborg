#!/usr/bin/env bash
# build-daily-score.sh — deterministic daily symptom score from the latest
# Guava export. Idempotent; no model.
#
# Default = dry-run (safe to run anytime). --apply writes, reindexes GBrain so
# the new score page/links become graph edges, and (with --sync) refreshes
# the mirror.
# Manual: bash .claude/scripts/build-daily-score.sh --apply
set -uo pipefail

WIKI="/Users/lashawsalta/life-wiki"
LOGDIR="$WIKI/.claude/logs"
PY="$WIKI/.claude/scripts/lib/daily_score.py"
CHARTS_PY="$WIKI/.claude/scripts/lib/render_score_charts.py"
GBRAIN="$WIKI/.claude/scripts/gbrain"
mkdir -p "$LOGDIR"
source "$WIKI/.claude/scripts/lib/wikilog.sh"
wikilog_open "build-daily-score"
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
notify() { /usr/bin/osascript -e "display notification \"$1\" with title \"Life Wiki Daily Score\" sound name \"Ping\"" 2>/dev/null || true; }

log "=== build-daily-score started (apply=$APPLY sync=$SYNC) ==="

# Shared write-lock — only for --apply, which rewrites pages. Supersedes the old
# pgrep-based synthesis guard: now defers for ANY writer (sibling jobs AND
# interactive sessions), not just a running synthesis pass. Dry-run needs no lock.
if [[ "$APPLY" -eq 1 ]]; then
  source "$WIKI/.claude/scripts/lib/wiki-lock.sh"
  if ! wiki_lock_acquire "build-daily-score"; then
    log "wiki-write lock held by '$(wiki_lock_holder)' (since $(wiki_lock_since)) — deferring. Exit."
    exit 0
  fi
  trap 'wiki_lock_release; wikilog_flush' EXIT
  OUT=$(python3 "$PY" --wiki-root "$WIKI" --apply 2>&1)
else
  OUT=$(python3 "$PY" --wiki-root "$WIKI" 2>&1)
fi
RC=$?
printf '%s\n' "$OUT" >> "$LOG"
if [[ "$RC" -ne 0 ]]; then
  log "ERROR: builder failed rc=$RC"; notify "Daily score builder FAILED — see log"; exit 1
fi

if [[ "$APPLY" -eq 1 ]]; then
  # Best-effort chart render — charts must never fail the build.
  if [[ -f "$CHARTS_PY" ]]; then
    python3 "$CHARTS_PY" --wiki-root "$WIKI" --apply >> "$LOG" 2>&1 || log "warn: chart render failed (non-fatal)"
  else
    log "charts renderer not present — skipped"
  fi

  # Make the new score page/links traversable edges in GBrain (best-effort; never fatal).
  if [[ -x "$GBRAIN" ]]; then
    "$GBRAIN" import "$WIKI/wikis/" --no-embed >> "$LOG" 2>&1 || log "warn: gbrain import failed"
    "$GBRAIN" extract links --source db >> "$LOG" 2>&1 || log "warn: gbrain extract links failed"
  fi
  if [[ "$SYNC" -eq 1 ]]; then
    bash "$WIKI/.claude/scripts/vps-mirror-sync.sh" >> "$LOG" 2>&1 || log "warn: mirror sync failed"
  fi
else
  # Dry-run: still exercise the chart renderer best-effort, without --apply.
  if [[ -f "$CHARTS_PY" ]]; then
    python3 "$CHARTS_PY" --wiki-root "$WIKI" >> "$LOG" 2>&1 || log "warn: chart render failed (non-fatal)"
  else
    log "charts renderer not present — skipped"
  fi
fi

log "=== build-daily-score finished: $OUT ==="
echo "$OUT"
