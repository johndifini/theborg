#!/usr/bin/env bash
# harness-health.sh — daily watchdog over the wiki's scheduled automation.
#
#   Tier 0  detect    log/status freshness for every scheduled job
#   Tier 1  fix       deterministic: launchctl kickstart, stale lock cleanup
#   Tier 2  diagnose  headless `claude -p` with a read/launchctl-scoped allowlist
#   fallback notify   macOS notification naming what needs the curator
#
# Scheduled by com.lashawsalta.harness-health (daily 08:00 — after the 07:00
# mirror run). Manual run: bash .claude/scripts/harness-health.sh
# Every run ends in exactly one of: "all green" (silent), "fixed: ..." or
# "needs you: ..." (both notify).
set -uo pipefail

WIKI="/Users/lashawsalta/life-wiki"
LOGDIR="$WIKI/.claude/logs"
AGENT_LOG="$LOGDIR/harness-health-agent.log"
CLAUDE_BIN="/opt/homebrew/bin/claude"
TARGETS="$HOME/Devops/life-wiki-sanitizer/secrets/redaction_targets.json"
UID_N=$(id -u)
mkdir -p "$LOGDIR"

# Newest-first run logging (lib/wikilog.sh): log() lines buffer per run and get
# prepended to harness-health.log at exit — open the log, newest run is on top.
source "$WIKI/.claude/scripts/lib/wikilog.sh"
wikilog_open "harness-health"
LOG="$WIKILOG_BUF"
trap 'wikilog_flush' EXIT

log()    { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }
notify() { /usr/bin/osascript -e "display notification \"$1\" with title \"Wiki Harness Health\" sound name \"Ping\"" 2>/dev/null || true; }
age()    { [[ -e "$1" ]] && echo $(( $(date +%s) - $(stat -f %m "$1") )) || echo 999999999; }

issues=(); fixed=()

# check NAME FILE MAX_AGE_SECONDS LAUNCHD_LABEL("" = not kickstartable)
check() {
  local name="$1" f="$2" max="$3" label="$4"
  (( $(age "$f") <= max )) && return 0
  if [[ -n "$label" ]]; then
    log "STALE: $name ($f) — kickstarting $label"
    launchctl kickstart -k "gui/$UID_N/$label" >> "$LOG" 2>&1 || true
    sleep 90
    if (( $(age "$f") > max )); then
      issues+=("$name: still stale after kickstarting $label")
    else
      fixed+=("$name (kickstarted)")
    fi
  else
    issues+=("$name: stale, no auto-fix (scheduled by cron — Mac asleep at trigger time skips silently)")
  fi
}

log "=== harness-health run started ==="

# Tier 1 pre-clean: an orphaned mirror lock blocks every future sync silently.
LOCK="$WIKI/.claude/tmp/vps-mirror-sync.lock"
if [[ -d "$LOCK" ]] && (( $(age "$LOCK") > 7200 )); then
  rmdir "$LOCK" 2>/dev/null && { log "removed stale mirror-sync lock"; fixed+=("stale mirror-sync lock removed"); }
fi

# Tier 1 pre-clean: a forgotten wiki-write lock (an interactive agent that took it
# for an ingest/synthesis and crashed without releasing) would make every scheduled
# write job defer. Sweep it once past its 2 h TTL (matches lib/wiki-lock.sh). The
# lock dir holds metadata files, so rm -rf, not rmdir.
WLOCK="$WIKI/.claude/tmp/wiki-write.lock"
if [[ -d "$WLOCK" ]] && (( $(age "$WLOCK") > 7200 )); then
  rm -rf "$WLOCK" 2>/dev/null && { log "removed stale wiki-write lock"; fixed+=("stale wiki-write lock removed"); }
fi

# Tier 1 pre-clean: cap append-only job logs so they never grow unbounded.
# (gbrain-sync writes progress to .err; modest now that it runs daily, not every 15 min.)
ROTATE_OUT=$(bash "$WIKI/.claude/scripts/rotate-logs.sh" 2>&1) || true
printf '%s\n' "$ROTATE_OUT" | grep -q 'rotated ' && log "log rotation: $(printf '%s' "$ROTATE_OUT" | grep '^rotated ' | tr '\n' ';')"

