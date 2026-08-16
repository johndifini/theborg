#!/bin/bash
# weekly-reset.sh — report the next weekly usage-limit reset for a harness.
#
# Why this exists: jobs that deliberately spend the tail of a weekly budget (the
# backlog burndown) need to know when that budget rolls over. The reset is an
# ACCOUNT fact, not a vendor constant — it differs per user — so it must never be
# hardcoded into a schedule or copied between files.
#
# What can actually be derived, verified 2026-08-16:
#   codex   YES. Session rollouts under $CODEX_HOME/sessions/ carry
#           `"rate_limits":{"primary":{"window_minutes":10080,"resets_at":<epoch>}}`.
#           10080 minutes is exactly 7 days, so that entry IS the weekly window.
#           Note the window is ROLLING (anchored to first use), so the reset
#           drifts — two observed samples were 26.01 days apart, not a multiple
#           of 7. That is precisely why callers must read this at the moment of
#           use rather than cache it.
#   claude  NO. There is no usage/limit subcommand, `claude auth status` returns
#           only login state, and nothing under ~/.claude persists a reset time
#           (grep for resets_at/window_minutes finds zero hits). The only reset
#           string Claude records is prose on a limit hit, and it describes the
#           5-hour rolling session window, not the weekly one. `/usage` shows the
#           weekly reset but is interactive-only. So the claude value is stated
#           by the user via $BORG_CLAUDE_RESET and audited monthly (Assumption H
#           in c4po/.claude/scheduled/c4po-assumptions-audit-monthly.prompt).
#
# Usage:
#   .bin/weekly-reset.sh                  report for $BORG_HARNESS (default claude)
#   .bin/weekly-reset.sh --harness codex  report for a specific harness
#
# Output is KEY=VALUE lines on stdout. Exit 0 when the reset is known, 3 when it
# is not. Callers should treat 3 as "proceed, but say so" rather than as a hard
# error — see the fail-open note at the bottom of this file.
set -uo pipefail

HARNESS="${BORG_HARNESS:-claude}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --harness) HARNESS="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "usage: $(basename "$0") [--harness claude|codex]" >&2; exit 64 ;;
  esac
done

case "$HARNESS" in
  claude|codex) ;;
  *) echo "invalid harness: '$HARNESS' (expected 'claude' or 'codex')" >&2; exit 64 ;;
esac

emit_unknown() {
  printf 'harness=%s\nsource=none\nknown=no\nreason=%s\n' "$HARNESS" "$1"
  exit 3
}

# Render an epoch as both machine and human forms. `date -r` is BSD/macOS.
emit_known() {
  local epoch="$1" source="$2" extra="${3:-}"
  printf 'harness=%s\nsource=%s\nknown=yes\nreset_epoch=%s\nreset_local=%s\nseconds_until=%s\n' \
    "$HARNESS" "$source" "$epoch" \
    "$(date -r "$epoch" '+%Y-%m-%d %H:%M %Z (%A)')" \
    "$(( epoch - $(date +%s) ))"
  [[ -n "$extra" ]] && printf '%s\n' "$extra"
  exit 0
}

if [[ "$HARNESS" == codex ]]; then
  CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
  [[ -d "$CODEX_DIR" ]] || emit_unknown "no codex home at $CODEX_DIR"

  # Newest rollout carrying a non-null weekly window wins. Scanning is capped:
  # a machine with years of sessions should not pay for a full-tree grep, and
  # anything older than the last few dozen sessions is stale enough to be
  # useless anyway. `window_minutes":10080` pins it to the WEEKLY entry so a
  # future 5-hour `primary` can never be mistaken for it.
  reset_epoch=""
  while IFS= read -r f; do
    line="$(grep -oE '"primary":\{"used_percent":[0-9.]+,"window_minutes":10080,"resets_at":[0-9]+\}' "$f" 2>/dev/null | tail -1)"
    if [[ -n "$line" ]]; then
      reset_epoch="${line##*:}"
      reset_epoch="${reset_epoch%\}}"
      break
    fi
  done < <(find "$CODEX_DIR/sessions" "$CODEX_DIR/archived_sessions" \
             -name 'rollout-*.jsonl' -type f -print0 2>/dev/null \
             | xargs -0 ls -t 2>/dev/null | head -60)

  [[ -n "$reset_epoch" ]] || emit_unknown "no weekly rate_limits entry in the 60 newest codex rollouts"

  # A reset in the past means the window already rolled over and codex has not
  # run since. Report it as unknown rather than handing back a stale timestamp a
  # caller would compare against now() and misread as "reset imminent".
  if (( reset_epoch <= $(date +%s) )); then
    emit_unknown "newest codex reset ($(date -r "$reset_epoch" '+%Y-%m-%d %H:%M %Z')) is in the past; run codex to refresh it"
  fi

  emit_known "$reset_epoch" "codex-rollout" "window_minutes=10080"
fi

# claude: stated, not derived. Format is "<dayabbr> HH:MM" in local time, e.g.
# BORG_CLAUDE_RESET="wed 11:00". Read it from ~/.zshenv so both interactive
# shells and launchd jobs see the same value.
RESET_SPEC="${BORG_CLAUDE_RESET:-}"
[[ -n "$RESET_SPEC" ]] || emit_unknown "BORG_CLAUDE_RESET is not set (read the weekly reset from /usage in an interactive Claude Code session, then export it from ~/.zshenv as e.g. 'wed 11:00')"

day="$(printf '%s' "$RESET_SPEC" | awk '{print tolower($1)}')"
time_part="$(printf '%s' "$RESET_SPEC" | awk '{print $2}')"
case "$day" in
  sun|mon|tue|wed|thu|fri|sat) ;;
  *) emit_unknown "BORG_CLAUDE_RESET='$RESET_SPEC' — first field must be a 3-letter weekday (sun..sat)" ;;
esac
[[ "$time_part" =~ ^([0-9]{1,2}):([0-9]{2})$ ]] \
  || emit_unknown "BORG_CLAUDE_RESET='$RESET_SPEC' — second field must be HH:MM (24-hour)"
hh="${BASH_REMATCH[1]}"; mm="${BASH_REMATCH[2]}"
(( 10#$hh <= 23 && 10#$mm <= 59 )) \
  || emit_unknown "BORG_CLAUDE_RESET='$RESET_SPEC' — time out of range"

# `date -v+<dayabbr>` lands on the NEXT such weekday, except when today already
# is that weekday, where it stays on today. That is the behavior we want, but it
# leaves one edge: fired after the reset hour on reset day, it returns a time
# already past. Roll forward a week in that case so the answer is always the
# NEXT reset.
epoch="$(date -v+"$day" -v"${hh}"H -v"${mm}"M -v0S '+%s' 2>/dev/null)"
[[ -n "$epoch" ]] || emit_unknown "could not compute a date from BORG_CLAUDE_RESET='$RESET_SPEC'"
if (( epoch <= $(date +%s) )); then
  epoch="$(date -r "$epoch" -v+1w '+%s')"
fi

emit_known "$epoch" "configured" "spec=$RESET_SPEC"

# Fail-open, deliberately. A caller that cannot determine the reset should run
# and say so, not abort: on a fresh fork nothing is configured yet, and a job
# that silently never fires is a worse failure than one that fires at a
# suboptimal hour. The cost of guessing wrong is a wasted portion of one week's
# budget; the cost of aborting is a feature that appears broken with no signal.
