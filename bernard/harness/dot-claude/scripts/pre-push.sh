#!/usr/bin/env bash
# pre-push.sh — agent-agnostic egress backstop (tracked copy of .git/hooks/pre-push).
#
# Hard rule (CLAUDE.md "Egress rules"): this repo is LOCAL GIT ONLY — never add a
# remote, never push. The wiki is one person's full pseudonymized health record;
# the only sanctioned egress is the gated VPS mirror sync. A `git push` is the one
# irreversible way the whole record leaves the machine.
#
# Unlike the Claude Code guard-git.py hook (which only covers Claude Code), this
# git hook fires for EVERY agent and every manual push — Codex, Gemini, the
# curator's terminal, cron. It refuses unconditionally.
#
# Curator override (deliberate, rare): `git push --no-verify`.
#
# Reinstall after clone:
#   cp .claude/scripts/pre-push.sh .git/hooks/pre-push && chmod +x .git/hooks/pre-push
set -uo pipefail

cat >&2 <<'EOF'
╳ PUSH BLOCKED — life-wiki is local-git-only (CLAUDE.md egress hard rule).

  This repo is one person's full pseudonymized health record. It must never
  leave this machine except through the gated, leak-scanned VPS mirror sync.
  Off-site backup is curator-managed encrypted local media — never a git remote.

  If you are the curator and this push is a deliberate, vetted exception:
      git push --no-verify
EOF
exit 1
