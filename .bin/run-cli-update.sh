#!/bin/bash
# Model-less weekly maintenance runner for com.theborg.c4po-cli-update.
# It intentionally bypasses run-scheduled-task.sh: there is no prompt, model
# session, state gate, or useful interactive slash-command equivalent.
set -uo pipefail

# Distinct exit code meaning "this CLI is not installed here", so a missing
# harness is skipped rather than counted as an update failure. Chosen out of the
# way of any real `<cli> update` exit code.
readonly CLI_ABSENT=64

parse_doctor_output() {
  local input_file="$1" known_file="$2" new_file="$3"
  local finding reported_count=0 actual_count=0 saw_summary=0 saw_clean_result=0

  : > "$known_file"
  : > "$new_file"

  while read -r count _kind; do
    reported_count=$((reported_count + count))
    saw_summary=1
  done < <(sed -nE 's/^([0-9]+) (warning|error)s? found$/\1 \2/p' "$input_file")

  # Claude Code 2.1.226 stopped printing a numeric warning summary when doctor
  # is clean. It now emits this explicit success sentinel, even when a separate
  # feature advisory (for example Remote Control auth scope) follows it.
  grep -qxF 'No installation issues found.' "$input_file" && saw_clean_result=1

  while IFS= read -r finding; do
    actual_count=$((actual_count + 1))
    # Expected under launchd: its headless security context cannot interact with
    # the login keychain. Require all three cause-specific fragments so another
    # keychain failure is treated as new and this baseline can be retired safely.
    if [[ "$finding" == "- macOS Keychain is not writable ("* ]] &&
       [[ "$finding" == *"User interaction is not allowed."* ]] &&
       [[ "$finding" == *"add-generic-password: returned -25308)"* ]]; then
      echo "$finding" >> "$known_file"
    elif [[ "$finding" == "- Sign-in is missing the user:profile scope" ]]; then
      # A Remote Control capability advisory, not an installation-health issue.
      echo "$finding" >> "$known_file"
    else
      echo "$finding" >> "$new_file"
    fi
  done < <(grep -E '^- ' "$input_file" || true)

  # A changed doctor format must fail visibly instead of silently reporting clean.
  if [[ $saw_summary -eq 0 && $saw_clean_result -eq 0 && $actual_count -gt 0 ]]; then
    echo "doctor parser found findings without a warning/error summary" >&2
    return 1
  fi
  if [[ $saw_summary -eq 0 && $saw_clean_result -eq 0 && $actual_count -eq 0 ]]; then
    echo "doctor parser found neither a health summary nor a clean result" >&2
    return 1
  fi
  if [[ $saw_summary -eq 1 && $reported_count -ne $actual_count ]]; then
    echo "doctor parser count mismatch: report says $reported_count, parsed $actual_count" >&2
    return 1
  fi
}

line_count() {
  awk 'END { print NR + 0 }' "$1"
}

cleanup_temp_files() {
  [[ -z ${RUN_OUTPUT:-} ]] || rm -f -- "$RUN_OUTPUT"
  [[ -z ${DOCTOR_OUTPUT:-} ]] || rm -f -- "$DOCTOR_OUTPUT"
  [[ -z ${KNOWN_FINDINGS:-} ]] || rm -f -- "$KNOWN_FINDINGS"
  [[ -z ${NEW_FINDINGS:-} ]] || rm -f -- "$NEW_FINDINGS"
}

