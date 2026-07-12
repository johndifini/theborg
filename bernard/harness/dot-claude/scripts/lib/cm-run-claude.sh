#!/usr/bin/env bash
# cm-run-claude.sh — steelman runner for cross-model-review. Reads a prompt on
# stdin, runs read-only headless Claude in the wiki, emits the model's text.
# Anthropic-only: sanctioned egress (model API inherent to running the agent).
set -uo pipefail
WIKI="/Users/lashawsalta/life-wiki"
CLAUDE_BIN="${CLAUDE_BIN:-/opt/homebrew/bin/claude}"
STANCE="Assess the claim even-handedly on the wiki evidence."
PROMPT="$STANCE

$(cat)"
cd "$WIKI" || exit 1
"$CLAUDE_BIN" -p "$PROMPT" --allowedTools "Read,Grep,Glob" 2>&1
