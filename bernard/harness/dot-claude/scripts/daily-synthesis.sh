#!/usr/bin/env bash
# daily-synthesis.sh
# Delta-driven synthesis pass: mines what changed since the last pass for
# novel connections, contradictions, and pattern updates, appending to
# wikis/health/wiki/holistic-health-synthesis.md per .claude/skills/synthesis-pass/SKILL.md.
#
# Scheduled DAILY by com.life-wiki.synthesis (06:00 — after dream 03:15 and
# leak scan 02:30). Cheap on quiet days: a bash snapshot gate (git HEAD +
# working-tree state of wikis/) exits before invoking Claude when nothing
# changed since the last completed pass. The pass itself runs an on-demand
# mirror sync, so results reach Bernard same-day regardless of the 07:00 cron.
# Manual run: bash .claude/scripts/daily-synthesis.sh
#
# Runs structural lint before the pass; skips (and notifies) on critical
# issues so synthesis never builds on a structurally broken graph.
set -uo pipefail

HOME_DIR="/Users/lashawsalta"
WIKI_DIR="$HOME_DIR/life-wiki"
CLAUDE_BIN="/opt/homebrew/bin/claude"
LINT_SCRIPT="$WIKI_DIR/.claude/scripts/wiki-lint-structural.sh"
LOG_DIR="$WIKI_DIR/.claude/logs"
STATE_FILE="$LOG_DIR/synthesis-state"

# Headless writes need explicit tool grants. Scoped: read anything, edit/write
# wiki pages (guard-wiki.py still denies raw/ once hooks are registered), run
# only the wiki's own scripts + gbrain + read-only git.
ALLOWED_TOOLS="Read,Glob,Grep,Edit,Write,Bash(gbrain:*),Bash(bash .claude/scripts/:*),Bash(git log:*),Bash(git status:*),Bash(git diff:*)"

mkdir -p "$LOG_DIR"
source "$WIKI_DIR/.claude/scripts/lib/wikilog.sh"
wikilog_open "daily-synthesis"
LOG_FILE="$WIKILOG_BUF"
trap 'wikilog_flush' EXIT

DATE_TAG=$(date '+%Y-%m-%d %H:%M:%S')
log() { printf '[%s] %s\n' "$DATE_TAG" "$1" >> "$LOG_FILE"; }

notify() {
    /usr/bin/osascript \
        -e "display notification \"$1\" with title \"Life Wiki\" sound name \"Ping\"" \
        2>/dev/null || true
}

# Snapshot of wiki content state: HEAD commit + working-tree changes under
# wikis/. Any ingest, edit, or commit changes it; an idle wiki does not.
snapshot() {
    (cd "$WIKI_DIR" && { git rev-parse HEAD; git status --porcelain -- wikis/; } \
        | /usr/bin/shasum | cut -d' ' -f1)
}

log "=== daily-synthesis started ==="

SNAP=$(snapshot)
if [[ -f "$STATE_FILE" ]] && [[ "$(cat "$STATE_FILE")" == "$SNAP" ]]; then
    log "no wiki delta since last completed pass — skipping (no Claude run)."
    exit 0
fi

# Shared write-lock: a delta exists and this pass is about to write. Defer if
# another writer (interactive session or sibling job) holds the lock; otherwise
# take it and release on exit. Prevents the parallel-write/shared-index race.
source "$WIKI_DIR/.claude/scripts/lib/wiki-lock.sh"
if ! wiki_lock_acquire "daily-synthesis"; then
    log "wiki-write lock held by '$(wiki_lock_holder)' (since $(wiki_lock_since)) — deferring this pass."
    exit 0
fi
trap 'wiki_lock_release; wikilog_flush' EXIT

# Lint gate — never synthesize on top of a structurally broken graph.
LINT_OUTPUT=$(bash "$LINT_SCRIPT" 2>&1) || true
printf '%s\n' "$LINT_OUTPUT" >> "$LOG_FILE"

SUMMARY_LINE=$(printf '%s\n' "$LINT_OUTPUT" | grep -i '^Summary:' || true)
CRITICAL_COUNT=$(printf '%s\n' "$SUMMARY_LINE" \
    | grep -oE '[0-9]+ critical' | grep -oE '^[0-9]+' || echo "0")
