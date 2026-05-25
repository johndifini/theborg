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

cd "$AGENT_DIR"

# Render the prompt: substitute only ${BORG_ROOT}. Bash parameter
# expansion (no envsubst dependency) — leaves all other $-tokens alone,
# so literal `$50`, regex `$1`, etc. in prompts pass through untouched.
PROMPT_CONTENT=$(<"$PROMPT_FILE")
PROMPT_CONTENT=${PROMPT_CONTENT//\$\{BORG_ROOT\}/$BORG_ROOT}

# --strict-mcp-config: a scheduled `claude -p` run must NOT spawn the telegram
# channel's MCP server. server.ts kills whatever poller holds bot.pid, so a
# scheduled run would silently clobber the agent's interactive session poller
# and leave it deaf to Telegram. Scheduled tasks send outbound via
# .bin/notify-telegram.sh instead.
{
  echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) start $TASK_NAME (cwd=$AGENT_DIR) ====="
  "$CLAUDE_BIN" -p "$PROMPT_CONTENT" --strict-mcp-config < /dev/null
  echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) end $TASK_NAME ====="
} >> "$LOG_FILE" 2>&1
