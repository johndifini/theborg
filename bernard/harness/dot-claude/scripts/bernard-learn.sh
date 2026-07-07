#!/usr/bin/env bash
# bernard-learn.sh — turn Bernard's conversations into wiki improvements.
#
# The learning half of Bernard's north star ([[wikis/shared/bernard-north-star]]):
# the family's questions are the strongest signal of what the record must cover.
# Reads the conversation log pulled back by vps-mirror-sync.sh and:
#   - files NEW actionable question-inbox items (tagged [bernard], deduped against
#     inbox + archive by question text — same convention as self-interrogate.sh),
#   - (re)writes wikis/shared/bernard-usage-profile.md (mirror-visible) so the
#     curator + synthesis pass see what's actually being asked,
#   - reindexes GBrain so the profile's links become edges.
#
# Default = dry-run (prints what it would file/write). --apply writes; --sync
# also refreshes the mirror. Scheduled daily after the 07:00 mirror sync.
# Manual: bash .claude/scripts/bernard-learn.sh
set -uo pipefail

WIKI="/Users/lashawsalta/life-wiki"
PY="$WIKI/.claude/scripts/lib/bernard_learn.py"
# Paths are env-overridable (defaults are the real ones) so the job is testable
# into a sandbox without touching the live inbox/wiki — same convention as
# vps-mirror-sync.sh's REMOTE/WIKI_ROOT.
LOG_IN="${BL_LOG_IN:-$WIKI/.claude/inbox/bernard-conversation-log.md}"
INBOX="${BL_INBOX:-$WIKI/.claude/inbox/wiki-question-inbox.md}"
ARCHIVE="${BL_ARCHIVE:-$WIKI/.claude/inbox/inbox-archive.md}"
USAGE="${BL_USAGE:-$WIKI/wikis/shared/bernard-usage-profile.md}"
GBRAIN="${BL_GBRAIN:-$WIKI/.claude/scripts/gbrain}"
mkdir -p "$WIKI/.claude/logs" "$(dirname "$INBOX")"
source "$WIKI/.claude/scripts/lib/wikilog.sh"
wikilog_open "bernard-learn"
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
notify() { /usr/bin/osascript -e "display notification \"$1\" with title \"Bernard Learn\" sound name \"Ping\"" 2>/dev/null || true; }
log "=== bernard-learn started (apply=$APPLY sync=$SYNC) ==="

if [[ ! -f "$LOG_IN" ]]; then
  echo "bernard-learn: no conversation log at $LOG_IN yet — nothing to do."
  log "no conversation log — exit 0"; exit 0
fi

TODAY="$(date '+%Y-%m-%d')"

# Run the distiller. --usage-out only on --apply (it writes a wiki page); on a
# dry run we still want the candidate inbox lines, so call without --usage-out.
acquire_lock() {
  source "$WIKI/.claude/scripts/lib/wiki-lock.sh"
  if ! wiki_lock_acquire "bernard-learn"; then
    log "wiki-write lock held by '$(wiki_lock_holder)' (since $(wiki_lock_since)) — deferring."
    echo "bernard-learn: wiki-write lock busy — deferring."
    exit 0
  fi
  trap 'wiki_lock_release; wikilog_flush' EXIT
}

if [[ "$APPLY" -eq 1 ]]; then
  acquire_lock
  CAND=$(python3 "$PY" --log "$LOG_IN" --usage-out "$USAGE" --now "$TODAY" 2>>"$LOG") || {
    log "distiller failed"; notify "bernard-learn FAILED — see log"; exit 1; }
else
  CAND=$(python3 "$PY" --log "$LOG_IN" --now "$TODAY" 2>>"$LOG") || {
    log "distiller failed"; exit 1; }
fi

# Dedup candidate inbox lines against inbox+archive by question text (field 2,
# split on ' — '), exactly like self-interrogate.sh.
existing=$(mktemp); new=$(mktemp)
{ [[ -f "$INBOX" ]] && cat "$INBOX"; [[ -f "$ARCHIVE" ]] && cat "$ARCHIVE"; } \
  | awk -F' — ' '/^- /{print $2}' | sed 's/[[:space:]]*$//' | sort -u > "$existing"
while IFS= read -r line; do
  [[ "$line" == "- "* ]] || continue
  q=$(printf '%s' "$line" | awk -F' — ' '{print $2}' | sed 's/[[:space:]]*$//')
  grep -qxF "$q" "$existing" || printf '%s\n' "$line" >> "$new"
done <<< "$CAND"

n_new=$(grep -c '^- ' "$new" 2>/dev/null); n_new=${n_new:-0}
log "distiller emitted candidates; $n_new new after dedup"

if [[ "$APPLY" -eq 1 ]]; then
  if (( n_new > 0 )); then
    [[ -f "$INBOX" ]] || printf '# Wiki Question Inbox\n\nOne line per gap.\n\n' > "$INBOX"
    cat "$new" >> "$INBOX"
    log "appended $n_new [bernard] item(s) to inbox"
    notify "Bernard learn: $n_new new item(s) — run /inbox-triage"
  fi
  # Make the new usage-profile links traversable (best-effort; never fatal).
  if [[ -x "$GBRAIN" ]]; then
    "$GBRAIN" import "$WIKI/wikis/" --no-embed >> "$LOG" 2>&1 || log "warn: gbrain import failed"
    "$GBRAIN" extract links --source db >> "$LOG" 2>&1 || log "warn: gbrain extract links failed"
  fi
  if [[ "$SYNC" -eq 1 ]]; then
    bash "$WIKI/.claude/scripts/vps-mirror-sync.sh" >> "$LOG" 2>&1 || log "warn: mirror sync failed"
  fi
  echo "bernard-learn: filed $n_new new inbox item(s); usage profile refreshed."
else
  echo "bernard-learn DRY-RUN: $n_new new inbox item(s) would be filed:"
  cat "$new"
  echo "(usage profile would be (re)written to $USAGE on --apply)"
fi

rm -f "$existing" "$new"
log "=== bernard-learn finished: $n_new new ==="
