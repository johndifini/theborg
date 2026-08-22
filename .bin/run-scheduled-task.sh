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
# blocks the task; if the binary still can't be resolved we'll fail loudly
# below.
#
# The profile is user-owned and outside this repo, so it may still contain an
# unconditional `export BORG_ROOT=...`. Capture the caller's value first and
# re-assert it below rather than trusting the profile to be well-behaved.
_caller_root="${BORG_ROOT:-}"
if [[ -f "$HOME/.zshenv" ]]; then
  # shellcheck disable=SC1091
  set +u
  source "$HOME/.zshenv" 2>/dev/null || true
  set -u
fi

# BORG_ROOT: workspace root, auto-detected from this script's location
# (.bin/ sits at the workspace root). Override by exporting BORG_ROOT
# before invocation. Prompts reference paths as ${BORG_ROOT}/... and the
# runner substitutes the literal token below.
#
# Precedence is caller > profile > autodetect. An explicit BORG_ROOT is the
# documented escape hatch for a checkout that is not at ~/theborg, and it is
# how a test run redirects this script at a scratch tree — letting the profile
# win here once aimed a test back at the real workspace and sent real email.
[[ -n "$_caller_root" ]] && BORG_ROOT="$_caller_root"
unset _caller_root
BORG_ROOT="${BORG_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export BORG_ROOT

# Harness default. The Borg is harness-agnostic: a scheduled job may run on
# Claude Code or on Codex, and the choice is per-task rather than baked in here.
# Resolution order, last wins:
#   1. `claude` — the built-in default
#   2. $BORG_HARNESS — the workspace-wide default, exported from ~/.zshenv
#   3. HARNESS= in the task's .conf sidecar — the per-task override
# The .conf is sourced further down (it also carries MODEL/EFFORT/EXTRA_ARGS),
# so the binary check and every harness-specific decision below it are deferred
# until after that source. Validate the workspace default now, though: a typo in
# ~/.zshenv would otherwise silently fall through to per-task defaults on every
# job at once.
HARNESS="${BORG_HARNESS:-claude}"
case "$HARNESS" in
  claude|codex) ;;
  *) echo "invalid BORG_HARNESS: '$HARNESS' (expected 'claude' or 'codex')" >&2; exit 64 ;;
esac

cd "$AGENT_DIR"

# Render the prompt: substitute only ${BORG_ROOT}. Bash parameter
# expansion (no envsubst dependency) — leaves all other $-tokens alone,
# so literal `$50`, regex `$1`, etc. in prompts pass through untouched.
PROMPT_CONTENT=$(<"$PROMPT_FILE")
PROMPT_CONTENT=${PROMPT_CONTENT//\$\{BORG_ROOT\}/$BORG_ROOT}

# $PROMPT_CONTENT now holds the raw .prompt text. The scheduled-run preamble is
# wrapped around it further down, AFTER the .conf sidecar is sourced, because
# its closing sentence depends on REPORT. See "Scheduled-run preamble" below.

# Per-task effort (claude only; codex tasks take model and reasoning effort from
# ~/.codex/config.toml). Every claude job runs at "high" unless its .conf
# sidecar says otherwise.
EFFORT=high

# Per-task model (claude only; codex tasks use ~/.codex/config.toml).
# Set HERE via --model, deliberately NOT inherited from the user-level `model`
# field in ~/.claude/settings.json. That field is mutated by any interactive
# `/model` toggle, and a drift there onto a credits-gated model (Fable 5) is what
# hard-failed the security audit 2026-07-21 with "Fable 5 requires usage credits."
# Setting it in the runner decouples scheduled jobs from the interactive default.
# The `opus` alias resolves to the latest GA Opus, so a new Opus generation is
# picked up without an edit here — the family stays pinned, which is what keeps
# Fable off these jobs. The monthly assumptions audit (Assumption F in
# c4po/.claude/scheduled/c4po-assumptions-audit-monthly.prompt) still checks that
# the alias is intact and that Opus remains the right default family.
MODEL=opus

# Per-task extra CLI args, harness-neutral portion. The backlog burndown edits
# files across the whole workspace (root BACKLOG.md, sibling agents, the
# git-ignored repos/*); the session retro stages into the sibling
# cerebruh/ingest/ and pipes to .bin/notify-email.sh. Neither stays inside its
# own agent dir, so both get the workspace root as a writable root — both
# harnesses accept --add-dir, and codex additionally needs it to widen its
# workspace-write sandbox, which otherwise confines writes to the cwd. Other
# tasks stay confined to their agent dir. Repo-hosted tasks set their own
# EXTRA_ARGS via the .conf sidecar sourced below.
#
# Harness-SPECIFIC args are appended after the .conf source, once HARNESS is
# final — see the block below. Anything that only one CLI understands
# (--permission-mode, --sandbox, the codex .git and $CODEX_HOME writable roots)
# belongs there, not here.
EXTRA_ARGS=()
case "$TASK_NAME" in
  c4po-backlog-burndown|c4po-retro) EXTRA_ARGS+=(--add-dir "$BORG_ROOT") ;;
