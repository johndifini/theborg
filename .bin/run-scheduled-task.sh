#!/bin/bash
# Wrapper invoked by launchd to run a scheduled task in an agent's working dir.
# Usage: run-scheduled-task.sh <agent-dir> <prompt-file>
set -euo pipefail

# The whole body lives in main() so bash parses it before executing any of it.
# Bash reads a top-level script incrementally, keeping a byte offset and seeking
# back to it after each external command -- so a script rewritten while it runs
# resumes at an offset that now points into shifted text. This runner is the one
# most exposed to that: it hands a model a prompt and waits, and the weekly
# backlog burndown implements workspace tooling items, which land in .bin/. On
# 2026-09-09 a burndown child committed to this very file mid-run (1e619be).
# Reproduced deterministically before this fix: the victim re-executed commands
# and resumed one byte into a token ("leep: command not found"). Note the call
# below MUST keep `exit` on the same line -- a bare `main "$@"` still lets bash
# seek past it and misparse, which reproduced at 5/5.
#
# The body is deliberately NOT re-indented, so this stays a three-line diff that
# can be reviewed against the previous version rather than a 500-line reflow.
main() {

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

# Keep last30days out of macOS's TCC-protected folders. Its save directory
# defaults to ~/Documents/Last30Days, and ~/.zshenv (sourced above) points it at
# ~/Downloads. Headless claude holds no Files and Folders grant for either. So the
# first touch does not fail; it raises a consent dialog on the Studio's screen
# and blocks until someone answers. On 2026-09-29 the mrs-beast image job did
# exactly that and sat for a day. Override unconditionally, because the process
# env beats ~/.config/last30days/.env in the engine. The directory sits per agent
# and under .claude/scheduled/, which the memory inventory classifies as
# generated report input; gitignore each one an agent adds.
export LAST30DAYS_MEMORY_DIR="$AGENT_DIR/.claude/scheduled/last30days-raw"

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

# Per-task wall-clock limit. The harness call has no limit of its own: on
# 2026-09-29 mrs-beast-ai-week-image-prompt stalled right after a Bash call
# returned and hung for 26 hours until something outside the runner SIGKILLed
# it. While it hung, launchd skipped Wednesday's firing as "still running", so
# the hang silently ate a retry too. On expiry the watchdog below kills the
# whole process tree, logs it, and the failure email reports TIMED OUT.
#
# Format: <n>s, <n>m or <n>h; a bare number means MINUTES; 0 disables. Every
# job but one finished well inside 20 minutes as of 2026-09-30. The exception
# is the burndown, which fans out a child per item: a codex burndown ran 209
# minutes on 2026-08-15 and exited 0, so it gets its own longer default here.
TIMEOUT=60m
case "$TASK_NAME" in
  c4po-backlog-burndown) TIMEOUT=6h ;;
esac
# Between SIGTERM and SIGKILL, so a harness can flush its transcript on exit.
TIMEOUT_GRACE_SECONDS=30

# Optional per-task config sidecar. Any task may have one — repo-hosted tasks
# (under repos/*) use it to keep runner settings in their own repo instead of
# hard-coding them here, and a Borg agent's task uses it to override a default.
# Drop a <task>.conf beside the <task>.prompt. Sourced last, so it overrides the
# defaults above. Recognized keys: HARNESS (claude|codex), MODEL, EFFORT,
# EXTRA_ARGS (a bash array), REPORT=1 (capture stdout as a dated report and
# email it), and TIMEOUT (the wall-clock limit above, e.g. TIMEOUT=2h).
CONF_FILE="$AGENT_DIR/.claude/scheduled/$TASK_NAME.conf"
if [[ -f "$CONF_FILE" ]]; then
  REPORT=0
  # shellcheck disable=SC1090
  source "$CONF_FILE"
  [[ "${REPORT:-0}" == 1 ]] && REPORT_FILE="$AGENT_DIR/.claude/scheduled/reports/$(date +%Y-%m-%d).md"
fi

