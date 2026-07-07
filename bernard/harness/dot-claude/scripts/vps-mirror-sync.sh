#!/usr/bin/env bash
# vps-mirror-sync.sh — one-way scoped mirror of the wiki to the VPS companion agent,
# plus pull-back of the single question-inbox file (the only reverse channel).
#
# Scope is allowlist-only: three explicit trees. Finance/housing/work, ingest/,
# raw journal transcripts, and audio can never reach the mirror because they are
# never named as a source. Deletions propagate (--delete) so removals on the Mac
# disappear from the mirror on the next run.
set -euo pipefail

REMOTE="${REMOTE:-youruser@your-vps}"
WIKI_ROOT="${WIKI_ROOT:-/Users/lashawsalta/life-wiki}"
MIRROR_DIR="health-wiki-mirror"                                  # under $HOME on the VPS
INBOX_REMOTE="health-wiki-workspace/wiki-question-inbox.md"      # under $HOME on the VPS
INBOX_LOCAL="$WIKI_ROOT/.claude/inbox/wiki-question-inbox.md"
LOCK_DIR="$WIKI_ROOT/.claude/tmp/vps-mirror-sync.lock"

# The entire mirror scope. Adding a path here is a curator decision — see
# "Publisher role" in CLAUDE.md before changing.
SCOPE=(
  "wikis/health"
  "wikis/shared"
  "wikis/journal/wiki/entries"
)

# PDFs excluded: the companion reads markdown only, and at least one raw PDF
# (2026-05-05-lee-cardiology-followup.pdf) is known to still contain
# un-pseudonymized PHI — binary provenance never leaves the Mac.
RSYNC_EXCLUDES=(
  --exclude '.DS_Store'
  --exclude '*.pdf'
  --exclude '*.m4a' --exclude '*.mp3' --exclude '*.wav' --exclude '*.mp4' --exclude '*.aac'
  # Curator decision 2026-06-12: the curator's family-of-origin journal work is
  # out of mirror scope — Bernard answers health questions about PATIENT-001 and
  # has no need for it. The sync runs with --delete-excluded, so adding a file
  # here also REMOVES any already-synced copy from the VPS on the next run.
  --exclude '2021-08-07-grand-lake-family-system.md'
  --exclude '2021-09-05-body-keeps-score-keystone.md'
)

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$WIKILOG_BUF"; }
notify() { /usr/bin/osascript -e "display notification \"$1\" with title \"Wiki Mirror Sync\" sound name \"Ping\"" 2>/dev/null || true; }

mkdir -p "$WIKI_ROOT/.claude/tmp" "$WIKI_ROOT/.claude/inbox" "$WIKI_ROOT/.claude/logs"
source "$WIKI_ROOT/.claude/scripts/lib/wikilog.sh"
wikilog_open "wiki-mirror-sync"
trap 'wikilog_flush' EXIT

# Failure alarm. Under `set -e`, an rsync/ssh failure (e.g. Tailscale tunnel down
# or SSH re-auth expired) aborts the script silently — launchd just records a
# non-zero exit and the mirror goes stale unnoticed (this bit us 2026-06-14→15).
# An ERR trap surfaces it. It fires only on UNEXPECTED command failures: explicit
# `exit 1` (the leak-gate branches, which already notify) does not trigger ERR,
# and the inbox-drain section's failures are all guarded by `if`/`&&`/`||`.
trap 'ec=$?; log "ERROR: sync aborted (exit $ec) near line $LINENO — VPS unreachable or rsync/ssh failed; see wiki-mirror-sync.err"; notify "Mirror sync FAILED (exit $ec) — tunnel down or VPS unreachable. See wiki-mirror-sync.err"' ERR