esac

# Per-task report file. Most tasks email their own results from inside the
# session (their .prompt pipes to notify-email.sh). A read-only task can't —
# it has no Bash — so the runner captures the model's stdout as a dated report
# and emails it on success (failure emailing below covers the rest). A task opts
# in by setting REPORT=1 in its .conf sidecar (sourced below).
REPORT_FILE=""

# Optional per-task config sidecar. Any task may have one — repo-hosted tasks
# (under repos/*) use it to keep runner settings in their own repo instead of
# hard-coding them here, and a Borg agent's task uses it to override a default.
# Drop a <task>.conf beside the <task>.prompt. Sourced last, so it overrides the
# defaults above. Recognized keys: HARNESS (claude|codex), MODEL, EFFORT,
# EXTRA_ARGS (a bash array), and REPORT=1 (capture stdout as a dated report and
# email it).
CONF_FILE="$AGENT_DIR/.claude/scheduled/$TASK_NAME.conf"
if [[ -f "$CONF_FILE" ]]; then
  REPORT=0
  # shellcheck disable=SC1090
  source "$CONF_FILE"
  [[ "${REPORT:-0}" == 1 ]] && REPORT_FILE="$AGENT_DIR/.claude/scheduled/reports/$(date +%Y-%m-%d).md"
fi

# Scheduled-run preamble. Every .prompt has a paired interactive slash command
# (lint rule: Scheduled tasks) that delegates back to this same file but applies
# overrides for session use — skip the once-per-period state gate, don't write
# state, report to the session instead of emailing. Both harnesses surface those
# commands to a headless run as invocable skills (claude: `.claude/commands/*`;
# codex: the `$name` skill bridge), and the model will match one to the task it
# was just handed and follow its overrides instead of these instructions.
# That is a SILENT failure — the run exits 0 having sent no email and written no
# state, so the runner's failure-email path never fires and the next scheduled
# firing repeats the work. Observed on a multi-day private task on 2026-07-22
# and 2026-07-28. Prepended here rather than in each .prompt so new tasks are
# covered automatically and the guard can't drift out of sync.
#
# Built HERE, below the sidecar, because the closing duties sentence is FALSE
# for a REPORT=1 task. Those run read-only (typically
# --allowedTools "WebSearch,WebFetch", no Bash) so a fetched page cannot inject
# actions into the repo — which means no state gate, no reachable
# notify-email.sh, and no state write; the runner emails their stdout instead.
# Telling them otherwise made all five waiq-tts-watch runs in the week of
# 2026-08-19 burn turns sweeping the filesystem for notify-email.sh before
# reasoning past their own instructions; one spawned a subagent to look for it.
# Keep this construction below the sidecar: moving it back above silently
# reintroduces the mismatch for every read-only task at once.
# See .claude/rules/readonly-scheduled-tasks.md.
if [[ -n "$REPORT_FILE" ]]; then
  PREAMBLE_DUTIES="Perform every phase below yourself. This run is READ-ONLY: it \
has no Bash, no state gate, and no way to email itself. The runner captures your \
stdout and emails it on success, so do not look for notify-email.sh, do not write \
state, and do not treat their absence as a reason to stop or to search the \
filesystem for them."
else
  PREAMBLE_DUTIES="Perform every phase below yourself, including the state gate, \
the notify-email.sh delivery, and the state write."
fi

