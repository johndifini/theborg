#!/bin/bash
# Wrapper invoked by launchd to run a scheduled task in an agent's working dir.
# Usage: run-scheduled-task.sh <agent-dir> <prompt-file>
set -euo pipefail

AGENT_DIR="$1"
PROMPT_FILE="$2"

if [[ ! -d "$AGENT_DIR" ]]; then
  echo "agent dir not found: $AGENT_DIR" >&2
  exit 64
fi
if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "prompt file not found: $PROMPT_FILE" >&2
  exit 64
fi

TASK_NAME="$(basename "$PROMPT_FILE" .prompt)"
LOG_DIR="$AGENT_DIR/.claude/scheduled/logs"
LOG_FILE="$LOG_DIR/$TASK_NAME.log"
mkdir -p "$LOG_DIR"

# launchd starts jobs with a minimal PATH and does not source any shell
# profile, so `claude` (and anything else installed via Homebrew, nvm, etc.)
# won't be found. The user keeps PATH in ~/.zshenv — source it before
# resolving CLAUDE_BIN. Errors are swallowed so a profile hiccup never
# blocks the task; if claude still can't be resolved we'll fail loudly below.
if [[ -f "$HOME/.zshenv" ]]; then
  # shellcheck disable=SC1091
  set +u
  source "$HOME/.zshenv" 2>/dev/null || true
  set -u
fi

CLAUDE_BIN="${CLAUDE_BIN:-claude}"
if ! command -v "$CLAUDE_BIN" >/dev/null 2>&1; then
  echo "claude binary not found on PATH after sourcing ~/.zshenv (PATH=$PATH)" >&2
  exit 127
fi

# BORG_ROOT: workspace root, auto-detected from this script's location
# (.bin/ sits at the workspace root). Override by exporting BORG_ROOT
# before invocation. Prompts reference paths as ${BORG_ROOT}/... and the
# runner substitutes the literal token below.
BORG_ROOT="${BORG_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export BORG_ROOT

# Pin a session id for this run so notifications (notify-email.sh) can tell the user
# how to resume this exact headless session: `claude --resume $BORG_SESSION_ID`.
# Lowercased — claude stores/looks up session ids in lowercase.
SESSION_ID="$(uuidgen | tr '[:upper:]' '[:lower:]')"
export BORG_SESSION_ID="$SESSION_ID"

cd "$AGENT_DIR"

# Render the prompt: substitute only ${BORG_ROOT}. Bash parameter
# expansion (no envsubst dependency) — leaves all other $-tokens alone,
# so literal `$50`, regex `$1`, etc. in prompts pass through untouched.
PROMPT_CONTENT=$(<"$PROMPT_FILE")
PROMPT_CONTENT=${PROMPT_CONTENT//\$\{BORG_ROOT\}/$BORG_ROOT}

# Per-task effort. Every scheduled job runs at "high"; the weekly "dream" harvest
# reasons over dozens of transcripts, so it gets "xhigh" to match an interactive Opus
# run (a lower-effort headless pass under-harvests). Override per task in the case below.
EFFORT=high
case "$TASK_NAME" in
  c4po-dream) EFFORT=xhigh ;;
esac

# Per-task extra CLI args. The backlog burndown edits files across the whole
# workspace (root BACKLOG.md, sibling agents, the git-ignored repos/*), not
# just its agent dir — grant it the workspace root as an additional working
# directory. Other tasks stay confined to their agent dir.
EXTRA_ARGS=()
case "$TASK_NAME" in
  c4po-backlog-burndown) EXTRA_ARGS+=(--add-dir "$BORG_ROOT") ;;
esac

# --strict-mcp-config: a scheduled `claude -p` run must NOT spawn the telegram
# channel's MCP server. server.ts kills whatever poller holds bot.pid, so a
# scheduled run would silently clobber the agent's interactive session poller
# and leave it deaf to Telegram. Scheduled tasks send outbound via
# .bin/notify-email.sh instead.
#
# --session-id pins the run to $SESSION_ID so the notification can hand the user a
# `claude --resume` command pointing at this exact session.
# Agent slug (c4po | mrs-beast | warren-bot-fett) — labels failure emails and
# is the first arg notify-email.sh expects.
AGENT_NAME="$(basename "$AGENT_DIR")"

# Run the task, capturing its exit code instead of letting `set -e` abort here:
# on failure we still need to notify and to preserve the code for launchd. The
# `end` marker moves outside the block so it always records, pass or fail
# (previously a failed run left no end line in the log).
STATUS=0
{
  echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) start $TASK_NAME (cwd=$AGENT_DIR, session=$SESSION_ID) ====="
  "$CLAUDE_BIN" -p "$PROMPT_CONTENT" --session-id "$SESSION_ID" --strict-mcp-config --effort "$EFFORT" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} < /dev/null
} >> "$LOG_FILE" 2>&1 || STATUS=$?
echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) end $TASK_NAME (exit $STATUS) =====" >> "$LOG_FILE" 2>&1

# On any non-zero exit, email the user. A scheduled run is fired once by launchd
# (no KeepAlive, no retry loop), so a failure means this run's work is dropped
# until the next scheduled fire — including usage-limit misses, which do NOT
# self-heal. Notify on every failure; the subject distinguishes a usage-limit
# miss (re-runnable now once the cap resets) from a hard failure, without
# suppressing either.
if [[ $STATUS -ne 0 ]]; then
  LOG_TAIL="$(tail -n 25 "$LOG_FILE" 2>/dev/null || true)"
  if grep -qiE 'hit your (session|usage) limit|session limit|usage limit' <<<"$LOG_TAIL"; then
    SUBJECT="[Borg/$AGENT_NAME] scheduled task hit usage limit: $TASK_NAME"
  else
    SUBJECT="[Borg/$AGENT_NAME] scheduled task FAILED: $TASK_NAME (exit $STATUS)"
  fi
  {
    echo "Scheduled task '$TASK_NAME' exited $STATUS."
    echo "  agent:   $AGENT_NAME"
    echo "  session: $SESSION_ID"
    echo "  log:     $LOG_FILE"
    echo
    echo "Last lines of the log:"
    echo "$LOG_TAIL"
  } | "$BORG_ROOT/.bin/notify-email.sh" "$AGENT_NAME" "$SUBJECT" \
    || echo "notify-email.sh failed to send failure alert for $TASK_NAME" >> "$LOG_FILE" 2>&1
fi

# Re-exit with the task's own code so `launchctl list` reflects reality.
exit $STATUS
