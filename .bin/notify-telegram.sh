#!/bin/bash
# Send a Telegram message as an agent's bot, reading the message body from stdin.
#
# Scheduled tasks run via run-scheduled-task.sh with --strict-mcp-config, so they
# have no telegram MCP `reply` tool. They must not boot a telegram MCP server of
# their own either: server.ts kills whatever poller holds bot.pid, which would
# clobber the interactive session's poller and leave that agent deaf to Telegram.
# This script sends outbound-only via the HTTP API — no poller, nothing to clobber.
#
# Usage: notify-telegram.sh <agent> [chat_id] < message
#   agent   — c4po | mrs-beast | warren-bot-fett (selects the bot token)
#   chat_id — defaults to $TELEGRAM_CHAT_ID from ~/.claude/channels/telegram-shared/.env
set -euo pipefail

AGENT="${1:?usage: notify-telegram.sh <agent> [chat_id] < message}"
SHARED_ENV="$HOME/.claude/channels/telegram-shared/.env"
[[ -f "$SHARED_ENV" ]] && . "$SHARED_ENV"
CHAT_ID="${2:-${TELEGRAM_CHAT_ID:?TELEGRAM_CHAT_ID not set (expected in $SHARED_ENV or argv[2])}}"
ENV_FILE="$HOME/.claude/channels/telegram-$AGENT/.env"

[[ -f "$ENV_FILE" ]] || { echo "notify-telegram: no env file at $ENV_FILE" >&2; exit 1; }
TOKEN="$(sed -n 's/^TELEGRAM_BOT_TOKEN=//p' "$ENV_FILE")"
[[ -n "$TOKEN" ]] || { echo "notify-telegram: no TELEGRAM_BOT_TOKEN in $ENV_FILE" >&2; exit 1; }

MESSAGE="$(cat)"
[[ -n "$MESSAGE" ]] || { echo "notify-telegram: empty message on stdin" >&2; exit 1; }

API="https://api.telegram.org/bot$TOKEN/sendMessage"

# Telegram caps a single message at 4096 chars — send in <=4000-char chunks.
while [[ -n "$MESSAGE" ]]; do
  CHUNK="${MESSAGE:0:4000}"
  MESSAGE="${MESSAGE:4000}"
  curl -fsS "$API" \
    --data-urlencode "chat_id=$CHAT_ID" \
    --data-urlencode "text=$CHUNK" >/dev/null
done