PROMPT_CONTENT="You are a scheduled (headless) run of the task named \
'$TASK_NAME'. Execute the instructions below directly and in full.

Do NOT invoke any skill or slash command that wraps this same task — in
particular the interactive companion whose name matches '$TASK_NAME'. That
companion exists only for interactive use and its overrides (skip the state
gate, skip writing state, report to the session instead of emailing) are WRONG
here and would silently void this run. $PREAMBLE_DUTIES

--- BEGIN TASK INSTRUCTIONS ---
$PROMPT_CONTENT"

# HARNESS is now final (default -> $BORG_HARNESS -> .conf). Validate it again:
# the first check caught a bad workspace default, this one catches a bad .conf.
case "$HARNESS" in
  claude|codex) ;;
  *) echo "invalid HARNESS in $CONF_FILE: '$HARNESS' (expected 'claude' or 'codex')" >&2; exit 64 ;;
esac

# Resolve the binary for the chosen harness and fail loudly if it isn't there.
# A missing CLI is a hard error, not a fallback to the other one: silently
# running a job on a harness it wasn't configured for would change its model,
# its sandbox, and its budget without anyone being told.
case "$HARNESS" in
  claude) HARNESS_BIN="${CLAUDE_BIN:-claude}" ;;
  codex)  HARNESS_BIN="${CODEX_BIN:-codex}" ;;
esac
if ! command -v "$HARNESS_BIN" >/dev/null 2>&1; then
  echo "$HARNESS binary '$HARNESS_BIN' not found on PATH after sourcing ~/.zshenv (PATH=$PATH)" >&2
  exit 127
fi

