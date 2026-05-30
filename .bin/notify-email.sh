#!/bin/bash
# Send an email notification as an agent, reading the message body from stdin.
#
# Mirrors notify-telegram.sh by design: outbound-only, no MCP server. Scheduled
# tasks run via run-scheduled-task.sh with --strict-mcp-config and < /dev/null,
# so they have no Gmail MCP tool and must not boot one. This script sends over
# Gmail SMTP via curl — no server, nothing to clobber.
#
# Usage: notify-email.sh <agent> [subject] < body
#   agent   — c4po | mrs-beast | warren-bot-fett (labels the From line + subject)
#   subject — optional; defaults to "[Borg/<agent>] notification"
#
# Credentials come from ~/.claude/channels/email-shared/.env (chmod 600):
#   EMAIL_SMTP_USER  — Gmail address used to authenticate (e.g. selfaware97@gmail.com)
#   EMAIL_SMTP_PASS  — a Gmail *App Password* (not the account password; needs 2FA)
#   EMAIL_FROM       — From address (defaults to EMAIL_SMTP_USER)
#   EMAIL_TO         — recipient (e.g. johndifini@gmail.com)
#   EMAIL_SMTP_HOST  — optional; defaults to smtp.gmail.com
#   EMAIL_SMTP_PORT  — optional; defaults to 587
#
# When $BORG_SESSION_ID is set (run-scheduled-task.sh exports it for scheduled
# runs), a footer is appended telling John how to resume that exact session.
set -euo pipefail

AGENT="${1:?usage: notify-email.sh <agent> [subject] < body}"
SUBJECT="${2:-[Borg/$AGENT] notification}"

ENV_FILE="$HOME/.claude/channels/email-shared/.env"
[[ -f "$ENV_FILE" ]] || { echo "notify-email: no env file at $ENV_FILE" >&2; exit 1; }

# Parse KEY=VALUE rather than sourcing: a secret with a space or shell
# metacharacter must never be executed as code. Comment/blank lines (no match)
# are ignored. Trims a trailing CR for CRLF-saved files.
env_get() { sed -n "s/^$1=//p" "$ENV_FILE" | head -1 | tr -d '\r'; }

EMAIL_SMTP_USER="$(env_get EMAIL_SMTP_USER)"
# Gmail App Passwords are displayed in 4-char groups; the spaces are cosmetic
# and Gmail ignores them. Strip all whitespace so a pasted-with-spaces value works.
EMAIL_SMTP_PASS="$(env_get EMAIL_SMTP_PASS | tr -d '[:space:]')"
EMAIL_TO="$(env_get EMAIL_TO)"
EMAIL_FROM="$(env_get EMAIL_FROM)"
SMTP_HOST="$(env_get EMAIL_SMTP_HOST)"
SMTP_PORT="$(env_get EMAIL_SMTP_PORT)"

[[ -n "$EMAIL_SMTP_USER" ]] || { echo "notify-email: EMAIL_SMTP_USER not set in $ENV_FILE" >&2; exit 1; }
[[ -n "$EMAIL_SMTP_PASS" ]] || { echo "notify-email: EMAIL_SMTP_PASS not set in $ENV_FILE" >&2; exit 1; }
[[ -n "$EMAIL_TO" ]]        || { echo "notify-email: EMAIL_TO not set in $ENV_FILE" >&2; exit 1; }
EMAIL_FROM="${EMAIL_FROM:-$EMAIL_SMTP_USER}"
SMTP_HOST="${SMTP_HOST:-smtp.gmail.com}"
SMTP_PORT="${SMTP_PORT:-587}"

BODY="$(cat)"
[[ -n "$BODY" ]] || { echo "notify-email: empty message on stdin" >&2; exit 1; }

# Resume footer — only for scheduled runs that pinned a session id.
if [[ -n "${BORG_SESSION_ID:-}" ]]; then
  AGENT_DIR="${BORG_ROOT:-$HOME/theborg}/$AGENT"
  BODY="$BODY

— To continue this session, SSH into the Mac Studio and run:
    cd $AGENT_DIR && claude --resume $BORG_SESSION_ID"
fi

# SMTP wants CRLF line endings throughout the message.
BODY_CRLF="${BODY//$'\n'/$'\r\n'}"
DATE_HDR="$(date -R 2>/dev/null || date)"

MSG="$(printf 'From: Borg %s <%s>\r\nTo: %s\r\nSubject: %s\r\nDate: %s\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n%s\r\n' \
  "$AGENT" "$EMAIL_FROM" "$EMAIL_TO" "$SUBJECT" "$DATE_HDR" "$BODY_CRLF")"

printf '%s' "$MSG" | curl -fsS --ssl-reqd \
  "smtp://$SMTP_HOST:$SMTP_PORT" \
  --mail-from "$EMAIL_FROM" \
  --mail-rcpt "$EMAIL_TO" \
  --user "$EMAIL_SMTP_USER:$EMAIL_SMTP_PASS" \
  --upload-file - >/dev/null
