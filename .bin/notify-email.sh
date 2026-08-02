#!/bin/bash
# Send a multipart plain-text + HTML notification, reading Markdown from stdin.
#
# HTML is the default for every caller. The bundled Python 3 renderer has no
# third-party dependencies and supports the scheduled jobs' Markdown subset:
# headings, ordered/unordered lists, pipe tables, links, emphasis, inline and
# fenced/indented code, block quotes, rules, and paragraphs. It escapes raw
# HTML; nested lists, images, footnotes, task lists, and other extensions remain
# readable text. The original body is always the first (text/plain) alternative.
#
# Outbound-only by design: no MCP server. Scheduled model tasks run via
# run-scheduled-task.sh with --strict-mcp-config and < /dev/null, while
# deterministic shell maintenance invokes this directly. This script sends
# over Gmail SMTP via curl — no server, nothing to clobber.
#
# Usage: notify-email.sh <agent> [subject] < body
#   agent   — c4po | mrs-beast | warren-bot-fett (labels the From line + subject)
#   subject — optional; defaults to "[Borg/<agent>] notification"
#
# Credentials come from the Borg's single consolidated env file (chmod 600).
# It lives at ~/.borg-secrets/.env, OUTSIDE the workspace, because ~/theborg is
# a Google Drive mirror root — a secret stored under it uploads to the cloud in
# plaintext, and a Drive-side delete propagates down and removes it locally.
# Resolution order: $BORG_ENV_FILE, then ~/.borg-secrets/.env, then the legacy
# $BORG_ROOT/.env. The legacy path may be a symlink to the real file, but
# nothing here depends on that symlink existing (it has been deleted once, by
# a Drive-side cleanup, silently breaking every scheduled notification).
# Keys:
#   EMAIL_SMTP_USER  — Gmail address used to authenticate (e.g. selfaware97@gmail.com)
#   EMAIL_SMTP_PASS  — a Gmail *App Password* (not the account password; needs 2FA)
#   EMAIL_FROM       — From address (defaults to EMAIL_SMTP_USER)
#   EMAIL_TO         — recipient (e.g. the-user@example.com)
#   EMAIL_SMTP_HOST  — optional; defaults to smtp.gmail.com
#   EMAIL_SMTP_PORT  — optional; defaults to 587
#
# Resume footer: Codex exposes the exact current session as $CODEX_THREAD_ID;
# prefer it over the runner's pre-launch `codex resume --last` fallback. For
# Claude-driven runs, $BORG_SESSION_ID is pinned before launch. Either tells the
# user how to continue the exact headless session. It remains unchanged in the
# plain part and becomes a muted, separated footer with a code block in HTML.
set -euo pipefail

AGENT="${1:?usage: notify-email.sh <agent> [subject] < body}"
SUBJECT="${2:-[Borg/$AGENT] notification}"

# Workspace root = parent of this script's .bin/ dir; BORG_ROOT overrides.
BORG_ROOT_DIR="${BORG_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# Find the env file (see header for why the workspace copy is not authoritative).
ENV_FILE="${BORG_ENV_FILE:-}"
if [[ -z "$ENV_FILE" ]]; then
  for _cand in "$HOME/.borg-secrets/.env" "$BORG_ROOT_DIR/.env"; do
    if [[ -f "$_cand" ]]; then ENV_FILE="$_cand"; break; fi
  done
fi
[[ -n "$ENV_FILE" && -f "$ENV_FILE" ]] || {
  echo "notify-email: no env file found (checked \$BORG_ENV_FILE, $HOME/.borg-secrets/.env, $BORG_ROOT_DIR/.env)" >&2
  exit 1
}

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

# Resume footer — only for scheduled runs that exported a resume handle.
if [[ -n "${CODEX_THREAD_ID:-}" || -n "${BORG_RESUME_CMD:-}" || -n "${BORG_SESSION_ID:-}" ]]; then
  AGENT_DIR="${BORG_ROOT:-$HOME/theborg}/$AGENT"
  # Repo-hosted agents live under repos/<name>, not at the workspace root.
  [[ -d "$AGENT_DIR" ]] || AGENT_DIR="${BORG_ROOT:-$HOME/theborg}/repos/$AGENT"
  if [[ -n "${CODEX_THREAD_ID:-}" ]]; then
    RESUME_CMD="codex resume $CODEX_THREAD_ID"
  else
    RESUME_CMD="${BORG_RESUME_CMD:-claude --resume ${BORG_SESSION_ID:-}}"
  fi
  BODY="$BODY

— To continue this session, SSH into the Mac Studio and run:
    cd $AGENT_DIR && $RESUME_CMD"
fi

PYTHON_BIN="${BORG_PYTHON_BIN:-python3}"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || {
  echo "notify-email: Python 3 not found (set \$BORG_PYTHON_BIN to override)" >&2
  exit 127
}
RENDERER="$BORG_ROOT_DIR/.bin/render-notification-email.py"
[[ -f "$RENDERER" ]] || { echo "notify-email: renderer not found: $RENDERER" >&2; exit 1; }

printf '%s' "$BODY" | "$PYTHON_BIN" "$RENDERER" \
  --agent "$AGENT" \
  --from-address "$EMAIL_FROM" \
  --to-address "$EMAIL_TO" \
  --subject "$SUBJECT" \
  | curl -fsS --ssl-reqd \
  "smtp://$SMTP_HOST:$SMTP_PORT" \
  --mail-from "$EMAIL_FROM" \
  --mail-rcpt "$EMAIL_TO" \
  --user "$EMAIL_SMTP_USER:$EMAIL_SMTP_PASS" \
  --upload-file - >/dev/null