# ---- Leak-scan gate (fail closed) -------------------------------------------
# The nightly deep scan (02:30, com.life-wiki.scan) writes leak-scan-status.
# A push is allowed only on a fresh "clean". DEFINITE, missing, or stale
# (>48 h) status refuses the push — PHI never reaches the VPS on hope.
SCAN_STATUS_FILE="$WIKI_ROOT/.claude/logs/leak-scan-status"
GATE_MAX_AGE_S=$(( 48 * 3600 ))
if [[ ! -f "$SCAN_STATUS_FILE" ]]; then
  log "MIRROR GATE: no leak-scan status — refusing to push. Bootstrap: bash .claude/scripts/nightly-leak-scan.sh"
  notify "Mirror push refused: no leak-scan status (run nightly-leak-scan.sh)"
  exit 1
fi
if ! head -1 "$SCAN_STATUS_FILE" | grep -q '^clean'; then
  log "MIRROR GATE: leak-scan status is $(head -1 "$SCAN_STATUS_FILE") — refusing to push. Triage leak-scan.log first."
  notify "Mirror push refused: leak scan found DEFINITE findings"
  exit 1
fi
if (( $(date +%s) - $(stat -f %m "$SCAN_STATUS_FILE") > GATE_MAX_AGE_S )); then
  log "MIRROR GATE: leak-scan status older than 48h — refusing to push. Re-run nightly-leak-scan.sh."
  notify "Mirror push refused: leak-scan status stale (>48h)"
  exit 1
fi

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  log "another sync is running ($LOCK_DIR exists) — exiting"
  exit 0
fi
trap 'rmdir "$LOCK_DIR"; wikilog_flush' EXIT

for dir in "${SCOPE[@]}"; do
  [ -d "$WIKI_ROOT/$dir" ] || { log "ERROR: scope dir missing locally: $dir"; notify "Mirror sync aborted: scope dir missing locally ($dir)"; exit 1; }
done

log "sync start → $REMOTE:~/$MIRROR_DIR"
ssh -o ConnectTimeout=15 "$REMOTE" "mkdir -p $(printf "~/$MIRROR_DIR/%q " "${SCOPE[@]}")"

for dir in "${SCOPE[@]}"; do
  rsync -az --delete --delete-excluded "${RSYNC_EXCLUDES[@]}" \
    "$WIKI_ROOT/$dir/" "$REMOTE:~/$MIRROR_DIR/$dir/"
  log "synced $dir"
done

# Freshness stamp — the companion agent reads this to report "my copy last synced ...".
STATUS_TMP="$(mktemp)"
cat > "$STATUS_TMP" <<EOF
# Mirror Status

- **Last synced:** $(date '+%Y-%m-%d %H:%M %Z')
- **Source:** curator's master wiki (one-way mirror — local edits here are overwritten)
- **Scope:** ${SCOPE[*]}
EOF
rsync -az "$STATUS_TMP" "$REMOTE:~/$MIRROR_DIR/MIRROR-STATUS.md"
rm -f "$STATUS_TMP"

# Reverse channel: exactly one file, PULL-AND-DRAIN. Bernard appends gap
# lines on the VPS; we atomically claim the file (mv is rename — Bernard's
# next append just recreates it, nothing is lost), merge new lines into the
# local pending inbox (deduped against pending + archive so /inbox-triage'd
# items never resurrect), then archive the drained copy remotely. If the
# remote archive step ever fails, the .draining file is re-read next run.
INBOX_ARCHIVE_LOCAL="$WIKI_ROOT/.claude/inbox/inbox-archive.md"
DRAIN="health-wiki-workspace/.wiki-question-inbox.draining"
if ssh -o ConnectTimeout=15 "$REMOTE" "
      cd ~ || exit 1
      if [ -f $INBOX_REMOTE ]; then mv $INBOX_REMOTE $DRAIN.new 2>/dev/null || true; fi
      if [ -f $DRAIN.new ]; then cat $DRAIN.new >> $DRAIN && rm $DRAIN.new; fi
      [ -f $DRAIN ] && cat $DRAIN || true
    " > "$INBOX_LOCAL.tmp"; then
  if [ -s "$INBOX_LOCAL.tmp" ]; then
    if [ ! -f "$INBOX_LOCAL" ]; then
      printf '# Wiki Question Inbox\n\nOne line per gap: `- YYYY-MM-DD — question — what was missing`\nDrain with /inbox-triage; done lines move to inbox-archive.md.\n\n' > "$INBOX_LOCAL"
    fi
    new_lines=0
    while IFS= read -r line; do
      case "$line" in "- "*) ;; *) continue ;; esac
      { cat "$INBOX_LOCAL" "$INBOX_ARCHIVE_LOCAL" 2>/dev/null || true; } | grep -qF -- "$line" && continue
      printf '%s\n' "$line" >> "$INBOX_LOCAL"
      new_lines=$((new_lines+1))
    done < "$INBOX_LOCAL.tmp"
    ssh -o ConnectTimeout=15 "$REMOTE" "
        cd ~ && [ -f $DRAIN ] \
        && cat $DRAIN >> health-wiki-workspace/wiki-question-inbox-archive.md \
        && rm $DRAIN" \
      && log "inbox drained: $new_lines new line(s) → $INBOX_LOCAL (remote archived)" \
      || log "WARN: inbox pulled ($new_lines new) but remote archive step failed — will re-read next run"
  else
    log "inbox empty or absent on VPS"
  fi
  rm -f "$INBOX_LOCAL.tmp"