# Graph maintenance (rec ①): rebuild entity backlinks + the timeline spine so new
# journal entries stay reachable by traversal. Idempotent; self-guards if a
# synthesis pass is mid-write. Changes reach Bernard on the next mirror sync.
if ! pgrep -f "daily-synthesis.sh" >/dev/null 2>&1; then
  BL_OUT=$(bash "$WIKI/.claude/scripts/build-backlinks.sh" --apply 2>&1) || true
  printf '%s\n' "$BL_OUT" | grep -q 'changed: 0' || { log "backlinks: $(printf '%s' "$BL_OUT" | grep APPLIED)"; fixed+=("backlinks/timeline refreshed"); }

  # build-graph-links.sh was removed from this daily chain 2026-07-02 (curator):
  # every daily run since creation applied 0 edits (ingest Step 3 already writes
  # Entity Links) while paying a full GBrain extract each time. It still runs on
  # demand and via `wiki-eval.sh --build-links` when a graph golden-row fails.
fi

# daily symptom score — deterministic rebuild from the latest Guava export
DS_OUT=$(bash "$WIKI/.claude/scripts/build-daily-score.sh" --apply 2>&1) || true
printf '%s\n' "$DS_OUT" | grep -q 'changed: 0' || { log "daily-score: $(printf '%s' "$DS_OUT" | grep 'APPLIED' | head -1)"; fixed+=("daily symptom score refreshed"); }

# Calibration (rec ⑤): refresh the precision profile from triaged inbox history
# BEFORE self-interrogation, so newly-filed questions carry the history note.
CAL_OUT=$(bash "$WIKI/.claude/scripts/calibration-capture.sh" --apply 2>&1) || true
printf '%s\n' "$CAL_OUT" | grep -q 'consider tightening' && { log "calibration hints: $(printf '%s' "$CAL_OUT" | grep 'tightening' | tr '\n' ';')"; }

# Self-interrogation (rec ②): file newly-detected structural gaps into the question
# inbox (deduped). New questions become /inbox-triage work — the wiki improving by
# asking itself, not waiting to be asked.
SI_OUT=$(bash "$WIKI/.claude/scripts/self-interrogate.sh" --apply 2>&1) || true
printf '%s\n' "$SI_OUT" | grep -qE 'appended [1-9]' && log "self-interrogate: $SI_OUT"

# Bernard learning loop: distill the conversation log the 07:00 mirror sync pulled
# back into inbox items + the usage profile (north star's "improve from use" arm).
# No-ops until Bernard is deployed and producing logs. Files [bernard] inbox items.
BLN_OUT=$(bash "$WIKI/.claude/scripts/bernard-learn.sh" --apply 2>&1) || true
printf '%s\n' "$BLN_OUT" | grep -qE 'filed [1-9]' && log "bernard-learn: $BLN_OUT"

# Hypothesis register (rec ③): recompile the inline-marker index so the curator
# sees all open inferences/contradictions in one place.
HR_OUT=$(bash "$WIKI/.claude/scripts/build-hypothesis-register.sh" --apply 2>&1) || true
printf '%s\n' "$HR_OUT" | grep -q 'changed' && log "hypothesis-register: $HR_OUT"

# Cross-model adversarial review (rec ④): WEEKLY (Mondays) — two independent Claude
# passes (steelman vs skeptic, Anthropic-only egress) on the top open hypothesis;
# a divergence files a [cross-model] inbox item. Heavy (2 model calls), so gated.
if [[ "$(date +%u)" == "1" ]]; then
  CM_OUT=$(bash "$WIKI/.claude/scripts/cross-model-review.sh" --apply 2>&1) || true
  printf '%s\n' "$CM_OUT" | grep -qE 'DIVERGE|AGREE' && log "cross-model: $CM_OUT"
fi

