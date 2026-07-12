#!/usr/bin/env bash
# build-graph-links.sh — build traversable graph EDGES from declared relationships.
#
# Per CLAUDE.md, frontmatter providers/conditions/medications lists are metadata
# ONLY — they create no graph edges. Bernard (and GBrain traversal) reach an
# entity only via an inline body [[wikilink]]. This converts every declared-but-
# unlinked relationship into a real body edge, mechanically:
#   1. backfill-entity-frontmatter.py  — ensure journal/recording entries carry
#      providers/conditions/medications frontmatter for entities they mention
#   2. backfill-entity-links.py        — emit the matching ## Entity Links body
#      wikilinks (the actual edges)
#   3. gbrain reindex                  — make the new body links graph edges
#
# Complements build-backlinks.sh (which builds the reverse "## Mentioned In"
# spine + timeline). Run as siblings — this one does NOT call build-backlinks,
# because both take the non-reentrant wiki-write lock.
#
# Default = dry-run (preview, no writes). --apply writes under the wiki-write
# lock + reindexes; --sync also refreshes the mirror.
# Wired into harness-health (daily) and triggerable by wiki-eval --build-links
# when a graph golden-row is failing. Manual: bash .claude/scripts/build-graph-links.sh
set -uo pipefail

WIKI="/Users/lashawsalta/life-wiki"
FM_PY="$WIKI/.claude/scripts/backfill-entity-frontmatter.py"
EL_PY="$WIKI/.claude/scripts/backfill-entity-links.py"
GBRAIN="${BGL_GBRAIN:-$WIKI/.claude/scripts/gbrain}"
LOGDIR="$WIKI/.claude/logs"
mkdir -p "$LOGDIR"
source "$WIKI/.claude/scripts/lib/wikilog.sh"
wikilog_open "build-graph-links"
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
notify() { /usr/bin/osascript -e "display notification \"$1\" with title \"Build Graph Links\" sound name \"Ping\"" 2>/dev/null || true; }
log "=== build-graph-links started (apply=$APPLY sync=$SYNC) ==="

if [[ "$APPLY" -eq 0 ]]; then
  echo "build-graph-links DRY-RUN (no writes):"
  echo "--- entity frontmatter backfill ---"; python3 "$FM_PY" || true
  echo "--- entity links backfill ---";        python3 "$EL_PY" || true
  echo "(run with --apply to write + reindex)"
  log "=== build-graph-links dry-run finished ==="
  exit 0
fi

# --apply: serialize against other writers (non-reentrant — do NOT nest under
# another holder such as build-backlinks).
source "$WIKI/.claude/scripts/lib/wiki-lock.sh"
if ! wiki_lock_acquire "build-graph-links"; then
  log "wiki-write lock held by '$(wiki_lock_holder)' (since $(wiki_lock_since)) — deferring."
  echo "build-graph-links: wiki-write lock busy — deferring."
  exit 0
fi
trap 'wiki_lock_release; wikilog_flush' EXIT

FM_OUT=$(python3 "$FM_PY" --apply 2>&1) || { log "ERROR: frontmatter backfill failed"; notify "build-graph-links: frontmatter backfill FAILED"; exit 1; }
EL_OUT=$(python3 "$EL_PY" --apply 2>&1) || { log "ERROR: entity-link backfill failed"; notify "build-graph-links: entity-link backfill FAILED"; exit 1; }
printf '%s\n%s\n' "$FM_OUT" "$EL_OUT" >> "$LOG"

# Count touched files (both scripts print one line per written file). Heuristic —
# any line mentioning a wiki path that isn't the dry-run hint.
changed=$(printf '%s\n%s\n' "$FM_OUT" "$EL_OUT" | grep -cE 'wikis/.*\.md' || true)
changed=${changed:-0}
log "backfills applied; ~${changed} file-edit line(s)"

# Make the new body links traversable edges (best-effort; never fatal).
if [[ -x "$GBRAIN" ]]; then
  "$GBRAIN" import "$WIKI/wikis/" --no-embed >> "$LOG" 2>&1 || log "warn: gbrain import failed"
  "$GBRAIN" extract links --source db >> "$LOG" 2>&1 || log "warn: gbrain extract links failed"
fi

if [[ "$SYNC" -eq 1 ]]; then
  bash "$WIKI/.claude/scripts/vps-mirror-sync.sh" >> "$LOG" 2>&1 || log "warn: mirror sync failed"
fi

echo "build-graph-links: applied (~${changed} edit line(s)); GBrain reindexed."
log "=== build-graph-links finished (~${changed} edit line(s)) ==="