# Resolve TIMEOUT to seconds. A malformed value falls back to 60m with a warning
# in the log rather than aborting: refusing to run would turn a typo into a
# silent missed job, and running unbounded would reopen the hang this guards.
TIMEOUT_WARNING=""
if [[ "$TIMEOUT" =~ ^([0-9]+)([smh]?)$ ]]; then
  case "${BASH_REMATCH[2]}" in
    s)  TIMEOUT_SECONDS=$(( 10#${BASH_REMATCH[1]} )) ;;
    h)  TIMEOUT_SECONDS=$(( 10#${BASH_REMATCH[1]} * 3600 )) ;;
    *)  TIMEOUT_SECONDS=$(( 10#${BASH_REMATCH[1]} * 60 )) ;;
  esac
else
  TIMEOUT_WARNING="invalid TIMEOUT '$TIMEOUT' in $CONF_FILE (expected e.g. 45m, 2h, 90s, or 0); using 60m"
  TIMEOUT=60m
  TIMEOUT_SECONDS=3600
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
  # The Claude burndown gets a dedicated sandbox policy rather than the
  # user-wide settings used by every other job. The tracked JSON contains a
  # literal ${BORG_ROOT}; render it into an inline --settings value here so a
  # checkout override remains portable. Validate before launch because print
  # mode silently ignores a settings file that fails validation — an ignored
  # file would turn this security boundary into a comment.
  #
  # The sandbox's allowWrite root covers the workspace and every independent
  # repo below it; its denyWrite entries keep cerebruh wiki content read-only.
  # failIfUnavailable and allowUnsandboxedCommands=false make the boundary a
  # hard gate. acceptEdits keeps file-tool writes unattended while preserving
  # explicit deny rules, and sandboxed Bash auto-runs without per-command
  # prompts. A real 2026-08-21 probe proved notify-email.sh can send through the
  # sandbox's allowlisted Gmail SMTP path; a second probe committed in a scratch
  # repo and confirmed that a sibling write outside $BORG_ROOT is blocked.
  #
  # The retro keeps the inherited `auto` mode like every other Claude job. It is
  # the one task that touches cerebruh/, so c4po's Edit deny rules remain its
  # mechanical write guard; the burndown now has those rules plus OS enforcement.
  case "$TASK_NAME" in
    c4po-backlog-burndown)
      BURNDOWN_SETTINGS_FILE="$BORG_ROOT/c4po/.claude/scheduled/c4po-backlog-burndown.settings.json"
      [[ -f "$BURNDOWN_SETTINGS_FILE" ]] || {
        echo "burndown sandbox settings not found: $BURNDOWN_SETTINGS_FILE" >&2
        exit 66
      }
      BURNDOWN_SETTINGS=$(<"$BURNDOWN_SETTINGS_FILE")
      BURNDOWN_SETTINGS=${BURNDOWN_SETTINGS//\$\{BORG_ROOT\}/$BORG_ROOT}
      python3 -c 'import json, sys; json.loads(sys.argv[1])' "$BURNDOWN_SETTINGS" || {
        echo "invalid burndown sandbox settings: $BURNDOWN_SETTINGS_FILE" >&2
        exit 65
      }
      EXTRA_ARGS+=(--settings "$BURNDOWN_SETTINGS" --permission-mode acceptEdits)
      ;;
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
# A child deliberately bypasses its own CLI permission layer. It is spawned by
# the parent's sandboxed Bash, so it and every subprocess it creates inherit the
# parent's OS-enforced boundary; initializing a second nested sandbox is neither
# needed nor relied upon. A real nested-Claude probe succeeded through the
# allowlisted Anthropic API path. Claude children disable session persistence so
# they do not need write access to ~/.claude outside the boundary.
export BORG_HARNESS="$HARNESS"
if [[ "$HARNESS" == codex ]]; then
  export BORG_CHILD_CMD="$HARNESS_BIN exec --dangerously-bypass-approvals-and-sandbox"
else
  export BORG_CHILD_CMD="$HARNESS_BIN -p --model $MODEL --effort $EFFORT --permission-mode bypassPermissions --strict-mcp-config --no-session-persistence"
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

# Process-tree helpers for the timeout watchdog. macOS ships no GNU `timeout`,
# and killing only the harness pid is not enough: its tool subprocesses (a Bash
# call, an MCP server, a nested child session) are reparented to launchd and
# keep running. So walk the tree by parent pid and signal every member at once.
# The walk is taken BEFORE any signal is sent, because a killed parent orphans
# its children and they can no longer be found through it.
descendant_pids() {
  local child
  for child in $(pgrep -P "$1" 2>/dev/null); do
    descendant_pids "$child"
    echo "$child"
  done
}
signal_tree() {
  # $1 = signal, $2 = root pid, remaining args = extra pids to include.
  local sig="$1" root="$2"
  shift 2
  # shellcheck disable=SC2046
  kill -"$sig" $(descendant_pids "$root") "$root" "$@" 2>/dev/null || true
}

# Run the task, capturing its exit code instead of letting `set -e` abort here:
# on failure we still need to notify and to preserve the code for launchd. The
# `end` marker moves outside the block so it always records, pass or fail
# (previously a failed run left no end line in the log).
#
# The block runs in the background so a watchdog can bound it (see TIMEOUT
# above); `wait` then collects its exit code exactly as `|| STATUS=$?` did.
STATUS=0
TIMED_OUT=0
START_STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
START_SECONDS=$SECONDS
{
  echo "===== $START_STAMP start $TASK_NAME (cwd=$AGENT_DIR, cli=$HARNESS, session=${SESSION_ID:-codex-assigned}, timeout=$TIMEOUT) ====="
  if [[ -n "$TIMEOUT_WARNING" ]]; then
    echo "WARNING: $TIMEOUT_WARNING"
  fi
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
} >> "$LOG_FILE" 2>&1 &
TASK_PID=$!

# Watchdog: sleep out the limit, then TERM the task's whole tree, give it
# $TIMEOUT_GRACE_SECONDS, and KILL whatever is left — including members of the
# first snapshot that were orphaned out of the tree by the TERM. The marker file
# is how the main shell learns the watchdog fired; an exit code alone cannot
# tell a timeout from a harness that died of its own SIGTERM.
WATCHDOG_PID=""
TIMEOUT_MARK=""
if (( TIMEOUT_SECONDS > 0 )); then
  TIMEOUT_MARK="$(mktemp "${TMPDIR:-/tmp}/borg-timeout.XXXXXX")"
  (
    sleep "$TIMEOUT_SECONDS"
    echo fired > "$TIMEOUT_MARK"
    echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) TIMEOUT $TASK_NAME: wall-clock limit $TIMEOUT reached; sending SIGTERM to the process tree =====" >> "$LOG_FILE" 2>&1
    # shellcheck disable=SC2207
    first_wave=($(descendant_pids "$TASK_PID"))
    signal_tree TERM "$TASK_PID"
    sleep "$TIMEOUT_GRACE_SECONDS"
    signal_tree KILL "$TASK_PID" ${first_wave[@]+"${first_wave[@]}"}
  ) &
  WATCHDOG_PID=$!
fi

# 2>/dev/null: when the watchdog kills the block, bash reports the job with
# its full source text ("Terminated: 15 { echo ... }") on stderr.
wait "$TASK_PID" 2>/dev/null || STATUS=$?
if [[ -n "$WATCHDOG_PID" ]]; then
  if [[ -s "$TIMEOUT_MARK" ]]; then
    # Fired: let it finish the KILL pass for anything that ignored the TERM.
    wait "$WATCHDOG_PID" 2>/dev/null || true
    TIMED_OUT=1
    STATUS=124  # GNU timeout's convention, so `launchctl list` reads the same
  else
    # Task finished first: stop the watchdog and its pending `sleep`.
    signal_tree TERM "$WATCHDOG_PID"
    wait "$WATCHDOG_PID" 2>/dev/null || true
  fi
  rm -f "$TIMEOUT_MARK"
fi
END_STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RUN_SECONDS=$(( SECONDS - START_SECONDS ))
if (( TIMED_OUT )); then
  echo "===== $END_STAMP end $TASK_NAME (exit $STATUS, TIMED OUT: killed after exceeding the $TIMEOUT limit; ran ${RUN_SECONDS}s) =====" >> "$LOG_FILE" 2>&1
else
  echo "===== $END_STAMP end $TASK_NAME (exit $STATUS) =====" >> "$LOG_FILE" 2>&1
fi

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
# self-heal. Notify on every failure; the subject distinguishes a starved run
# (nothing to fix, wait for the budget to reset) from a hard failure, without
# suppressing either.
if [[ $STATUS -ne 0 ]]; then
  LOG_TAIL="$(tail -n 25 "$LOG_FILE" 2>/dev/null || true)"

  # A REPORT=1 task's stdout is redirected to $REPORT_FILE — and stdout is
  # exactly where the harness prints its session-limit line — so for those tasks
  # the log holds nothing but the start/end markers and a scan of the log alone
  # cannot tell starvation from a hard failure. Scan both streams.
  #
  # That was the actual gap, verified on disk: on 2026-08-26 and 2026-09-02 the
  # REPORT=1 task waiq-tts-watch left reports/<date>.md containing exactly
  # "You've hit your session limit · resets 11:10am (America/Denver)" while its
  # log for those runs has no line at all between the markers — so it was
  # reported as an ordinary FAILED with an empty-looking excerpt. The two
  # non-REPORT tasks starved on the same days (c4po-security-audit,
  # c4po-lint-audit-monthly) kept the marker in their logs and classified fine.
  REPORT_TAIL=""
  if [[ -n "$REPORT_FILE" && -f "$REPORT_FILE" ]]; then
    REPORT_TAIL="$(tail -n 25 "$REPORT_FILE" 2>/dev/null || true)"
  fi

  # Which signal is reliable: NEITHER alone, both together. `claude -p` prints
  # the marker on stdout AND exits 1 (confirmed on the three tasks above), but a
  # non-zero exit is what every ordinary failure returns, and the marker text can
  # legitimately appear inside a task's own output — the security audit's own
  # report discusses usage limits in prose. So the test is: non-zero exit (this
  # branch) AND the marker in the harness's output.
  #
  # That still misreads one case: a task that fails hard WHILE its output
  # discusses a usage limit is labelled STARVED. Deliberate — the email goes out
  # either way carrying the exit code, the log tail and the matched line, so an
  # over-broad match costs a misleading subject on a mail the user still reads,
  # while an over-narrow one costs the silence this whole branch exists to end.
  # The codex phrasing is UNVERIFIED — nothing on disk has ever caught
  # `codex exec` at its limit — so this matches on text: a codex message
  # carrying any of these phrases is classified as starved, and one worded
  # differently degrades to the ordinary FAILED subject rather than being
  # mislabelled.
  #
  # A timeout is never starvation — a starved run dies at its first API call,
  # not an hour in — so it skips the scan: a hung task's log tail can mention a
  # usage limit in passing and must not be relabelled STARVED.
  LIMIT_LINE=""
  if (( ! TIMED_OUT )); then
    LIMIT_LINE="$(grep -ihE 'hit your (session|usage|weekly) limit|reached your (session|usage|weekly) limit|(session|usage|weekly) limit (reached|exceeded)|session limit|usage limit|weekly limit' \
      <<<"$LOG_TAIL"$'\n'"$REPORT_TAIL" | head -1 | tr -d '\r\n' | cut -c 1-200 || true)"
  fi

  if (( TIMED_OUT )); then
    SUBJECT="[Borg/$AGENT_NAME] scheduled task TIMED OUT, did not complete: $TASK_NAME (killed after $TIMEOUT)"
  elif [[ -n "$LIMIT_LINE" ]]; then
    # Lexically distinct from a hard failure, and the subject carries the verdict
    # so it can be acted on without opening the mail: STARVED means the budget is
    # gone and re-running now dies the same way, whereas FAILED means something
    # broke and a re-run is worth trying. The harness usually names the reset
    # clock in the same line; lift it into the subject when it does.
    RESET_HINT="$(sed -n 's/.*[Rr]esets \(.*\)$/\1/p' <<<"$LIMIT_LINE" | cut -c 1-60)"
    if [[ -n "$RESET_HINT" ]]; then
      SUBJECT="[Borg/$AGENT_NAME] scheduled task STARVED (usage limit), no output: $TASK_NAME — wait for reset $RESET_HINT"
    else
      SUBJECT="[Borg/$AGENT_NAME] scheduled task STARVED (usage limit), no output: $TASK_NAME — wait for the reset"
    fi
  else
    SUBJECT="[Borg/$AGENT_NAME] scheduled task FAILED: $TASK_NAME (exit $STATUS)"
  fi

  {
    if (( TIMED_OUT )); then
      echo "Scheduled task '$TASK_NAME' DID NOT COMPLETE: it was still running when"
      echo "its wall-clock limit of $TIMEOUT ran out, so the runner killed its whole"
      echo "process tree (SIGTERM, then SIGKILL after ${TIMEOUT_GRACE_SECONDS}s)."
      echo
      echo "Whatever the run was doing is unfinished: an email it would have sent was"
      echo "not sent, and a state write it would have made was not made. launchd will"
      echo "not retry before the next scheduled firing, so if this period's result is"
      echo "still wanted, rerun the job by hand. If the task legitimately needs longer,"
      echo "raise TIMEOUT= in its .conf sidecar instead."
      echo
    elif [[ -n "$LIMIT_LINE" ]]; then
      echo "Scheduled task '$TASK_NAME' was STARVED: it hit the harness usage limit"
      echo "and terminated before doing any work. It produced no result."
      echo
      echo "    $LIMIT_LINE"
      echo
      echo "This is not a task failure — nothing is broken and there is nothing to"
      echo "fix. Re-running before the budget resets will die exactly the same way."
      echo "launchd fires each job once with no retry, so this run is simply lost:"
      echo "a task with a state gate will pick the work up at its next firing, and a"
      echo "task without one (a pure report) has lost this period's run for good."
      echo
    else
      echo "Scheduled task '$TASK_NAME' exited $STATUS."
      echo
    fi
    echo "  agent:   $AGENT_NAME"
    echo "  harness: $HARNESS"
    echo "  session: ${SESSION_ID:-${CODEX_SESSION:-unknown}}"
    echo "  started: $START_STAMP"
    echo "  ended:   $END_STAMP (ran ${RUN_SECONDS}s)"
    echo "  log:     $LOG_FILE"
    [[ -n "$REPORT_FILE" ]] && echo "  report:  $REPORT_FILE"
    echo
    echo "Last lines of the log:"
    echo "$LOG_TAIL"
    if [[ -n "$REPORT_TAIL" ]]; then
      echo
      echo "Last lines of the captured report (this task's stdout):"
      echo "$REPORT_TAIL"
    fi
    # Closing section per the workspace AGENTS.md communication style. A real
    # failure has an obvious next step, so this caller supplies a static one
    # rather than notify-email.sh synthesizing it (see that script's header).
    # The STARVED branch deliberately gets none: it says above that nothing is
    # broken and nothing needs fixing, and the convention omits the section when
    # no meaningful next step exists. Suggesting a re-run there would also be
    # wrong on the facts — it would die the same way until the budget resets.
    if (( TIMED_OUT )); then
      echo
      echo "## Suggested Next Prompt"
      echo
      echo '```text'
      echo "Diagnose why the scheduled task '$TASK_NAME' hung past its $TIMEOUT limit and was killed at $END_STAMP: read $LOG_FILE and the session ${SESSION_ID:-${CODEX_SESSION:-transcript}}, find the last action before the stall, and propose a fix; then rerun the job if this period's result is still needed."
      echo '```'
    elif [[ -z "$LIMIT_LINE" ]]; then
      echo
      echo "## Suggested Next Prompt"
      echo
      echo '```text'
      echo "Diagnose why the scheduled task '$TASK_NAME' exited $STATUS on $END_STAMP: read $LOG_FILE, identify the cause, and propose a fix."
      echo '```'
    fi
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

}
main "$@"; exit $?