else
  rm -f "$INBOX_LOCAL.tmp"
  log "WARN: could not reach inbox on VPS"
fi

# Reverse channel #2: Bernard's conversation log — the learning-loop signal
# (every substantive exchange, not just gaps). Same atomic pull-and-drain as the
# inbox above: claim by rename, append new lines locally (deduped by exact line),
# archive the drained copy remotely. bernard-learn.sh distills the local copy
# into wiki-improvement work. Guarded by if/&&/|| so a failure here doesn't trip
# the ERR trap or abort the run.
CONVO_REMOTE="health-wiki-workspace/bernard-conversation-log.md"
CONVO_LOCAL="$WIKI_ROOT/.claude/inbox/bernard-conversation-log.md"
CONVO_DRAIN="health-wiki-workspace/.bernard-conversation-log.draining"
if ssh -o ConnectTimeout=15 "$REMOTE" "
      cd ~ || exit 1
      if [ -f $CONVO_REMOTE ]; then mv $CONVO_REMOTE $CONVO_DRAIN.new 2>/dev/null || true; fi
      if [ -f $CONVO_DRAIN.new ]; then cat $CONVO_DRAIN.new >> $CONVO_DRAIN && rm $CONVO_DRAIN.new; fi
      [ -f $CONVO_DRAIN ] && cat $CONVO_DRAIN || true
    " > "$CONVO_LOCAL.tmp"; then
  if [ -s "$CONVO_LOCAL.tmp" ]; then
    [ -f "$CONVO_LOCAL" ] || printf '# Bernard Conversation Log (pulled from VPS)\n\nAppend-only local copy. One line per exchange. Distilled by bernard-learn.sh.\n\n' > "$CONVO_LOCAL"
    convo_new=0
    while IFS= read -r line; do
      case "$line" in "- "*) ;; *) continue ;; esac
      grep -qF -- "$line" "$CONVO_LOCAL" 2>/dev/null && continue
      printf '%s\n' "$line" >> "$CONVO_LOCAL"
      convo_new=$((convo_new+1))
    done < "$CONVO_LOCAL.tmp"
    ssh -o ConnectTimeout=15 "$REMOTE" "
        cd ~ && [ -f $CONVO_DRAIN ] \
        && cat $CONVO_DRAIN >> health-wiki-workspace/bernard-conversation-log-archive.md \
        && rm $CONVO_DRAIN" \
      && log "conversation log drained: $convo_new new line(s) → $CONVO_LOCAL (remote archived)" \
      || log "WARN: conversation log pulled ($convo_new new) but remote archive failed — will re-read next run"
  else
    log "conversation log empty or absent on VPS"
  fi
  rm -f "$CONVO_LOCAL.tmp"
else
  rm -f "$CONVO_LOCAL.tmp"
  log "WARN: could not reach conversation log on VPS"
fi

log "sync complete"
