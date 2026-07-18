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
# profile, so `claude`/`codex` (and anything else installed via Homebrew, nvm,
# etc.) won't be found. The user keeps PATH in ~/.zshenv — source it before
# resolving the CLI binary. Errors are swallowed so a profile hiccup never
# blocks the task; if the binary still can't be resolved we'll fail loudly below.
if [[ -f "$HOME/.zshenv" ]]; then
  # shellcheck disable=SC1091
  set +u
  source "$HOME/.zshenv" 2>/dev/null || true
  set -u
fi

# Per-task CLI. The backlog burndown burns the *OpenAI* weekly budget, so it
# runs on Codex; every other task runs on Claude.
CLI=claude
case "$TASK_NAME" in
  c4po-backlog-burndown) CLI=codex ;;
esac

if [[ "$CLI" == codex ]]; then
  CODEX_BIN="${CODEX_BIN:-codex}"
  if ! command -v "$CODEX_BIN" >/dev/null 2>&1; then
    echo "codex binary not found on PATH after sourcing ~/.zshenv (PATH=$PATH)" >&2
    exit 127
  fi
else
  CLAUDE_BIN="${CLAUDE_BIN:-claude}"
  if ! command -v "$CLAUDE_BIN" >/dev/null 2>&1; then
    echo "claude binary not found on PATH after sourcing ~/.zshenv (PATH=$PATH)" >&2
    exit 127
  fi
fi

# BORG_ROOT: workspace root, auto-detected from this script's location
# (.bin/ sits at the workspace root). Override by exporting BORG_ROOT
# before invocation. Prompts reference paths as ${BORG_ROOT}/... and the
# runner substitutes the literal token below.
BORG_ROOT="${BORG_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export BORG_ROOT

# Resume handle for notification footers (notify-email.sh).
# - claude: pin a session id up front (`claude --resume $BORG_SESSION_ID`).
#   Lowercased — claude stores/looks up session ids in lowercase.
# - codex: no way to pre-pin an id (codex assigns one at launch), so export a
#   generic resume command for emails sent mid-run; after the run we upgrade
#   the failure email to the exact id parsed from the log. `codex resume --last`
#   scopes to the cwd the footer cd's into, which only this task uses.
SESSION_ID=""
if [[ "$CLI" == codex ]]; then
  export BORG_RESUME_CMD="codex resume --last"
else
  SESSION_ID="$(uuidgen | tr '[:upper:]' '[:lower:]')"
  export BORG_SESSION_ID="$SESSION_ID"
fi

cd "$AGENT_DIR"

# Render the prompt: substitute only ${BORG_ROOT}. Bash parameter
# expansion (no envsubst dependency) — leaves all other $-tokens alone,
# so literal `$50`, regex `$1`, etc. in prompts pass through untouched.
PROMPT_CONTENT=$(<"$PROMPT_FILE")
PROMPT_CONTENT=${PROMPT_CONTENT//\$\{BORG_ROOT\}/$BORG_ROOT}

# Per-task effort (claude tasks only; codex tasks use the model/effort defaults
# from ~/.codex/config.toml). Every claude job runs at "high"; the weekly "dream"
# harvest reasons over dozens of transcripts, so it gets "xhigh" to match an
# interactive Opus run (a lower-effort headless pass under-harvests).
EFFORT=high
case "$TASK_NAME" in
  c4po-dream) EFFORT=xhigh ;;
esac

# Per-task extra CLI args (claude and codex both accept --add-dir). The backlog
# burndown edits files across the whole workspace (root BACKLOG.md, sibling
# agents, the git-ignored repos/*), not just its agent dir — grant it the
# workspace root as an additional working directory. Other tasks stay confined
# to their agent dir.
#
# waiq-tts-watch reads untrusted web content, so it runs read-only: only
# WebSearch/WebFetch are allowed (no Write/Bash — a fetched page can't
# prompt-inject changes into the repo). No --bare: bare mode skips the OAuth
# resolution path, silently ignoring CLAUDE_CODE_OAUTH_TOKEN — the only
# working headless auth here (verified 2026-07-18, CLI 2.1.212; see
# anthropics/claude-code#38022).
EXTRA_ARGS=()
case "$TASK_NAME" in
  c4po-backlog-burndown) EXTRA_ARGS+=(--add-dir "$BORG_ROOT") ;;
  waiq-tts-watch) EXTRA_ARGS+=(--permission-mode dontAsk \
    --allowedTools "WebSearch,WebFetch" --model claude-sonnet-5 --max-turns 40) ;;
esac

