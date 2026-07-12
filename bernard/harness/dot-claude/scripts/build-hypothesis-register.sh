#!/usr/bin/env bash
# build-hypothesis-register.sh — recommendation ③: working-hypotheses register.
#
# Compiles every inline `> Hypothesis:` / `Needs verification:` / `> Contradiction:`
# marker across compiled-truth pages into wikis/health/wiki/working-hypotheses.md,
# each with a backlink to its source. Surfaces the dot-connecting the synthesis pass
# scatters across pages into one reviewable, re-graded-over-time place. Resolving a
# marker on its source page drops it off here next run. Idempotent; no model.
#
# Default = dry-run. --apply writes. Manual: bash .claude/scripts/build-hypothesis-register.sh --apply
set -uo pipefail

WIKI="/Users/lashawsalta/life-wiki"
PY="$WIKI/.claude/scripts/lib/hypothesis_register.py"
OUT="$WIKI/wikis/health/wiki/working-hypotheses.md"
mkdir -p "$WIKI/.claude/logs"
source "$WIKI/.claude/scripts/lib/wikilog.sh"
wikilog_open "build-hypothesis-register"
LOG="$WIKILOG_BUF"
trap 'wikilog_flush' EXIT

APPLY=0
for a in "$@"; do case "$a" in --apply) APPLY=1 ;; *) echo "unknown arg: $a" >&2; exit 2 ;; esac; done

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }

if pgrep -f "daily-synthesis.sh" >/dev/null 2>&1; then
  log "synthesis running — deferring."; exit 0
fi

if [[ "$APPLY" -eq 1 ]]; then
  OUTPUT=$(python3 "$PY" --wiki-root "$WIKI" --out "$OUT" --apply 2>&1)
else
  OUTPUT=$(python3 "$PY" --wiki-root "$WIKI" --out "$OUT" 2>&1)
fi
RC=$?
log "$OUTPUT"
if [[ "$RC" -ne 0 ]]; then echo "FAILED: $OUTPUT" >&2; exit 1; fi
echo "$OUTPUT"
