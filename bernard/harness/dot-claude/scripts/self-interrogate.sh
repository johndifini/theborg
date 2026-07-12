#!/usr/bin/env bash
# self-interrogate.sh — recommendation ②: the wiki asks itself questions.
#
# Runs the deterministic structural-gap detector and files NEW questions into the
# companion question inbox (the same queue Bernard's unanswered questions land in),
# tagged [self-interrogate] so /inbox-triage handles them like any other gap.
# Deduped against both the live inbox and inbox-archive.md by question text, so a
# gap already filed or already resolved is never re-asked.
#
# Default = dry-run (prints new candidates). --apply appends to the inbox.
# Scheduled idea: daily after build-backlinks. Manual: bash .claude/scripts/self-interrogate.sh
set -uo pipefail

WIKI="/Users/lashawsalta/life-wiki"
PY="$WIKI/.claude/scripts/lib/self_interrogate.py"
INBOX="$WIKI/.claude/inbox/wiki-question-inbox.md"
ARCHIVE="$WIKI/.claude/inbox/inbox-archive.md"
PROFILE="$WIKI/.claude/logs/calibration-profile.tsv"
mkdir -p "$(dirname "$INBOX")" "$WIKI/.claude/logs"
source "$WIKI/.claude/scripts/lib/wikilog.sh"
wikilog_open "self-interrogate"
LOG="$WIKILOG_BUF"
trap 'wikilog_flush' EXIT

APPLY=0
for a in "$@"; do case "$a" in --apply) APPLY=1 ;; *) echo "unknown arg: $a" >&2; exit 2 ;; esac; done

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }

# Pass the calibration profile (rec ⑤) so noisy categories get a history note.
CAND=$(python3 "$PY" --wiki-root "$WIKI" --profile "$PROFILE") || { log "detector failed"; exit 1; }

# Build the set of already-known question texts (field 2 split on ' — ') from
# inbox + archive, so dedup survives both filing and resolution.
existing=$(mktemp)
{ [[ -f "$INBOX" ]] && cat "$INBOX"; [[ -f "$ARCHIVE" ]] && cat "$ARCHIVE"; } \
  | awk -F' — ' '/^- /{print $2}' | sed 's/[[:space:]]*$//' | sort -u > "$existing"

new=$(mktemp)
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  q=$(printf '%s' "$line" | awk -F' — ' '{print $2}' | sed 's/[[:space:]]*$//')
  grep -qxF "$q" "$existing" || printf '%s\n' "$line" >> "$new"
done <<< "$CAND"

# grep -c prints the count to stdout but EXITS 1 when the count is 0; capture the
# clean number and ignore the exit status (do NOT add `|| echo 0` — that appends a
# second line and breaks the arithmetic test below).
n_total=$(grep -c '^- ' <<< "$CAND" 2>/dev/null); n_total=${n_total:-0}
n_new=$(grep -c '^- ' "$new" 2>/dev/null); n_new=${n_new:-0}
log "detector: $n_total candidate(s); $n_new new after dedup"

if [[ "$n_new" -eq 0 ]]; then
  echo "self-interrogate: 0 new questions (of $n_total candidates; rest already in inbox/archive)"
  rm -f "$existing" "$new"; exit 0
fi

if [[ "$APPLY" -eq 1 ]]; then
  [[ -f "$INBOX" ]] || printf '# Wiki Question Inbox\n\nOne line per gap: `- YYYY-MM-DD — question — what was missing`\n\n' > "$INBOX"
  cat "$new" >> "$INBOX"
  log "appended $n_new new question(s) to inbox"
  echo "self-interrogate: appended $n_new new question(s) to the inbox"
else
  echo "self-interrogate DRY-RUN: $n_new new question(s) would be filed:"
  cat "$new"
fi
rm -f "$existing" "$new"