# Per-task report file. Most tasks email their own results from inside the
# session (their .prompt pipes to notify-email.sh). A read-only task can't —
# it has no Bash — so the runner captures the model's stdout as a dated report
# and emails it on success (failure emailing below covers the rest).
REPORT_FILE=""
case "$TASK_NAME" in
  waiq-tts-watch) REPORT_FILE="$AGENT_DIR/.claude/scheduled/reports/$(date +%Y-%m-%d).md" ;;
esac

# claude flags:
# --strict-mcp-config: a scheduled `claude -p` run must not boot any
# session-configured MCP server — outbound goes via .bin/notify-email.sh
# only. (No codex equivalent needed: codex loads MCP servers only from
# ~/.codex/config.toml.)
# --session-id pins the run to $SESSION_ID so the notification can hand the user a
# `claude --resume` command pointing at this exact session.
#
# codex flags:
# --sandbox workspace-write: codex defaults headless runs to a read-only
# sandbox; the task must write (and --add-dir extends the writable roots).
# -c sandbox_workspace_write.network_access=true: workspace-write blocks
# network by default, which would break notify-email.sh's SMTP curl and any
# child `codex exec` the task spawns (the child's API calls run under this
# sandbox). Model and reasoning effort are deliberately NOT set — the defaults
# come from ~/.codex/config.toml.
#
# Agent slug (c4po | mrs-beast | warren-bot-fett) — labels failure emails and
# is the first arg notify-email.sh expects.
AGENT_NAME="$(basename "$AGENT_DIR")"

# Run the task, capturing its exit code instead of letting `set -e` abort here:
# on failure we still need to notify and to preserve the code for launchd. The
# `end` marker moves outside the block so it always records, pass or fail
# (previously a failed run left no end line in the log).
STATUS=0
{
  echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) start $TASK_NAME (cwd=$AGENT_DIR, cli=$CLI, session=${SESSION_ID:-codex-assigned}) ====="
  if [[ "$CLI" == codex ]]; then
    "$CODEX_BIN" exec --sandbox workspace-write -c sandbox_workspace_write.network_access=true ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} "$PROMPT_CONTENT" < /dev/null
  elif [[ -n "$REPORT_FILE" ]]; then
    # Report task: model stdout IS the report; stderr/markers stay in the log.
    mkdir -p "$(dirname "$REPORT_FILE")"
    "$CLAUDE_BIN" -p "$PROMPT_CONTENT" --session-id "$SESSION_ID" --strict-mcp-config --effort "$EFFORT" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} < /dev/null > "$REPORT_FILE"
  else
    "$CLAUDE_BIN" -p "$PROMPT_CONTENT" --session-id "$SESSION_ID" --strict-mcp-config --effort "$EFFORT" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} < /dev/null
  fi
} >> "$LOG_FILE" 2>&1 || STATUS=$?
echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) end $TASK_NAME (exit $STATUS) =====" >> "$LOG_FILE" 2>&1

# codex prints its self-assigned session id in the run header; now that the run
# is over, upgrade the failure email's resume footer from `--last` to the exact
# id. The log accumulates runs, so take the last match (this run's).
if [[ "$CLI" == codex ]]; then
  CODEX_SESSION="$(sed -n 's/^session id: //p' "$LOG_FILE" | tail -1)"
  [[ -n "$CODEX_SESSION" ]] && export BORG_RESUME_CMD="codex resume $CODEX_SESSION"
fi

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
    echo "  session: ${SESSION_ID:-${CODEX_SESSION:-unknown}}"
    echo "  log:     $LOG_FILE"
    echo
    echo "Last lines of the log:"
    echo "$LOG_TAIL"
  } | "$BORG_ROOT/.bin/notify-email.sh" "$AGENT_NAME" "$SUBJECT" \
    || echo "notify-email.sh failed to send failure alert for $TASK_NAME" >> "$LOG_FILE" 2>&1
fi

# Report tasks email their report on success (they are read-only sessions that
# cannot pipe to notify-email.sh themselves; see REPORT_FILE above).
if [[ $STATUS -eq 0 && -n "$REPORT_FILE" ]]; then
  "$BORG_ROOT/.bin/notify-email.sh" "$AGENT_NAME" "[Borg/$AGENT_NAME] $TASK_NAME — $(date +%Y-%m-%d)" < "$REPORT_FILE" \
    || echo "notify-email.sh failed to send report for $TASK_NAME" >> "$LOG_FILE" 2>&1
fi

# Re-exit with the task's own code so `launchctl list` reflects reality.
exit $STATUS
