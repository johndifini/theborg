#!/usr/bin/env bash
# gbrain-job.sh sync|dream — scheduled gbrain runs with newest-first logging.
#
# Replaces the raw plist commands so gbrain-sync.log / gbrain-dream.log get the
# same dated newest-first run blocks as every other job log, and the
# [extract.*] N/M (xx%) progress spam (hundreds of KB/day of .err growth) is
# filtered out — summary, "done", and error lines are kept.
#
# Wired by com.lashawsalta.gbrain-{sync,dream}.plist. Manual:
#   bash .claude/scripts/gbrain-job.sh sync
set -uo pipefail

JOB="${1:?usage: gbrain-job.sh sync|dream}"
WIKI="/Users/lashawsalta/life-wiki"
GB="$WIKI/.claude/scripts/gbrain"

source "$WIKI/.claude/scripts/lib/wikilog.sh"
wikilog_open "gbrain-$JOB"
trap 'wikilog_flush' EXIT

# Drop pure progress-ticker lines: "[extract.links_db] 2573/3022 (85%)".
# Keep "(100%) done", "Links: created ...", warnings, and errors.
quiet() { grep -vE '^\[[a-z._]+\] [0-9]+/[0-9]+ \([0-9]+%\)$' || true; }

case "$JOB" in
  sync)
    {
      "$GB" sync --repo "$WIKI/" --skip-failed 2>&1 \
        && "$GB" embed --stale 2>&1 \
        && "$GB" extract all --dir "$WIKI/" 2>&1
    } | quiet >> "$WIKILOG_BUF"
    ;;
  dream)
    "$GB" dream 2>&1 | quiet >> "$WIKILOG_BUF"
    ;;
  *)
    echo "unknown job: $JOB" >> "$WIKILOG_BUF"; exit 2 ;;
esac
