#!/usr/bin/env bash
# cm-run-claude-skeptic.sh — adversarial runner for cross-model-review. Same model
# (Anthropic, sanctioned egress) but an opposing stance: actively try to REFUTE the
# claim. Independent perspective catches what a single fair pass rationalizes away,
# without any cross-vendor PHI egress.
set -uo pipefail
WIKI="/Users/lashawsalta/life-wiki"
CLAUDE_BIN="${CLAUDE_BIN:-/opt/homebrew/bin/claude}"
STANCE="You are a SKEPTICAL reviewer. Actively try to REFUTE the claim. Hunt for \
missing evidence, alternative explanations, and contradicting wiki entries. Default \
to VERDICT: UNSUPPORTED unless the wiki evidence is genuinely strong and specific."
PROMPT="$STANCE

$(cat)"
cd "$WIKI" || exit 1
"$CLAUDE_BIN" -p "$PROMPT" --allowedTools "Read,Grep,Glob" 2>&1
