#!/usr/bin/env bash
# daily-ingest-check.sh
# Runs structural lint first. Auto-ingests only if lint is clean (0 critical).
# If lint has critical issues: notifies and exits without ingesting.
#
# Lint is split in two layers:
#   1. wiki-lint-structural.sh — bash, runs here, checks frontmatter/sidecars/handoff/sources
#   2. /lint Claude skill — semantic checks (injection, contradictions, citations)
#      Run the skill manually in a Claude Code session when deeper analysis is needed.
#
# To enable fully autonomous ingest (no permission prompts), add
# --dangerously-skip-permissions to CLAUDE_INGEST_FLAGS below.
set -uo pipefail

HOME_DIR="/Users/lashawsalta"
WIKI_DIR="$HOME_DIR/life-wiki"
CLAUDE_BIN="/opt/homebrew/bin/claude"
LINT_SCRIPT="$WIKI_DIR/.claude/scripts/wiki-lint-structural.sh"
LOG_DIR="$WIKI_DIR/.claude/logs"

# Add --dangerously-skip-permissions here to allow headless auto-ingest:
# Ingest extracts health claims + citations — hardest tier per the CLAUDE.md
# model policy. No --model flag: inherits the configured default so it always
# runs on the latest top-tier model (curator decision 2026-06-12: never pin
# the smart tier to a model id). Never downgrade this one.
CLAUDE_INGEST_FLAGS="--print"

mkdir -p "$LOG_DIR"
source "$WIKI_DIR/.claude/scripts/lib/wikilog.sh"
wikilog_open "daily-ingest"
LOG_FILE="$WIKILOG_BUF"
trap 'wikilog_flush' EXIT

DATE_TAG=$(date '+%Y-%m-%d %H:%M:%S')
log() { printf '[%s] %s\n' "$DATE_TAG" "$1" >> "$LOG_FILE"; }

notify() {
    /usr/bin/osascript \
        -e "display notification \"$1\" with title \"Life Wiki\" sound name \"Ping\"" \
        2>/dev/null || true
}

log "=== daily-ingest-check started ==="

# Count ingest-ready .md files in the flat ingest/ root (matches /ingest skill Step 1:
# files land flat — no subdirs; excludes gitkeep, smoketest, queue, and sidecars).
INGEST_COUNT=$(find "$WIKI_DIR/ingest" -maxdepth 1 \
    -name "*.md" ! -name ".gitkeep" ! -name "smoketest*" ! -name "queue*" \
    2>/dev/null | wc -l | tr -d '[:space:]')

if [ "$INGEST_COUNT" -eq 0 ]; then
    log "ingest/ is empty — nothing to do."
    notify "Life Wiki: no files pending ingest."
    exit 0
fi

# Shared write-lock: files are pending and we're about to ingest (writes wiki +
# git index). Defer if another writer (interactive session or sibling job) holds
# it; otherwise take it and release on exit. Next scheduled run retries.
source "$WIKI_DIR/.claude/scripts/lib/wiki-lock.sh"
if ! wiki_lock_acquire "daily-ingest"; then
    log "wiki-write lock held by '$(wiki_lock_holder)' (since $(wiki_lock_since)) — deferring this run."
    exit 0
fi
trap 'wiki_lock_release; wikilog_flush' EXIT

log "Found $INGEST_COUNT file(s) in ingest/. Running structural lint..."

# Run structural lint (bash — works in any runtime, no model required)
LINT_OUTPUT=$(bash "$LINT_SCRIPT" 2>&1) || true
printf '%s\n' "$LINT_OUTPUT" >> "$LOG_FILE"

SUMMARY_LINE=$(printf '%s\n' "$LINT_OUTPUT" | grep -i '^Summary:' || true)

if [ -z "$SUMMARY_LINE" ]; then
    log "ERROR: wiki-lint-structural.sh produced no Summary line. Check the script."
    notify "Life Wiki: structural lint failed — check .claude/logs/daily-ingest.log"
    exit 1
fi

CRITICAL_COUNT=$(printf '%s\n' "$SUMMARY_LINE" \
    | grep -oE '[0-9]+ critical' | grep -oE '^[0-9]+' || echo "0")
CRITICAL_COUNT="${CRITICAL_COUNT:-0}"

if [ "$CRITICAL_COUNT" -gt 0 ]; then
    log "Structural lint: $CRITICAL_COUNT critical issue(s). Ingest blocked — fix and re-run."
    notify "Life Wiki: $CRITICAL_COUNT critical lint issue(s) — fix before next ingest."
    exit 0
fi

log "Structural lint clean ($CRITICAL_COUNT critical). Auto-ingesting $INGEST_COUNT file(s)..."
notify "Life Wiki: lint clean — auto-ingesting $INGEST_COUNT file(s)."

# Run batch ingest via Claude Code. The prompt instructs the model to follow
# the ingest skill workflow — slash commands are not valid in --print mode.
INGEST_PROMPT="Execute the ingest workflow documented in .claude/skills/ingest/SKILL.md, \
following every step in order. All files land flat in ingest/ root (no subdirs) and are \
pre-sanitized — process every pending .md regardless of sidecar tier or flags; determine \
routing and speaker roles from content, not the sidecar. For each file: \
(Step 0) run wiki-lint-structural.sh and fix any critical issues first; \
(Step 1) inventory pending files; \
(Step 2/2a) route by content and move BOTH the .md and its paired .meta.json sidecar to the destination raw/ folder; \
(Step 3) read the full content, extract entities (providers/conditions/medications/biomarkers), \
populate structured frontmatter, update each entity page's timeline, and add an '## Entity Links' \
section with inline body wikilinks; \
(Step 4) update the GBrain index: gbrain import ~/life-wiki/wikis/ --no-embed && gbrain embed --stale && gbrain extract links --source db; \
(Step 4.5) run post-ingest-verify.sh and confirm it exits 0; \
(Step 5) close out — add a wikis/sources.md row per moved file, append to the domain log.md, \
update AGENT-HANDOFF.md, and confirm no orphaned .meta.json remain in ingest/. \
Never recommend medication changes or diagnoses; cite every health claim with a wikilink. \
Report a summary when done."

# shellcheck disable=SC2086
INGEST_OUTPUT=$(cd "$WIKI_DIR" \
    && "$CLAUDE_BIN" $CLAUDE_INGEST_FLAGS "$INGEST_PROMPT" 2>&1) || true
printf '%s\n' "$INGEST_OUTPUT" >> "$LOG_FILE"

log "Ingest run complete. Review $LOG_FILE for details."

# Post-ingest (curator 2026-06-14): new content just landed — rebuild the graph
# relationships now (backlinks/timeline/hypotheses + self-interrogate) so they
# reflect it same-day instead of waiting for the 08:00 watchdog. No --sync here:
# the mirror push is left to the next gated daily sync, after the nightly 02:30
# leak scan has vetted the freshly-ingested content.
log "Post-ingest: running self-improvement chain..."
SI_OUT=$(bash "$WIKI_DIR/.claude/scripts/self-improve.sh" 2>&1) || true
printf '%s\n' "$SI_OUT" >> "$LOG_FILE"

notify "Life Wiki: ingest run done — review .claude/logs/daily-ingest.log"
