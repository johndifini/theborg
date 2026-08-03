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

# Task table: <agent>|<task-name>|<schedule-id>|<kind>
# task-name becomes the launchd label com.theborg.<task-name>. schedule-id is
# expanded by schedule_xml() below. kind is "prompt" (the normal model runner)
# or "cli-update" (the model-less maintenance runner). Model-less shell jobs
# deliberately have no fake .prompt or slash-command companion; LINT.md records
# that narrow exemption. <agent> is relative to BORG_ROOT.
TASKS=(
  "c4po|c4po-security-audit|daily-10-00|prompt"
  "c4po|c4po-lint-audit-monthly|month-first5-09-00|prompt"
  "c4po|c4po-assumptions-audit-monthly|month-first5-09-00|prompt"
  "c4po|c4po-privacy-audit-monthly|month-first5-11-00|prompt"
  "c4po|c4po-retro|weekly-sat-sun-08-00|prompt"
  "c4po|c4po-backlog-burndown|weekly-fri-21-09-sat-02-19|prompt"
  "c4po|c4po-cli-update|weekly-sun-06-00|cli-update"
  "mrs-beast|mrs-beast-social-media-drafts|weekly-sun-wed-16-00|prompt"
  "warren-bot-fett|warren-bot-fett-daily-market-scan|weekly-mon-fri-09-00|prompt"
  "warren-bot-fett|warren-bot-fett-ai-sleeve-monthly|month-first5-09-00|prompt"
)

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
done

# Private task tables use the main table's row format but live in a gitignored
# glob so local-only job names never enter the public repository. Keeping those
# rows as data lets this installer remain the sole plist generator.
for table in "$BORG_ROOT"/.private/scheduled-tasks/*.tasks; do
  while IFS= read -r row || [[ -n "$row" ]]; do
    [[ -z "$row" || "$row" == \#* ]] && continue
    TASKS+=("$row")
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
    month-first5-09-00)
      printf '    <key>StartCalendarInterval</key>\n    <array>\n'
      for d in 1 2 3 4 5; do cal_entry "Day=$d" "Hour=9" "Minute=0"; done
      printf '    </array>\n'
      ;;
    month-first5-11-00)
      printf '    <key>StartCalendarInterval</key>\n    <array>\n'
      for d in 1 2 3 4 5; do cal_entry "Day=$d" "Hour=11" "Minute=0"; done
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
    weekly-sun-06-00)
      printf '    <key>StartCalendarInterval</key>\n    <dict>\n'
      printf '        <key>Weekday</key>\n        <integer>0</integer>\n'
      printf '        <key>Hour</key>\n        <integer>6</integer>\n'
      printf '        <key>Minute</key>\n        <integer>0</integer>\n'
      printf '    </dict>\n'
      ;;
    # Saturday 08:00 and Sunday 08:00 — just after the account's weekly Codex
    # usage reset (Sat 7:09 AM local), so the session retro (now a codex job)
    # starts the fresh week's budget. Sunday is the retry if Saturday's machine
    # was asleep; the prompt's ISO-week GATE skips it if Saturday already ran.
    weekly-sat-sun-08-00)
      printf '    <key>StartCalendarInterval</key>\n    <array>\n'
      for w in 6 0; do cal_entry "Weekday=$w" "Hour=8" "Minute=0"; done
      printf '    </array>\n'
      ;;
    # Friday 21:09 and Saturday 02:19 — ~10h and ~4h50m before the account's
    # weekly Codex usage reset (Sat 7:09 AM local). Two firings because the
    # 5-hour session limit caps one run's burn: the second starts just past the
    # first's session-limit boundary and resumes the same plan (the prompt's
    # GATE handles resume; its WINDOW phase aborts late, post-reset firings).
    weekly-fri-21-09-sat-02-19)
      printf '    <key>StartCalendarInterval</key>\n    <array>\n'
      cal_entry "Weekday=5" "Hour=21" "Minute=9"
      cal_entry "Weekday=6" "Hour=2" "Minute=19"
      printf '    </array>\n'
      ;;
    *)
      echo "unknown schedule id: $1" >&2; return 1 ;;
  esac
}

# Emit a complete plist for one task.
plist_xml() {
  local agent="$1" task="$2" sched="$3" kind="$4"
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
    *) echo "unknown task kind: $kind" >&2; return 1 ;;
  esac
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
$(schedule_xml "$sched")    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$logdir/launchd.out</string>
    <key>StandardErrorPath</key>
    <string>$logdir/launchd.err</string>
</dict>
</plist>
XML
}

[[ "$MODE" == "print" ]] || mkdir -p "$LAUNCH_AGENTS"

for row in "${TASKS[@]}"; do
  IFS='|' read -r agent task sched kind <<< "$row"
  case "$kind" in
    prompt)
      source_file="$BORG_ROOT/$agent/.claude/scheduled/$task.prompt"
      [[ -f "$source_file" ]] || echo "warning: prompt not found for $task: $source_file" >&2
      ;;
    cli-update)
      source_file="$BORG_ROOT/.bin/run-cli-update.sh"
      [[ -f "$source_file" ]] || echo "warning: runner not found for $task: $source_file" >&2
      ;;
    *) echo "unknown task kind: $kind" >&2; exit 1 ;;
  esac
  dest="$LAUNCH_AGENTS/com.theborg.$task.plist"

  case "$MODE" in
    print)
      echo "# ===== $dest ====="
      plist_xml "$agent" "$task" "$sched" "$kind"
      echo
      ;;
    write|load)
      plist_xml "$agent" "$task" "$sched" "$kind" > "$dest"
      echo "wrote $dest"
      if [[ "$MODE" == "load" ]]; then
        launchctl bootout "gui/$(id -u)/com.theborg.$task" 2>/dev/null || true
        launchctl bootstrap "gui/$(id -u)" "$dest"
        echo "loaded com.theborg.$task"
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
    IFS='|' read -r _agent task _sched _kind <<< "$row"
    if [[ "$label" == "com.theborg.$task" ]]; then
      accounted_for=true
      break
    fi
  done
  if [[ "$accounted_for" == false ]]; then
    echo "warning: loaded job has no task-table row: $label" >&2
  fi
done <<< "$loaded_jobs"
