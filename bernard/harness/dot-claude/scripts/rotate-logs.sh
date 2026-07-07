#!/usr/bin/env bash
# rotate-logs.sh — cap append-only scheduled-job logs in .claude/logs/.
#
# WHY truncate-in-place (not mv): launchd opens StandardOut/ErrorPath in append
# mode and holds the fd open. `mv` would orphan that fd — launchd keeps writing
# to the old inode and the new file never fills until the job restarts. We keep
# the SAME inode: copy the tail out, then `cat > file` to rewrite it in place.
#
# Strategy: any *.log/*.err over MAX_BYTES is trimmed to KEEP_LINES; the part
# removed is appended to a single gzipped overflow generation (*.1.gz) so a
# recent failure stays recoverable for one cycle. Status/state/.tsv files and
# overwrite-mode logs are left alone.
#
# Wire-in: called by harness-health.sh (daily 08:00). Safe to run by hand.
set -euo pipefail

LOGDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../logs" && pwd)"
MAX_BYTES=$((1 * 1024 * 1024))   # rotate when larger than 1 MB
KEEP_LINES=2000                  # lines retained in the live file
rotated=0

for f in "$LOGDIR"/*.log "$LOGDIR"/*.err; do
  [ -f "$f" ] || continue
  size=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null || echo 0)
  [ "$size" -le "$MAX_BYTES" ] && continue

  tmp="$f.rot.$$"
  # Preserve the overflow (whatever is trimmed) as one gz generation.
  total=$(wc -l < "$f")
  drop=$(( total > KEEP_LINES ? total - KEEP_LINES : 0 ))

  # Two formats live in logs/: wikilog job logs are NEWEST-FIRST (first line is
  # a ▶ run header) — keep the head, the overflow is the tail. Plain append
  # logs (launchd captures, .err files) — keep the tail, overflow is the head.
  if head -c 3 "$f" | grep -q '▶'; then
    if [ "$drop" -gt 0 ]; then
      tail -n "+$((KEEP_LINES + 1))" "$f" | gzip -c > "$f.1.gz" || true
    fi
    head -n "$KEEP_LINES" "$f" > "$tmp"
  else
    if [ "$drop" -gt 0 ]; then
      head -n "$drop" "$f" | gzip -c > "$f.1.gz" || true
    fi
    tail -n "$KEEP_LINES" "$f" > "$tmp"
  fi
  cat "$tmp" > "$f"            # rewrite same inode — keeps launchd's append fd valid
  rm -f "$tmp"
  rotated=$((rotated + 1))
  echo "rotated $(basename "$f"): ${size} bytes -> $(stat -f%z "$f" 2>/dev/null || stat -c%s "$f") bytes"
done

echo "rotate-logs: $rotated file(s) rotated"
