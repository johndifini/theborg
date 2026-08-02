#!/bin/bash
# Model-less weekly maintenance runner for com.theborg.c4po-cli-update.
# It intentionally bypasses run-scheduled-task.sh: there is no prompt, model
# session, state gate, or useful interactive slash-command equivalent.
set -uo pipefail

BORG_ROOT="${BORG_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
TASK_NAME="c4po-cli-update"
LOG_DIR="$BORG_ROOT/c4po/.claude/scheduled/logs"
LOG_FILE="$LOG_DIR/$TASK_NAME.log"
mkdir -p "$LOG_DIR"

# launchd supplies a minimal PATH. Match the model runner's resolution behavior.
if [[ -f "$HOME/.zshenv" ]]; then
  # shellcheck disable=SC1091
  set +u
  source "$HOME/.zshenv" 2>/dev/null || true
  set -u
fi

RUN_OUTPUT="$(mktemp "${TMPDIR:-/tmp}/borg-cli-update.XXXXXX")" || exit 1
trap 'rm -f "$RUN_OUTPUT"' EXIT
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
STATUS=0

update_one() {
  local name="$1" command_name="$2" binary before after update_status
  {
    echo
    echo "--- $name ---"
  } >> "$RUN_OUTPUT"

  binary="$(command -v "$command_name" 2>/dev/null)"
  if [[ -z "$binary" ]]; then
    echo "$name binary not found on PATH after sourcing ~/.zshenv (PATH=$PATH)" >> "$RUN_OUTPUT"
    return 127
  fi

  before="$("$binary" --version 2>&1)" || before="version check failed: $before"
  echo "before: $before" >> "$RUN_OUTPUT"
  "$binary" update >> "$RUN_OUTPUT" 2>&1 < /dev/null
  update_status=$?
  after="$("$binary" --version 2>&1)" || after="version check failed: $after"
  echo "after:  $after" >> "$RUN_OUTPUT"
  echo "update exit: $update_status" >> "$RUN_OUTPUT"
  return "$update_status"
}

echo "===== $STARTED_AT start $TASK_NAME =====" > "$RUN_OUTPUT"
update_one "Codex CLI" "${CODEX_BIN:-codex}" || STATUS=1
# Claude's native install already self-updates on use; this explicit update is
# belt-and-braces. Run it even if Codex failed so one failure cannot starve the other.
update_one "Claude Code CLI" "${CLAUDE_BIN:-claude}" || STATUS=1

FINISHED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "===== $FINISHED_AT updates complete (exit $STATUS) =====" >> "$RUN_OUTPUT"
cat "$RUN_OUTPUT" >> "$LOG_FILE"
cat "$RUN_OUTPUT"

if [[ $STATUS -eq 0 ]]; then
  SUBJECT="[Borg/c4po] weekly CLI update complete — $(date +%Y-%m-%d)"
else
  SUBJECT="[Borg/c4po] weekly CLI update FAILED — $(date +%Y-%m-%d)"
fi

if ! {
  echo "Weekly CLI update finished with exit $STATUS."
  echo "Log: $LOG_FILE"
  cat "$RUN_OUTPUT"
} | "$BORG_ROOT/.bin/notify-email.sh" c4po "$SUBJECT"; then
  MSG="notify-email.sh FAILED for $TASK_NAME"
  echo "$MSG" | tee -a "$LOG_FILE" >&2
  logger -t borg-notify "$MSG" 2>/dev/null || true
  mkdir -p "$BORG_ROOT/tmp" 2>/dev/null || true
  printf '%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$TASK_NAME" "update report" \
    >> "$BORG_ROOT/tmp/notify-failures.log" 2>/dev/null || true
  osascript -e "display notification \"$MSG\" with title \"Borg: notification channel is DOWN\"" \
    >/dev/null 2>&1 || true
  [[ $STATUS -ne 0 ]] || STATUS=70
fi

echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) end $TASK_NAME (exit $STATUS) =====" >> "$LOG_FILE"
exit "$STATUS"