check "gbrain-sync (daily 03:00)" "$LOGDIR/gbrain-sync.log"     93600  "com.lashawsalta.gbrain-sync"
check "gbrain-dream (nightly)"   "$LOGDIR/gbrain-dream.log"     93600  "com.lashawsalta.gbrain-dream"
check "wiki-mirror-sync (daily)" "$LOGDIR/wiki-mirror-sync.log" 90000  "com.lashawsalta.wiki-mirror-sync"
check "nightly-leak-scan"        "$LOGDIR/leak-scan-status"     172800 "com.life-wiki.scan"
check "daily-ingest (12:00)"     "$LOGDIR/daily-ingest.log"     172800 "com.life-wiki.ingest"
check "daily-synthesis (06:00)"  "$LOGDIR/daily-synthesis.log"  172800 "com.life-wiki.synthesis"
check "wiki-eval (daily 09:15)"  "$LOGDIR/wiki-eval.log"        129600 "com.life-wiki.eval"

# Mirror's last run must have ended in a known terminal state. The log is
# newest-first (wikilog), so the latest run block is the FIRST ~15 lines.
if [[ -f "$LOGDIR/wiki-mirror-sync.log" ]] \
   && ! head -15 "$LOGDIR/wiki-mirror-sync.log" | grep -qE 'sync complete|MIRROR GATE|another sync is running'; then
  issues+=("wiki-mirror-sync: last run did not reach a terminal state (see log)")
fi

# Leak-scan status must be clean — a DEFINITE here means the mirror is gated shut.
if [[ -f "$LOGDIR/leak-scan-status" ]] && ! head -1 "$LOGDIR/leak-scan-status" | grep -q '^clean'; then
  issues+=("leak-scan-status is NOT clean — mirror pushes are gated shut until resolved")
fi

# The PHI gate fails closed without the targets file; surface that early.
[[ -f "$TARGETS" ]] || issues+=("PHI targets file missing at $TARGETS — pre-commit + tripwire fail closed")