update_one() {
  local name="$1" command_name="$2" output_file="$3"
  local binary before after update_status
  {
    echo
    echo "--- $name ---"
  } >> "$output_file"

  binary="$(command -v "$command_name" 2>/dev/null)"
  if [[ -z "$binary" ]]; then
    # Not an error. The Borg is harness-agnostic: a fork may run Claude only,
    # Codex only, or both, and a CLI the user never installed is not a fault to
    # email about every Sunday. main() detects what's configured and only calls
    # this for those, so reaching here means the binary vanished between the
    # detection and now — worth a log line, not a failed job.
    echo "$name binary not found on PATH after sourcing ~/.zshenv (PATH=$PATH)" >> "$output_file"
    return "$CLI_ABSENT"
  fi

  before="$("$binary" --version 2>&1)" || before="version check failed: $before"
  echo "before: $before" >> "$output_file"
  "$binary" update >> "$output_file" 2>&1 < /dev/null
  update_status=$?
  after="$("$binary" --version 2>&1)" || after="version check failed: $after"
  echo "after:  $after" >> "$output_file"
  echo "update exit: $update_status" >> "$output_file"
  return "$update_status"
}

run_doctor() {
  local command_name="$1" doctor_output="$2"
  local binary

  binary="$(command -v "$command_name" 2>/dev/null)"
  if [[ -z "$binary" ]]; then
    echo "Claude Code CLI binary not found for doctor (PATH=$PATH)" > "$doctor_output"
    return 127
  fi

  # Run at the Borg root: this workspace-wide maintenance job should inspect the
  # root settings.local.json, not c4po's narrower agent-local settings overlay.
  (cd "$BORG_ROOT" && "$binary" doctor </dev/null) > "$doctor_output" 2>&1
}

