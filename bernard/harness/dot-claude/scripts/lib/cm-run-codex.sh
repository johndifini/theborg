#!/usr/bin/env bash
# cm-run-codex.sh — model-B runner for cross-model-review. Reads a prompt on
# stdin, runs read-only non-interactive Codex (gpt-5.5, web disabled per
# .codex/config.toml) in the wiki, emits the model's text.
set -uo pipefail
WIKI="/Users/lashawsalta/life-wiki"
PROMPT="$(cat)"
cd "$WIKI" || exit 1
codex exec --sandbox read-only "$PROMPT" < /dev/null 2>&1