# ---- VPS companion check (read-only, over the same SSH path the mirror uses) --
# Alerts only on failed units or unreachability; unit active-states are logged
# informationally because not every bundled unit is necessarily deployed.
VPS_HOST="youruser@your-vps"
vps_out=$(ssh -o ConnectTimeout=10 -o BatchMode=yes "$VPS_HOST" '
  failed=$(systemctl --user --failed --no-legend 2>/dev/null | awk "{print \$1}" | paste -sd, -)
  units=$(systemctl --user list-units --type=service,timer --all --no-legend 2>/dev/null \
    | grep -iE "openclaw|briefs|bernard" | awk "{print \$1\"=\"\$3}" | paste -sd" " -)
  echo "failed=${failed:-none} ${units:-no-matching-units}"' 2>/dev/null)
if [[ -n "$vps_out" ]]; then
  log "vps: $vps_out"
  [[ "$vps_out" == failed=none* ]] || issues+=("VPS: failed systemd user unit(s): ${vps_out%% *}")
else
  issues+=("VPS unreachable over SSH — companion health unknown")
fi

# Informational (logged, never notified)
ingest_count=$(find "$WIKI/ingest" -path "$WIKI/ingest/audio" -prune -o -name "*.md" ! -name ".gitkeep" -print 2>/dev/null | wc -l | tr -d ' ')
inbox_pending=$(grep -c '^- ' "$WIKI/.claude/inbox/wiki-question-inbox.md" 2>/dev/null || true)
log "info: ingest queue=${ingest_count} file(s); question inbox=${inbox_pending:-0} pending line(s)"

# ---- Tier 2: headless Claude diagnosis of whatever Tier 1 couldn't fix -------
# Dedup: if the unresolved issues are IDENTICAL to the previous run's, the
# diagnosis already sits in harness-health-agent.log — re-dispatching headless
# Claude daily to rediscover a known, curator-pending issue is pure token burn
# (it ran 4 days straight on the same leak-gate item, 2026-06-28 → 07-01).
prev_issue_lines=$(awk -F'\t' 'NR==1{s=$1;next} s=="needs-you"{print}' "$LOGDIR/harness-status" 2>/dev/null || true)
cur_issue_lines=$(printf '%s\n' "${issues[@]:-}")
if (( ${#issues[@]} > 0 )) && [[ -n "$prev_issue_lines" && "$cur_issue_lines" == "$prev_issue_lines" ]]; then
  log "Tier 2 skipped: same unresolved issue(s) as last run — diagnosis already in harness-health-agent.log; waiting on curator"
elif (( ${#issues[@]} > 0 )) && [[ -x "$CLAUDE_BIN" ]]; then
  log "Tier 2: dispatching headless Claude for: ${issues[*]}"
  PROMPT="You are the harness-health repair agent for the life wiki on this Mac.
The daily watchdog found issues its deterministic fixes could not resolve:
$(printf -- '- %s\n' "${issues[@]}")
Diagnose each one. You may: read logs in $LOGDIR (both .log and .err files),
inspect launchd state (launchctl print gui/$UID_N/<label>), check crontab -l,
check processes (pgrep), and re-attempt 'launchctl kickstart -k'. Do NOT edit
any file and do NOT touch wiki content. For each issue, end your reply with one
line starting 'DIAGNOSIS: ' summarizing cause and whether you fixed it or what
the curator must do."
  AGENT_OUT=$( (cd "$WIKI" && "$CLAUDE_BIN" -p "$PROMPT" \
      --model sonnet \
      --allowedTools "Read,Bash(launchctl:*),Bash(tail:*),Bash(ls:*),Bash(stat:*),Bash(pgrep:*),Bash(crontab -l)" \
      2>&1) & CPID=$!
    ( sleep 600 && kill "$CPID" 2>/dev/null ) & WPID=$!
    wait "$CPID"; kill "$WPID" 2>/dev/null; true )
  # Newest-first, same convention as wikilog: prepend this dispatch block.
  agent_tmp=$(mktemp)
  {
    echo "▶ $(date '+%Y-%m-%d %H:%M:%S') — harness-health-agent dispatch"
    printf '%s\n\n' "$AGENT_OUT"
    if [ -f "$AGENT_LOG" ]; then cat "$AGENT_LOG"; fi
  } > "$agent_tmp" && mv "$agent_tmp" "$AGENT_LOG"
  diag=$(printf '%s\n' "$AGENT_OUT" | grep '^DIAGNOSIS:' | head -3 | tr '\n' ' ' | cut -c1-180)
  [[ -n "$diag" ]] && log "agent: $diag"
fi

# ---- Outcome ------------------------------------------------------------------
# Persist a machine-readable status line so the alert outlives the ephemeral
# osascript banner. The session-start hook reads this and surfaces any "needs-you"
# at the top of every Claude session — the surface the curator can't miss.
# Line 1 (tab-separated): state \t run-timestamp \t since-date \t issue-count
# Lines 2..n: one issue string each (only when state=needs-you).
# `since` = the date this needs-you streak began, preserved across runs so a
# problem that lingers reads "(since 2026-06-19)" instead of looking brand-new.
STATUS_FILE="$LOGDIR/harness-status"
now_iso=$(date '+%Y-%m-%dT%H:%M:%S'); today=$(date '+%Y-%m-%d')
prev_state=""; prev_since=""
if [[ -f "$STATUS_FILE" ]]; then
  prev_state=$(awk -F'\t' 'NR==1{print $1}' "$STATUS_FILE")
  prev_since=$(awk -F'\t' 'NR==1{print $3}' "$STATUS_FILE")
fi

if (( ${#issues[@]} == 0 && ${#fixed[@]} == 0 )); then
  log "all green"
  printf 'green\t%s\t%s\t0\n' "$now_iso" "$today" > "$STATUS_FILE"
elif (( ${#issues[@]} == 0 )); then
  log "fixed: ${fixed[*]}"
  notify "Fixed automatically: ${fixed[*]}"
  printf 'fixed\t%s\t%s\t0\n' "$now_iso" "$today" > "$STATUS_FILE"
  { printf 'fixed: %s\n' "${fixed[*]}"; } >> "$STATUS_FILE"
else
  log "needs you: ${issues[*]}"
  notify "Needs you: ${issues[0]}$( (( ${#issues[@]} > 1 )) && printf ' (+%d more — see harness-health.log)' $(( ${#issues[@]} - 1 )) )"
  if [[ "$prev_state" == "needs-you" && -n "$prev_since" ]]; then since="$prev_since"; else since="$today"; fi
  { printf 'needs-you\t%s\t%s\t%d\n' "$now_iso" "$since" "${#issues[@]}"
    printf '%s\n' "${issues[@]}"; } > "$STATUS_FILE"
fi
log "=== harness-health run finished ==="