main() {
  local _caller_root="${BORG_ROOT:-}"
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

  # Precedence is caller > profile > autodetect. The profile is user-owned and
  # outside this repo, so it may still carry an unconditional
  # `export BORG_ROOT=...` that would clobber an explicitly-passed value.
  [[ -n "$_caller_root" ]] && BORG_ROOT="$_caller_root"

  RUN_OUTPUT="$(mktemp "${TMPDIR:-/tmp}/borg-cli-update.XXXXXX")" || exit 1
  DOCTOR_OUTPUT="$(mktemp "${TMPDIR:-/tmp}/borg-cli-doctor.XXXXXX")" || exit 1
  KNOWN_FINDINGS="$(mktemp "${TMPDIR:-/tmp}/borg-cli-doctor-known.XXXXXX")" || exit 1
  NEW_FINDINGS="$(mktemp "${TMPDIR:-/tmp}/borg-cli-doctor-new.XXXXXX")" || exit 1
  trap cleanup_temp_files EXIT

  local started_at finished_at status=0 doctor_status=0 parser_status=0
  local known_count=0 new_count=0 subject doctor_summary
  started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  echo "===== $started_at start $TASK_NAME =====" > "$RUN_OUTPUT"

  # Detect which CLIs this machine actually has before updating anything. The
  # Borg supports Claude-only, Codex-only, and both; updating a CLI the user
  # never installed used to return 127 and fail the whole job every week, which
  # trains people to ignore the one email that reports real breakage.
  local claude_present=0 codex_present=0 updated=0
  if command -v "${CLAUDE_BIN:-claude}" >/dev/null 2>&1; then claude_present=1; fi
  if command -v "${CODEX_BIN:-codex}" >/dev/null 2>&1; then codex_present=1; fi

  {
    echo
    echo "--- configured CLIs ---"
    echo "claude: $([[ $claude_present -eq 1 ]] && echo present || echo "not installed — skipping")"
    echo "codex:  $([[ $codex_present -eq 1 ]] && echo present || echo "not installed — skipping")"
  } >> "$RUN_OUTPUT"

  # No harness at all is a real problem: every model-driven scheduled job would
  # exit 127. Report it as a failure rather than a quiet clean run.
  if [[ $claude_present -eq 0 && $codex_present -eq 0 ]]; then
    echo "no supported CLI found on PATH (looked for claude and codex)" >> "$RUN_OUTPUT"
    status=1
  fi

  if [[ $codex_present -eq 1 ]]; then
    update_one "Codex CLI" "${CODEX_BIN:-codex}" "$RUN_OUTPUT" || status=1
    updated=$((updated + 1))
  fi
  # Claude's native install already self-updates on use; this explicit update is
  # belt-and-braces. Run it even if Codex failed so one failure cannot starve the other.
  if [[ $claude_present -eq 1 ]]; then
    update_one "Claude Code CLI" "${CLAUDE_BIN:-claude}" "$RUN_OUTPUT" || status=1
    updated=$((updated + 1))
  fi

  # `doctor` is a Claude Code subcommand with no Codex equivalent, so a
  # Codex-only machine skips it and says so instead of reporting a parse failure.
  if [[ $claude_present -eq 0 ]]; then
    doctor_summary="Claude doctor: skipped — claude is not installed on this machine."
    echo "$doctor_summary" >> "$RUN_OUTPUT"
  else
    run_doctor "${CLAUDE_BIN:-claude}" "$DOCTOR_OUTPUT" || doctor_status=$?
    if [[ $doctor_status -eq 0 ]]; then
      parse_doctor_output "$DOCTOR_OUTPUT" "$KNOWN_FINDINGS" "$NEW_FINDINGS" || parser_status=$?
    fi

    {
      echo
      echo "--- Claude Code doctor (raw output) ---"
      cat "$DOCTOR_OUTPUT"
      echo "doctor exit: $doctor_status"
      echo "doctor parser exit: $parser_status"
    } >> "$RUN_OUTPUT"

    if [[ $doctor_status -ne 0 || $parser_status -ne 0 ]]; then
      status=1
      doctor_summary="Claude doctor: FAILED to run or parse (exit $doctor_status; parser $parser_status)."
    else
      known_count="$(line_count "$KNOWN_FINDINGS")"
      new_count="$(line_count "$NEW_FINDINGS")"
      if [[ $new_count -eq 0 ]]; then
        doctor_summary="Claude doctor: no new findings; $known_count known headless finding(s) suppressed (full report in log)."
      else
        doctor_summary="Claude doctor: $new_count NEW/CHANGED finding(s); $known_count known headless finding(s)."
      fi
    fi
  fi

  finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "===== $finished_at updates and doctor complete (exit $status) =====" >> "$RUN_OUTPUT"
  cat "$RUN_OUTPUT" >> "$LOG_FILE"
  cat "$RUN_OUTPUT"

  if [[ $status -eq 0 ]]; then
    subject="[Borg/c4po] weekly CLI maintenance complete — $(date +%Y-%m-%d)"
  else
    subject="[Borg/c4po] weekly CLI maintenance FAILED — $(date +%Y-%m-%d)"
  fi

  if ! {
    echo "$doctor_summary"
    if [[ $new_count -gt 0 ]]; then
      echo
      cat "$NEW_FINDINGS"
    fi
    echo
    echo "Weekly CLI maintenance finished with exit $status."
    echo "Log (includes full doctor report): $LOG_FILE"
    echo
    # Preserve the updater's existing emailed detail without duplicating the raw
    # doctor report; doctor findings above are the intentionally concise summary.
    sed '/^--- Claude Code doctor (raw output) ---$/,$d' "$RUN_OUTPUT"
  } | "$BORG_ROOT/.bin/notify-email.sh" c4po "$subject"; then
    local msg="notify-email.sh FAILED for $TASK_NAME"
    echo "$msg" | tee -a "$LOG_FILE" >&2
    logger -t borg-notify "$msg" 2>/dev/null || true
    mkdir -p "$BORG_ROOT/tmp" 2>/dev/null || true
    printf '%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$TASK_NAME" "maintenance report" \
      >> "$BORG_ROOT/tmp/notify-failures.log" 2>/dev/null || true
    osascript -e "display notification \"$msg\" with title \"Borg: notification channel is DOWN\"" \
      >/dev/null 2>&1 || true
    [[ $status -ne 0 ]] || status=70
  fi

  echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) end $TASK_NAME (exit $status) =====" >> "$LOG_FILE"
  exit "$status"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
