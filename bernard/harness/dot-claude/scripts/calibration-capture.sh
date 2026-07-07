#!/usr/bin/env bash
# calibration-capture.sh — recommendation ⑤: learn from curator confirmations.
#
# Turns triaged inbox history into a calibration profile: per detector/category
# precision (real vs dismissed) + median latency, written to
# .claude/logs/calibration-profile.tsv. self-interrogate reads this profile to
# annotate noise-prone categories, and tuning hints surface to the log — so a
# detector that keeps crying wolf gets tightened instead of repeating itself.
#
# Requires the curator to archive triaged lines with an outcome tag:
#   [done YYYY-MM-DD → target]  (real)   |   [dismissed YYYY-MM-DD: reason] (noise)
# Manual: bash .claude/scripts/calibration-capture.sh [--apply]
set -uo pipefail

WIKI="/Users/lashawsalta/life-wiki"
PY="$WIKI/.claude/scripts/lib/calibration_capture.py"
ARCHIVE="${CAL_ARCHIVE:-$WIKI/.claude/inbox/inbox-archive.md}"
PROFILE="${CAL_PROFILE:-$WIKI/.claude/logs/calibration-profile.tsv}"
mkdir -p "$WIKI/.claude/logs" "$(dirname "$PROFILE")"
source "$WIKI/.claude/scripts/lib/wikilog.sh"
wikilog_open "calibration-capture"
LOG="$WIKILOG_BUF"
trap 'wikilog_flush' EXIT

APPLY=0
for a in "$@"; do case "$a" in --apply) APPLY=1 ;; *) echo "unknown arg: $a" >&2; exit 2 ;; esac; done

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }

if [[ "$APPLY" -eq 1 ]]; then
  OUT=$(python3 "$PY" --archive "$ARCHIVE" --out-tsv "$PROFILE" --apply 2>&1)
else
  OUT=$(python3 "$PY" --archive "$ARCHIVE" 2>&1)
fi
RC=$?
log "$OUT"
[[ "$RC" -ne 0 ]] && { echo "FAILED: $OUT" >&2; exit 1; }
# Surface tuning hints (if any) to the log prominently.
printf '%s\n' "$OUT" | grep -q '— consider tightening' && log "TUNING HINTS present (see above)"
echo "$OUT"
