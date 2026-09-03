#!/bin/bash
# install-scheduled-tasks.sh — regenerate the launchd plists for every Borg
# scheduled task from a single source of truth, and optionally load them.
#
# Why this exists: the live plists live in ~/Library/LaunchAgents/ (outside the
# repo) and embed absolute paths, so they can't be committed verbatim. This
# script rebuilds them from BORG_ROOT, keeping them in lockstep with the
# tracked task inventory and eliminating hand-edited drift. To change a task's
# cadence, edit its schedule-id in the TASKS table and re-run.
#
# Usage:
#   .bin/install-scheduled-tasks.sh           write plists to ~/Library/LaunchAgents
#   .bin/install-scheduled-tasks.sh --print   print to stdout, write nothing
#   .bin/install-scheduled-tasks.sh --load    write, then (re)register with launchd
set -euo pipefail

MODE="write"
case "${1:-}" in
  --print) MODE="print" ;;
  --load)  MODE="load" ;;
  "")      MODE="write" ;;
  *) echo "usage: $(basename "$0") [--print|--load]" >&2; exit 64 ;;
esac

BORG_ROOT="${BORG_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

# Task table: <agent>|<task-name>|<schedule-id>|<kind>[|<target>]
# task-name becomes the launchd label com.theborg.<task-name>. schedule-id is
# expanded by schedule_xml() below. kind is one of:
#   prompt      the normal model runner, driving <agent>/.claude/scheduled/<task>.prompt
#   cli-update  the model-less maintenance runner (.bin/run-cli-update.sh)
#   script      any other model-less shell job; <target> is the script path
#               relative to BORG_ROOT and is required for this kind
# Model-less shell jobs deliberately have no fake .prompt or slash-command
# companion; LINT.md records that narrow exemption. <agent> is relative to
# BORG_ROOT.
TASKS=(
  # Moved off 10:00 on 2026-09-02: 10:00 sits inside the Wednesday burndown's
  # 01:00-11:00 burn window, and this job has no state gate and no retry
  # firing, so a starved run is a lost audit rather than a no-op. It was in
  # fact lost on 2026-09-02 (exit 1 after one second, no report, no email).
  "c4po|c4po-security-audit|daily-13-00|prompt"
  # The four monthly model jobs sit on a six-hour grid — 03:00 privacy, 09:00
  # warren-bot-fett/ai-sleeve, 15:00 lint, 21:00 assumptions — so no two share
  # a five-hour usage window. The grid is ANCHORED ON ai-sleeve's pre-existing
  # 09:00 (declared further down); the three c4po audits were placed around it.
  # Move ai-sleeve and the grid breaks — rephase all four, don't shift one.
  #
  # Two of them, 03:00 and 09:00, land inside c4po-backlog-burndown's pre-reset
  # window (reset minus two session windows minus slack — Wed 00:40-10:30 for an
  # 11:00 reset). That is unavoidable, not an oversight: the window is ~9h50m
  # wide, so four jobs spaced >5h apart need >15h of the 14h10m left outside it,
  # and any 6h grid puts at least one slot inside a window that wide. This
  # phasing is the best available with ai-sleeve fixed at 09:00 — it moved lint
  # and assumptions out of the window and off each other, at the cost of putting
  # privacy in. A phasing that halves the overlap (05/11/17/23) exists but
  # requires moving ai-sleeve, which is warren-bot-fett's call, not this file's.
  #
  # Keep the first-five-days retries: each prompt's state gate makes later
  # firings no-ops after a successful run.
  "c4po|c4po-lint-audit-monthly|month-first5-15-00|prompt"
  "c4po|c4po-assumptions-audit-monthly|month-first5-21-00|prompt"
  "c4po|c4po-privacy-audit-monthly|month-first5-03-00|prompt"
  "c4po|c4po-retro|weekly-wed-thu-12-00|prompt"
  "c4po|c4po-backlog-burndown|weekly-wed-01-00-06-10|prompt"
  "c4po|c4po-cli-update|weekly-sun-06-00|cli-update"
  "mrs-beast|mrs-beast-social-media-drafts|weekly-sun-wed-16-00|prompt"
  # Paused 2026-08-06 for a ~4-month account rebalance: the label is `launchctl
  # disable`d in the gui domain, so --load writes its plist but skips the
  # bootstrap (see the disabled check below) rather than failing with EIO. The
  # row stays so the job remains in the tracked inventory; the one-shot reminder
  # below fires 2026-12-06 to ask whether to re-enable it.
  "warren-bot-fett|warren-bot-fett-daily-market-scan|weekly-mon-fri-09-00|prompt"
  "warren-bot-fett|warren-bot-fett-ai-sleeve-monthly|month-first5-09-00|prompt"
)

