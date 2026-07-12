#!/usr/bin/env bash
# lib/wikilog.sh — newest-run-first job logging for .claude/logs/.
#
# Every job log reads top-down = newest run first. Each run is one dated block:
#   ▶ 2026-07-02 08:00:01 — <job> (ended 08:00:09)
#   ...the run's lines, oldest-first within the block...
#   <blank line>
#
# Usage in a job script:
#   source "$WIKI/.claude/scripts/lib/wikilog.sh"
#   wikilog_open "<job>"            # after this, $WIKILOG_BUF is the run buffer
#   LOG="$WIKILOG_BUF"              # existing log()/appends keep working as-is
#   trap 'wikilog_flush' EXIT       # merge into any existing EXIT trap
#
# wikilog_flush prepends the buffered block to .claude/logs/<job>.log via a
# temp-file + mv swap. Safe because job scripts open/write/close per run (no
# held append fds). launchd StandardOut/ErrorPath capture files (*-launchd.log,
# *.err) are NOT managed by this lib — they stay append-mode; rotate-logs.sh
# handles both formats. Overlapping runs of the same job are excluded by each
# job's own single-flight lock; distinct jobs never share a log file.

WIKILOG_DIR="${WIKILOG_DIR:-/Users/lashawsalta/life-wiki/.claude/logs}"

wikilog_open() {
  WIKILOG_JOB="$1"
  WIKILOG_FILE="$WIKILOG_DIR/$WIKILOG_JOB.log"
  WIKILOG_T0="$(date '+%Y-%m-%d %H:%M:%S')"
  WIKILOG_BUF="$(mktemp "${TMPDIR:-/tmp}/wikilog-$WIKILOG_JOB.XXXXXX")"
}

wikilog_flush() {
  [ -n "${WIKILOG_BUF:-}" ] && [ -f "$WIKILOG_BUF" ] || return 0
  local tmp
  tmp="$(mktemp "${TMPDIR:-/tmp}/wikilog-flush.XXXXXX")" || return 0
  {
    printf '\xe2\x96\xb6 %s \xe2\x80\x94 %s (ended %s)\n' "$WIKILOG_T0" "$WIKILOG_JOB" "$(date '+%H:%M:%S')"
    cat "$WIKILOG_BUF"
    printf '\n'
    if [ -f "$WIKILOG_FILE" ]; then cat "$WIKILOG_FILE"; fi
  } > "$tmp" && mv "$tmp" "$WIKILOG_FILE"
  rm -f "$WIKILOG_BUF"
  WIKILOG_BUF=""
}