CRITICAL_COUNT="${CRITICAL_COUNT:-0}"

if [ -z "$SUMMARY_LINE" ] || [ "$CRITICAL_COUNT" -gt 0 ]; then
    log "Structural lint not clean ($CRITICAL_COUNT critical) — synthesis pass skipped."
    notify "Life Wiki: synthesis skipped — $CRITICAL_COUNT critical lint issue(s)."
    exit 0
fi

log "Wiki delta detected and lint clean. Running synthesis pass..."

SYNTH_PROMPT="Execute the synthesis-pass workflow documented in \
.claude/skills/synthesis-pass/SKILL.md, following every step in order. \
Read AGENT-HANDOFF.md first. Determine the window from the latest dated entry \
in the Synthesis Log section of wikis/health/wiki/holistic-health-synthesis.md \
(fallback 2026-06-09). Build the delta from git log + sources.md, pull graph \
context via gbrain graph-query/orphans and .claude/scripts/wiki-query, then \
mine each substantive new fact: pattern updates, contradictions (per \
.claude/skills/contradiction-review/SKILL.md — preserve, never resolve), and new \
multi-source chains. Append a dated entry to the Synthesis Log (append-only), \
update compiled patterns in place only when their status genuinely changes, \
cross-link entity pages both directions. If the delta contains no substantive \
new facts (mechanical changes only), append a one-line no-delta entry and \
stop. Then reindex GBrain (import --no-embed, embed --stale, extract links \
--source db) and run bash .claude/scripts/vps-mirror-sync.sh. Update \
AGENT-HANDOFF.md. Never recommend medication changes, doses, or diagnoses; \
cite every health claim with a wikilink; mark uncited inference as Hypothesis. \
Never edit raw/ or ingest/ files. Report a summary when done."

# Smart tier (CLAUDE.md model policy): /synthesis-pass requires PHI judgment +
# source-hierarchy reasoning. No --model flag — inherits the configured default
# so it always runs on the latest top-tier model. Never pin, never downgrade.
# Capture Claude's exit code and output to a temp file so a FAILED run (model
# unavailable, rate limit, timeout) is NOT mistaken for a completed pass — the
# old code unconditionally advanced the snapshot state, so a failure was logged
# as success and never retried until the next wiki delta.
SYNTH_TMP=$(mktemp "${TMPDIR:-/tmp}/daily-synthesis.XXXXXX")
(cd "$WIKI_DIR" && "$CLAUDE_BIN" -p "$SYNTH_PROMPT" \
    --allowedTools "$ALLOWED_TOOLS" \
    > "$SYNTH_TMP" 2>&1) & CPID=$!
( sleep 2700 && kill "$CPID" 2>/dev/null ) & WPID=$!
wait "$CPID"; SYNTH_RC=$?
kill "$WPID" 2>/dev/null; wait "$WPID" 2>/dev/null || true
SYNTH_OUTPUT=$(cat "$SYNTH_TMP"); rm -f "$SYNTH_TMP"
printf '%s\n' "$SYNTH_OUTPUT" >> "$LOG_FILE"

# Treat as failure if: non-zero exit (incl. 143 = timeout kill), a known
# model-unavailability/limit signature in the output, or empty output (Claude
# was invoked because a delta exists, so a real pass always prints a summary).
if [ "$SYNTH_RC" -ne 0 ] \
   || printf '%s' "$SYNTH_OUTPUT" | grep -qiE "currently unavailable|usage limit|rate limit|overloaded|api error" \
   || [ "$(printf '%s' "$SYNTH_OUTPUT" | tr -d '[:space:]' | wc -c | tr -d '[:space:]')" -lt 20 ]; then
    log "ERROR: synthesis Claude run failed (rc=$SYNTH_RC) — state NOT advanced; will retry next run."
    notify "Life Wiki: synthesis FAILED — see daily-synthesis.log; will retry next run."
    exit 1
fi

# Record post-pass state so tomorrow's gate skips unless something new lands.
# (The pass's own edits are part of this snapshot by design.) Only reached on
# a confirmed-successful pass.
snapshot > "$STATE_FILE"

log "Synthesis pass complete. Review $LOG_FILE for details."
notify "Life Wiki: daily synthesis pass done — see .claude/logs/daily-synthesis.log"
