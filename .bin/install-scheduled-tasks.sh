#!/bin/bash
# install-scheduled-tasks.sh — regenerate the launchd plists for every Borg
# scheduled task from a single source of truth, and optionally load them.
#
# Why this exists: the live plists live in ~/Library/LaunchAgents/ (outside the
# repo) and embed absolute paths, so they can't be committed verbatim. This
# script rebuilds them from BORG_ROOT, keeping them in lockstep with the
# .prompt inventory and eliminating hand-edited drift. To change a task's
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
RUNNER="$BORG_ROOT/.bin/run-scheduled-task.sh"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

# Task table: <agent>|<task-name>|<schedule-id>
# task-name matches <agent>/.claude/scheduled/<task-name>.prompt and the launchd
# label com.theborg.<task-name>. schedule-id is expanded by schedule_xml() below.
TASKS=(
  "c4po|c4po-security-audit|daily-10-00"
  "c4po|c4po-lint-audit-monthly|month-first5-09-00"
  "c4po|c4po-assumptions-audit-monthly|month-first5-09-00"
  "c4po|c4po-dream|weekly-sat-sun-22-00"
  "c4po|c4po-backlog-burndown|weekly-wed-06-59"
  "c4po|c4po-consolidate-memory|weekly-sun-mon-23-00"
  "mrs-beast|mrs-beast-social-media-drafts|weekly-sun-wed-16-00"
  "warren-bot-fett|warren-bot-fett-daily-market-scan|weekly-mon-fri-09-00"
  "warren-bot-fett|warren-bot-fett-ai-sleeve-monthly|month-first5-09-00"
)

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
    weekly-sun-wed-16-00)
      printf '    <key>StartCalendarInterval</key>\n    <array>\n'
      for w in 0 1 2 3; do cal_entry "Weekday=$w" "Hour=16" "Minute=0"; done
      printf '    </array>\n'
      ;;
    weekly-mon-fri-09-00)
      printf '    <key>StartCalendarInterval</key>\n    <array>\n'
      for w in 1 2 3 4 5; do cal_entry "Weekday=$w" "Hour=9" "Minute=0"; done
      printf '    </array>\n'
      ;;
    weekly-sat-sun-22-00)
      printf '    <key>StartCalendarInterval</key>\n    <array>\n'
      for w in 6 0; do cal_entry "Weekday=$w" "Hour=22" "Minute=0"; done
      printf '    </array>\n'
      ;;
    # 6:59 AM Wednesday — ~4h before the account's weekly usage reset (Wed
    # 10:59 AM); the prompt's WINDOW phase aborts late (post-reset) firings.
    weekly-wed-06-59)
      printf '    <key>StartCalendarInterval</key>\n    <dict>\n'
      printf '        <key>Weekday</key>\n        <integer>3</integer>\n'
      printf '        <key>Hour</key>\n        <integer>6</integer>\n'
      printf '        <key>Minute</key>\n        <integer>59</integer>\n'
      printf '    </dict>\n'
      ;;
    weekly-sun-mon-23-00)
      printf '    <key>StartCalendarInterval</key>\n    <array>\n'
      for w in 0 1; do cal_entry "Weekday=$w" "Hour=23" "Minute=0"; done
      printf '    </array>\n'
      ;;
    *)
      echo "unknown schedule id: $1" >&2; return 1 ;;
  esac
}

# Emit a complete plist for one task.
plist_xml() {
  local agent="$1" task="$2" sched="$3"
  local agent_dir="$BORG_ROOT/$agent"
  local prompt="$agent_dir/.claude/scheduled/$task.prompt"
  local logdir="$agent_dir/.claude/scheduled/logs"
  cat <<XML
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.theborg.$task</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$RUNNER</string>
        <string>$agent_dir</string>
        <string>$prompt</string>
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
  IFS='|' read -r agent task sched <<< "$row"
  prompt="$BORG_ROOT/$agent/.claude/scheduled/$task.prompt"
  [[ -f "$prompt" ]] || echo "warning: prompt not found for $task: $prompt" >&2
  dest="$LAUNCH_AGENTS/com.theborg.$task.plist"

  case "$MODE" in
    print)
      echo "# ===== $dest ====="
      plist_xml "$agent" "$task" "$sched"
      echo
      ;;
    write|load)
      plist_xml "$agent" "$task" "$sched" > "$dest"
      echo "wrote $dest"
      if [[ "$MODE" == "load" ]]; then
        launchctl bootout "gui/$(id -u)/com.theborg.$task" 2>/dev/null || true
        launchctl bootstrap "gui/$(id -u)" "$dest"
        echo "loaded com.theborg.$task"
      fi
      ;;
  esac
done