# Harness-specific args, appended after the .conf so a sidecar can pick the
# harness and still get the right flags for it.
if [[ "$HARNESS" == codex ]]; then
  # Codex's workspace-write sandbox carves `.git/` out of every writable root,
  # so --add-dir "$BORG_ROOT" leaves the whole tree writable EXCEPT its index
  # and every commit dies on `Unable to create '.../.git/index.lock': Operation
  # not permitted`. The carveout is per-root (root + "/.git"), so a `.git`
  # passed as a root in its own right is not carved out. Learned when the
  # 2026-07-31 burndown implemented 0 of its 39 planned items. Claude needs none
  # of this: --add-dir grants tool access rather than defining a Seatbelt
  # boundary, so a root already covers committing inside it.
  case "$TASK_NAME" in
    c4po-backlog-burndown|c4po-retro)
      EXTRA_ARGS+=(--add-dir "$BORG_ROOT/.git")
      # `if`, not `[[ ... ]] &&`: with `set -e`, a trailing false `&&` list makes
      # the loop (and the enclosing case) exit non-zero and kills the run. That
      # fires whenever the last glob entry has no .git — including the no-match
      # case, where the unexpanded pattern itself is the only "entry".
      for git_dir in "$BORG_ROOT"/repos/*/.git; do
        if [[ -d "$git_dir" ]]; then
          EXTRA_ARGS+=(--add-dir "$git_dir")
        fi
      done
      ;;
  esac
  # $CODEX_HOME, for tasks that spawn a nested `codex exec`. The child starts an
  # in-process app-server that writes there; without it every child exits with
  # `failed to initialize in-process app-server client: Operation not permitted`
  # before it ever reads its prompt. Verified 2026-08-01 that narrowing this to
  # ~/.codex/app-server-control/ is NOT sufficient. Granted only to the
  # burndown, the one task that spawns children.
  case "$TASK_NAME" in
    c4po-backlog-burndown) EXTRA_ARGS+=(--add-dir "${CODEX_HOME:-$HOME/.codex}") ;;
  esac
else
  # The burndown runs in bypassPermissions. It must write and commit across
  # several repositories unattended, and a mid-BURN permission denial is
  # precisely the silent failure the task's phase design exists to prevent — the
  # run would exit 0 having implemented nothing. This matches the effective
  # posture its Codex children have (they run
  # --dangerously-bypass-approvals-and-sandbox), but note what is NOT carried
  # over: under Codex the whole process tree sits inside an OS-enforced
  # workspace-write Seatbelt boundary, and nothing replaces that on the Claude
  # path. Claude Code has its own Seatbelt-backed Bash sandbox, but adopting it
  # needs the outbound SMTP path in .bin/notify-email.sh verified against the
  # sandbox's HTTP-proxy network layer first — email is the only notification
  # channel, so a silent break there is unacceptable. Tracked in BACKLOG.md.
  #
  # The retro deliberately does NOT get bypassPermissions. It runs under the
  # inherited `auto` mode like every other Claude job, because it is the one task
  # that touches cerebruh/ and the Edit deny rules in
  # c4po/.claude/settings.local.json are what mechanically enforce "wiki content
  # is read-only" — bypassPermissions would skip them and leave only the
  # prompt's instruction.
  case "$TASK_NAME" in
    c4po-backlog-burndown) EXTRA_ARGS+=(--permission-mode bypassPermissions) ;;
  esac
fi

# Resume handle for notification footers (notify-email.sh).
# - claude: pin a session id up front (`claude --resume $BORG_SESSION_ID`).
#   Lowercased — claude stores/looks up session ids in lowercase.
# - codex: no way to pre-pin an id (codex assigns one at launch), so export a
#   generic fallback. Inside the run, notify-email.sh prefers Codex's exact
#   $CODEX_THREAD_ID; after the run we also upgrade failure emails to the exact
#   id parsed from the log. `codex resume --last` is only the last-resort path.
SESSION_ID=""
if [[ "$HARNESS" == codex ]]; then
  export BORG_RESUME_CMD="codex resume --last"
else
  SESSION_ID="$(uuidgen | tr '[:upper:]' '[:lower:]')"
  export BORG_SESSION_ID="$SESSION_ID"
fi

# Child-session spawn command, exported for the one task that fans out (the
# backlog burndown dispatches a fresh headless child per item). The prompt uses
# $BORG_CHILD_CMD verbatim instead of naming a CLI, which is what keeps it
# harness-neutral — the flags live here, in one place, next to the harness that
# needs them. A prompt that spawns children should append only its prompt string.
#
# The codex child deliberately bypasses approvals and sandboxing: it cannot
# initialize a second macOS Seatbelt sandbox inside the parent's, and it remains
# confined by the parent process tree's workspace-write boundary regardless.
export BORG_HARNESS="$HARNESS"
if [[ "$HARNESS" == codex ]]; then
  export BORG_CHILD_CMD="$HARNESS_BIN exec --dangerously-bypass-approvals-and-sandbox"
else
  export BORG_CHILD_CMD="$HARNESS_BIN -p --model $MODEL --effort $EFFORT --permission-mode bypassPermissions --strict-mcp-config"
fi

# claude flags:
# --strict-mcp-config: a scheduled `claude -p` run must not boot any
# session-configured MCP server — outbound goes via .bin/notify-email.sh only.
# (No codex equivalent needed: codex loads MCP servers only from
# ~/.codex/config.toml.)
# --session-id pins the run to $SESSION_ID so the notification can hand the user a
# `claude --resume` command pointing at this exact session.
#
# codex flags:
# --sandbox workspace-write: codex defaults headless runs to a read-only
# sandbox; the task must write (and --add-dir extends the writable roots).
# -c sandbox_workspace_write.network_access=true: workspace-write blocks
# network by default, which would break notify-email.sh's SMTP curl and any
# child session the task spawns (the child's API calls run under this sandbox).
# Model and reasoning effort are deliberately NOT set — the defaults come from
# ~/.codex/config.toml.
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
  echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) start $TASK_NAME (cwd=$AGENT_DIR, cli=$HARNESS, session=${SESSION_ID:-codex-assigned}) ====="
  if [[ "$HARNESS" == codex ]]; then
    # The Codex desktop app injects these only for its current interactive
    # thread. A launchd task must never inherit them: otherwise `codex exec`
    # reconnects to that thread through its in-process app-server client rather
    # than starting the fresh, isolated headless session the task requires.
    if [[ -n "$REPORT_FILE" ]]; then
      mkdir -p "$(dirname "$REPORT_FILE")"
      env -u CODEX_REMOTE_PAYLOAD -u CODEX_THREAD_ID \
        "$HARNESS_BIN" exec --sandbox workspace-write -c sandbox_workspace_write.network_access=true ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} "$PROMPT_CONTENT" < /dev/null > "$REPORT_FILE"
    else
      env -u CODEX_REMOTE_PAYLOAD -u CODEX_THREAD_ID \
        "$HARNESS_BIN" exec --sandbox workspace-write -c sandbox_workspace_write.network_access=true ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} "$PROMPT_CONTENT" < /dev/null
    fi
  elif [[ -n "$REPORT_FILE" ]]; then
    # Report task: model stdout IS the report; stderr/markers stay in the log.
    mkdir -p "$(dirname "$REPORT_FILE")"
    "$HARNESS_BIN" -p "$PROMPT_CONTENT" --session-id "$SESSION_ID" --strict-mcp-config --model "$MODEL" --effort "$EFFORT" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} < /dev/null > "$REPORT_FILE"
  else
    "$HARNESS_BIN" -p "$PROMPT_CONTENT" --session-id "$SESSION_ID" --strict-mcp-config --model "$MODEL" --effort "$EFFORT" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} < /dev/null
  fi
} >> "$LOG_FILE" 2>&1 || STATUS=$?
echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) end $TASK_NAME (exit $STATUS) =====" >> "$LOG_FILE" 2>&1

# codex prints its self-assigned session id in the run header; now that the run
# is over, upgrade the failure email's resume footer from `--last` to the exact
# id. The log accumulates runs, so take the last match (this run's).
CODEX_SESSION=""
if [[ "$HARNESS" == codex ]]; then
  CODEX_SESSION="$(sed -n 's/^session id: //p' "$LOG_FILE" | tail -1)"
  [[ -n "$CODEX_SESSION" ]] && export BORG_RESUME_CMD="codex resume $CODEX_SESSION"
fi

# notify-email.sh failing is a silent-outage class of bug: email is the ONLY
# outbound channel, so a failure here means the user learns nothing — including
# that a task failed. (This happened 2026-08-01: the workspace .env symlink was
# removed by a Drive-side delete and every notification would have vanished into
# a log line.) Escalate to every channel that does NOT depend on email: the task
# log, the macOS unified log, a desktop notification, and a sentinel file a later
# run or the daily security audit can surface. All guarded — a broken escalation
# must never take down the run itself.
notify_failed() {
  local what="$1"
  local msg="notify-email.sh FAILED to send $what for $TASK_NAME"
  echo "$msg" >> "$LOG_FILE" 2>&1 || true
  logger -t borg-notify "$msg" 2>/dev/null || true
  mkdir -p "$BORG_ROOT/tmp" 2>/dev/null || true
  printf '%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$TASK_NAME" "$what" \
    >> "$BORG_ROOT/tmp/notify-failures.log" 2>/dev/null || true
  osascript -e "display notification \"$msg\" with title \"Borg: notification channel is DOWN\"" \
    >/dev/null 2>&1 || true
}

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
    || notify_failed "failure alert"
fi

# Report tasks email their report on success (they are read-only sessions that
# cannot pipe to notify-email.sh themselves; see REPORT_FILE above).
if [[ $STATUS -eq 0 && -n "$REPORT_FILE" ]]; then
  "$BORG_ROOT/.bin/notify-email.sh" "$AGENT_NAME" "[Borg/$AGENT_NAME] $TASK_NAME — $(date +%Y-%m-%d)" < "$REPORT_FILE" \
    || notify_failed "report"
fi

# Re-exit with the task's own code so `launchctl list` reflects reality.
exit $STATUS
