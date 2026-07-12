#!/usr/bin/env bash
# self-improve.sh — run the whole self-improvement chain ON DEMAND, in dependency
# order. This is the same chain harness-health.sh runs daily at 08:00, packaged as
# one command for "I just ingested/edited — refresh the graph now."
#
#   ① build-backlinks       reciprocal entity backlinks + timeline spine
#   ⑥ build-daily-score     daily symptom score from latest Guava export
#   ⑤ calibration-capture   refresh precision profile from triaged history
#   ② self-interrogate      file newly-detected structural-gap questions
#   ③ hypothesis-register   recompile the open-inferences index
#   ④ cross-model-review    (only with --cross-model) adversarial verdict check
#
# Flags:
#   --dry-run       preview everything, write nothing
#   --cross-model   also run ④ (2 model calls; Anthropic-only by default)
#   --sync          push to the Bernard mirror afterward (leak-scan-gated)
# Default (no flags) = apply ①⑤②③, no ④, no mirror push.
set -uo pipefail

WIKI="/Users/lashawsalta/life-wiki"
S="$WIKI/.claude/scripts"
mkdir -p "$WIKI/.claude/logs"
source "$WIKI/.claude/scripts/lib/wikilog.sh"
wikilog_open "self-improve"
LOG="$WIKILOG_BUF"
trap 'wikilog_flush' EXIT

APPLY="--apply"; CROSS=0; SYNC=0; MODE="APPLY"
for a in "$@"; do
  case "$a" in
    --dry-run)     APPLY=""; MODE="DRY-RUN" ;;
    --cross-model) CROSS=1 ;;
    --sync)        SYNC=1 ;;
    *) echo "unknown arg: $a (use --dry-run | --cross-model | --sync)" >&2; exit 2 ;;
  esac
done

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }

# Never race the synthesis pass (it writes wiki content + does its own reindex).
if pgrep -f "daily-synthesis.sh" >/dev/null 2>&1; then
  echo "self-improve: a synthesis pass is running — try again when it finishes."
  exit 0
fi

log "=== self-improve ($MODE cross=$CROSS sync=$SYNC) ==="
echo "self-improve [$MODE]:"

step() {  # $1=label  $2..=command
  local label="$1"; shift
  local out; out=$("$@" 2>&1); local rc=$?
  local last; last=$(printf '%s\n' "$out" | tail -1)
  printf '  %-22s %s\n' "$label" "$last"
  log "$label :: $last"
  return $rc
}

step "① backlinks/timeline" bash "$S/build-backlinks.sh" $APPLY
step "⑥ daily-score"       bash "$S/build-daily-score.sh" $APPLY
step "⑤ calibration"        bash "$S/calibration-capture.sh" $APPLY
step "② self-interrogate"   bash "$S/self-interrogate.sh" $APPLY
step "③ hypothesis-register" bash "$S/build-hypothesis-register.sh" $APPLY
[[ "$CROSS" -eq 1 ]] && step "④ cross-model" bash "$S/cross-model-review.sh" $APPLY

# Make new body backlinks traversable edges, then optionally push to Bernard.
if [[ -n "$APPLY" ]]; then
  if [[ -x "$S/gbrain" ]]; then
    "$S/gbrain" import "$WIKI/wikis/" --no-embed >/dev/null 2>&1 \
      && "$S/gbrain" extract links --source db >/dev/null 2>&1 \
      && echo "  gbrain                 reindexed" || echo "  gbrain                 reindex warn (non-fatal)"
  fi
  [[ "$SYNC" -eq 1 ]] && step "mirror sync" bash "$S/vps-mirror-sync.sh"
fi

log "=== self-improve done ==="
echo "done — details in .claude/logs/self-improve.log"