# Where each row came from, index-aligned with TASKS. Only used to make a bad
# schedule id actionable: a row from a gitignored private table or a repos/
# .conf can outlive the schedule_xml() case it names, because the row is
# untracked and the case is branch-tracked. Naming the source file tells you
# whether to fix a typo or to check out the branch that defines the schedule.
TASK_ORIGINS=()
for _row in "${TASKS[@]}"; do TASK_ORIGINS+=("the TASKS table in this script"); done

# Repo-hosted tasks: each independent repo under repos/ can register a scheduled
# job with this framework without a row in the table above. It drops a
# <task>.conf beside its <task>.prompt with a SCHEDULE= line; we discover those
# from the filesystem (repos/ is git-ignored, so nothing repo-specific is
# tracked in The Borg). The same .conf carries the runner's per-task overrides
# (see run-scheduled-task.sh); here we read only SCHEDULE.
shopt -s nullglob
for conf in "$BORG_ROOT"/repos/*/.claude/scheduled/*.conf; do
  task="$(basename "$conf" .conf)"
  agent_dir="$(cd "$(dirname "$conf")/../.." && pwd)"   # repos/<name>
  agent="${agent_dir#"$BORG_ROOT"/}"
  SCHEDULE=""
  # shellcheck disable=SC1090
  source "$conf"
  if [[ -z "$SCHEDULE" ]]; then
    echo "warning: no SCHEDULE in $conf — skipping" >&2
    continue
  fi
  TASKS+=("$agent|$task|$SCHEDULE|prompt")
  TASK_ORIGINS+=("$conf")
done

# Private task tables use the main table's row format but live in a gitignored
# glob so local-only job names never enter the public repository. Keeping those
# rows as data lets this installer remain the sole plist generator.
for table in "$BORG_ROOT"/.private/scheduled-tasks/*.tasks; do
  while IFS= read -r row || [[ -n "$row" ]]; do
    [[ -z "$row" || "$row" == \#* ]] && continue
    TASKS+=("$row")
    TASK_ORIGINS+=("$table")
  done < "$table"
done
shopt -u nullglob

# Emit one <dict> calendar entry. Args: Key=Value among Day/Weekday/Hour/Minute.
cal_entry() {
  printf '        <dict>\n'
  local kv
  for kv in "$@"; do
    printf '            <key>%s</key>\n            <integer>%s</integer>\n' "${kv%%=*}" "${kv##*=}"
  done
  printf '        </dict>\n'
}

# Emit the StartCalendarInterval block for a schedule id.
schedule_xml() {
  case "$1" in
    daily-10-00)
      printf '    <key>StartCalendarInterval</key>\n    <dict>\n'
      printf '        <key>Hour</key>\n        <integer>10</integer>\n'
      printf '        <key>Minute</key>\n        <integer>0</integer>\n'
      printf '    </dict>\n'
      ;;
    # 13:00 daily — two hours after the Wednesday weekly reset, so a daily job
    # never lands inside the burndown's Wed 01:00-11:00 burn window, and two
    # hours before the 15:00 monthly slot. See
    # .claude/rules/burndown-window-is-not-schedulable.md.
    daily-13-00)
      printf '    <key>StartCalendarInterval</key>\n    <dict>\n'
      printf '        <key>Hour</key>\n        <integer>13</integer>\n'
      printf '        <key>Minute</key>\n        <integer>0</integer>\n'
      printf '    </dict>\n'
      ;;
    month-first5-09-00)
      printf '    <key>StartCalendarInterval</key>\n    <array>\n'
      for d in 1 2 3 4 5; do cal_entry "Day=$d" "Hour=9" "Minute=0"; done
      printf '    </array>\n'
      ;;
    month-first5-15-00)
      printf '    <key>StartCalendarInterval</key>\n    <array>\n'
      for d in 1 2 3 4 5; do cal_entry "Day=$d" "Hour=15" "Minute=0"; done
      printf '    </array>\n'
      ;;
    month-first5-21-00)
      printf '    <key>StartCalendarInterval</key>\n    <array>\n'
      for d in 1 2 3 4 5; do cal_entry "Day=$d" "Hour=21" "Minute=0"; done
      printf '    </array>\n'
      ;;
    month-first5-03-00)
      printf '    <key>StartCalendarInterval</key>\n    <array>\n'
      for d in 1 2 3 4 5; do cal_entry "Day=$d" "Hour=3" "Minute=0"; done
      printf '    </array>\n'
      ;;
    weekly-sun-wed-16-00)
      printf '    <key>StartCalendarInterval</key>\n    <array>\n'
      for w in 0 1 2 3; do cal_entry "Weekday=$w" "Hour=16" "Minute=0"; done
      printf '    </array>\n'
      ;;
    weekly-tue-wed-17-30)
      printf '    <key>StartCalendarInterval</key>\n    <array>\n'
      for w in 2 3; do cal_entry "Weekday=$w" "Hour=17" "Minute=30"; done
      printf '    </array>\n'
      ;;
    weekly-mon-fri-09-00)
      printf '    <key>StartCalendarInterval</key>\n    <array>\n'
      for w in 1 2 3 4 5; do cal_entry "Weekday=$w" "Hour=9" "Minute=0"; done
      printf '    </array>\n'
      ;;
    weekly-mon-wed-fri-09-00)
      printf '    <key>StartCalendarInterval</key>\n    <array>\n'
      for w in 1 3 5; do cal_entry "Weekday=$w" "Hour=9" "Minute=0"; done
      printf '    </array>\n'
      ;;
    # Mon/Thu/Sat 09:00 — three runs a week at roughly even spacing that avoid
    # Wednesday entirely. This is the slot for a job with NO state gate, which
    # cannot no-op and retry if the Wednesday burndown starves it; a starved run
    # is a permanently lost report. See
    # .claude/rules/burndown-window-is-not-schedulable.md.
    weekly-mon-thu-sat-09-00)
      printf '    <key>StartCalendarInterval</key>\n    <array>\n'
      for w in 1 4 6; do cal_entry "Weekday=$w" "Hour=9" "Minute=0"; done
      printf '    </array>\n'
      ;;
    # One-shot: launchd has no "run once" flag and StartCalendarInterval has no
    # year component, so a Month+Day entry fires on that date every year and the
    # job stays loaded until something boots it out. One-shot tasks are expected
    # to remove themselves — plist, task row, and their own files — on the run.
    once-2026-12-06-09-00)
      printf '    <key>StartCalendarInterval</key>\n'
      cal_entry "Month=12" "Day=6" "Hour=9" "Minute=0"
      ;;
    once-2026-12-07-09-00)
      printf '    <key>StartCalendarInterval</key>\n'
      cal_entry "Month=12" "Day=7" "Hour=9" "Minute=0"
      ;;
    weekly-sun-06-00)
      printf '    <key>StartCalendarInterval</key>\n    <dict>\n'
      printf '        <key>Weekday</key>\n        <integer>0</integer>\n'
      printf '        <key>Hour</key>\n        <integer>6</integer>\n'
      printf '        <key>Minute</key>\n        <integer>0</integer>\n'
      printf '    </dict>\n'
      ;;
    # Wednesday 12:00 and Thursday 12:00 — just after this account's weekly
    # usage reset, so the session retro starts on the fresh week's budget.
    # Thursday is the retry if Wednesday's machine was asleep; the prompt's
    # ISO-week GATE skips it if Wednesday already ran. Noon rather than just
    # after the reset leaves the burndown's second run (below) room to finish
    # burning the outgoing week before the retro starts the new one.
    #
    # The reset hour is an ACCOUNT fact and differs per user — a forker whose
    # week rolls over on a different day should change this id rather than
    # assume it fits. Nothing derives it from here; `.bin/weekly-reset.sh` is
    # the run-time source of truth.
    weekly-wed-thu-12-00)
      printf '    <key>StartCalendarInterval</key>\n    <array>\n'
      for w in 3 4; do cal_entry "Weekday=$w" "Hour=12" "Minute=0"; done
      printf '    </array>\n'
      ;;
    # Wednesday 01:00 and Wednesday 06:10 — ~10h and ~4h50m before this
    # account's weekly usage reset. Two firings because the 5-hour session limit
    # caps one run's burn: the second starts just past the first's session-limit
    # boundary and resumes the same plan (the prompt's GATE handles resume).
    # Derived from the burndown's invariant, not chosen by hand — worked here
    # against an 11:00 reset:
    #   second fire = reset - window + 10min  = 11:00 - 5:00 + 0:10 = 06:10
    #   first fire  = second - window - 10min = 06:10 - 5:10        = 01:00
    #
    # These times are a COARSE APPROXIMATION and are allowed to be. The reset is
    # an account fact that differs per user (and on codex it drifts week to
    # week), so no fixed launchd time can track it. The burndown's WINDOW phase
    # reads the real reset via `.bin/weekly-reset.sh` at fire time and declines
    # to run outside its valid window; Assumption H checks monthly that at least
    # one of these times still lands inside it.
    weekly-wed-01-00-06-10)
      printf '    <key>StartCalendarInterval</key>\n    <array>\n'
      cal_entry "Weekday=3" "Hour=1" "Minute=0"
      cal_entry "Weekday=3" "Hour=6" "Minute=10"
      printf '    </array>\n'
      ;;
    *)
      echo "unknown schedule id: $1" >&2; return 1 ;;
  esac
}

# Emit a complete plist for one task.
plist_xml() {
  local agent="$1" task="$2" sched="$3" kind="$4" target="${5:-}"
  local agent_dir="$BORG_ROOT/$agent"
  local logdir="$agent_dir/.claude/scheduled/logs"
  local arguments
  case "$kind" in
    prompt)
      arguments="        <string>/bin/bash</string>
        <string>$BORG_ROOT/.bin/run-scheduled-task.sh</string>
        <string>$agent_dir</string>
        <string>$agent_dir/.claude/scheduled/$task.prompt</string>"
      ;;
    cli-update)
      arguments="        <string>/bin/bash</string>
        <string>$BORG_ROOT/.bin/run-cli-update.sh</string>"
      ;;
    script)
      arguments="        <string>/bin/bash</string>
        <string>$BORG_ROOT/$target</string>"
      ;;
    *) echo "unknown task kind: $kind" >&2; return 1 ;;
  esac
  # Capture the schedule block before emitting. Interpolating
  # $(schedule_xml ...) straight into the heredoc below discards its exit
  # status, so an unknown id produced a plist with no StartCalendarInterval at
  # all -- a job that installs cleanly and can never fire.
  local schedule
  schedule="$(schedule_xml "$sched")" || return 1
  cat <<XML
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.theborg.$task</string>
    <key>ProgramArguments</key>
    <array>
$arguments
    </array>
$schedule    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$logdir/launchd.out</string>
    <key>StandardErrorPath</key>
    <string>$logdir/launchd.err</string>
</dict>
</plist>
XML
}

# Preflight: resolve every row's schedule id before writing anything. Failing
# here rather than mid-loop means one bad row cannot leave a half-installed set
# behind, and it turns the branch-desync case into a named diagnostic instead
# of a bare "unknown schedule id".
unresolved_schedules=()
for i in "${!TASKS[@]}"; do
  IFS='|' read -r _agent task sched _kind _target <<< "${TASKS[$i]}"
  if ! schedule_xml "$sched" >/dev/null 2>&1; then
    echo "error: task '$task' uses schedule id '$sched', which this script does not define" >&2
    echo "       row source: ${TASK_ORIGINS[$i]}" >&2
    if [[ "${TASK_ORIGINS[$i]}" != "the TASKS table in this script" ]]; then
      echo "       that row is untracked but schedule_xml() is branch-tracked, so this is" >&2
      echo "       either a typo in the row or a checkout that predates the schedule case" >&2
    fi
    unresolved_schedules+=("$task ($sched)")
  fi
done
if (( ${#unresolved_schedules[@]} > 0 )); then
  echo >&2
  echo "error: ${#unresolved_schedules[@]} task(s) name an undefined schedule id; nothing was written:" >&2
  printf '  %s\n' "${unresolved_schedules[@]}" >&2
  exit 1
fi

[[ "$MODE" == "print" ]] || mkdir -p "$LAUNCH_AGENTS"

# Labels that `launchctl disable` has switched off in this user's gui domain.
# Bootstrapping one of those fails with "5: Input/output error", which is
# indistinguishable at the exit code from a real breakage — so we read the
# disabled database once up front and skip those deliberately instead. Snapshot
# it before the loop: nothing below changes it, and it is one subprocess.
UID_N="$(id -u)"
disabled_labels=""
[[ "$MODE" == "load" ]] && disabled_labels="$(launchctl print-disabled "gui/$UID_N" 2>/dev/null || true)"

is_disabled() {
  [[ "$disabled_labels" == *"\"$1\" => disabled"* ]]
}

# Rows whose bootstrap failed, reported together at the end. A failure must not
# abort the loop: under `set -e` one bad row silently skipped every task after
# it in the table, which is how three live jobs went unregistered unnoticed.
bootstrap_failures=()

# Rows whose plist could not be generated. The preflight above already catches
# every undefined schedule id, so this is defense in depth for any future
# generator failure -- reported the same way, and never silently.
render_failures=()

for row in "${TASKS[@]}"; do
  IFS='|' read -r agent task sched kind target <<< "$row"
  # launchd opens StandardOutPath/StandardErrorPath before starting the target,
  # so a newly added agent task needs its ignored log directory to exist before
  # the first load. --print remains strictly read-only.
  [[ "$MODE" == "print" ]] || mkdir -p "$BORG_ROOT/$agent/.claude/scheduled/logs"
  case "$kind" in
    prompt)
      # Deliberately a warning, not an error, unlike an undefined schedule id.
      # A missing .prompt still yields a structurally valid plist whose failure
      # is loud at fire time (the runner exits non-zero into launchd.err),
      # and it is the expected steady state for a fired one-shot, which deletes
      # its own prompt and leaves its row stale by design. An undefined
      # schedule id is the opposite: valid-looking plist, silent forever.
      source_file="$BORG_ROOT/$agent/.claude/scheduled/$task.prompt"
      [[ -f "$source_file" ]] || echo "warning: prompt not found for $task: $source_file" >&2
      ;;
    cli-update)
      source_file="$BORG_ROOT/.bin/run-cli-update.sh"
      [[ -f "$source_file" ]] || echo "warning: runner not found for $task: $source_file" >&2
      ;;
    script)
      if [[ -z "$target" ]]; then
        echo "error: kind 'script' needs a target path: $row" >&2; exit 1
      fi
      source_file="$BORG_ROOT/$target"
      [[ -f "$source_file" ]] || echo "warning: script not found for $task: $source_file" >&2
      ;;
    *) echo "unknown task kind: $kind" >&2; exit 1 ;;
  esac
  dest="$LAUNCH_AGENTS/com.theborg.$task.plist"
  label="com.theborg.$task"

  # Render first, write second. `plist_xml ... > "$dest"` truncates the
  # destination before the generator runs, so a generator failure would replace
  # a working plist with a broken one; building the document in a variable
  # leaves the installed plist untouched when generation fails.
  if ! rendered="$(plist_xml "$agent" "$task" "$sched" "$kind" "$target")"; then
    echo "error: could not generate a plist for $task; leaving $dest as-is" >&2
    render_failures+=("$task")
    continue
  fi

  case "$MODE" in
    print)
      echo "# ===== $dest ====="
      printf '%s\n' "$rendered"
      echo
      ;;
    write|load)
      printf '%s\n' "$rendered" > "$dest"
      echo "wrote $dest"
      if [[ "$MODE" == "load" ]]; then
        if is_disabled "$label"; then
          # Deliberately paused via `launchctl disable`; the plist above is kept
          # current so re-enabling is just `launchctl enable` + bootstrap.
          echo "note: $label is disabled in launchd — skipping bootstrap"
        else
          launchctl bootout "gui/$UID_N/$label" 2>/dev/null || true
          if launchctl bootstrap "gui/$UID_N" "$dest"; then
            echo "loaded $label"
          else
            status=$?
            echo "error: bootstrap failed for $label (exit $status)" >&2
            bootstrap_failures+=("$label")
          fi
        fi
      fi
      ;;
  esac
done

# Surface loaded com.theborg jobs that no current table would regenerate.
# Reconciliation is deliberately advisory: installation never unloads or
# removes an unaccounted-for job.
loaded_jobs="$(launchctl list 2>/dev/null || true)"
while read -r _pid _status label; do
  [[ "$label" == com.theborg.* ]] || continue
  accounted_for=false
  for row in "${TASKS[@]}"; do
    IFS='|' read -r _agent task _sched _kind _target <<< "$row"
    if [[ "$label" == "com.theborg.$task" ]]; then
      accounted_for=true
      break
    fi
  done
  if [[ "$accounted_for" == false ]]; then
    echo "warning: loaded job has no task-table row: $label" >&2
  fi
done <<< "$loaded_jobs"

# Every row was attempted; now fail the run as a whole if any bootstrap did not
# take, so a partial install can't pass for a clean one in a scheduled context.
failed=0
if (( ${#render_failures[@]} > 0 )); then
  echo >&2
  echo "error: ${#render_failures[@]} task(s) could not be generated:" >&2
  printf '  %s\n' "${render_failures[@]}" >&2
  failed=1
fi
if (( ${#bootstrap_failures[@]} > 0 )); then
  echo >&2
  echo "error: ${#bootstrap_failures[@]} job(s) failed to bootstrap:" >&2
  printf '  %s\n' "${bootstrap_failures[@]}" >&2
  failed=1
fi
(( failed == 0 )) || exit 1
