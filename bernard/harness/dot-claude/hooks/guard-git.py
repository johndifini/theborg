#!/usr/bin/env python3
"""PreToolUse hook (Bash matcher): git safety guard for the life wiki.

Makes two CLAUDE.md hard rules mechanical for Claude Code instead of
honor-system. (Codex/Gemini/manual git are NOT covered by Claude Code hooks —
the egress half is backstopped agent-agnostically by .git/hooks/pre-push;
see .claude/scripts/pre-push.sh.)

  * Off-machine egress  -> DENY
      git remote add / git remote set-url / git push
    The wiki is one person's full pseudonymized health record. "Local git only —
    never add a remote." A push or new remote is the one irreversible way the
    whole record leaves this machine outside the gated mirror.

  * Blanket staging     -> ASK
      git add -A / git add --all / git add . / git commit -a|-am|--all
    Many writers share one working tree (interactive agents, the curator's
    terminal, the scheduled write jobs). A broad add sweeps another session's
    in-progress files into your commit (the recorded 2026-06-11 race). Stage
    explicit paths instead.

Everything else passes through untouched. Fast path: non-git commands exit
immediately.
"""
import json
import re
import sys

# Off-machine egress — never allowed for this repo.
RE_EGRESS = re.compile(
    r"\bgit\s+(?:-[^\s]+\s+)*(?:push\b|remote\s+(?:add|set-url|set-branches)\b)"
)
# Blanket staging — surface for explicit-path confirmation.
RE_ADD_ALL = re.compile(r"\bgit\s+add\s+(?:[^\n|;&]*\s)?(?:-A\b|--all\b|\.(?=\s|$))")
RE_COMMIT_ALL = re.compile(
    r"\bgit\s+commit\b(?P<rest>[^\n|;&]*)"
)


def decide(decision: str, reason: str):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def commit_is_blanket(rest: str) -> bool:
    """True if `git commit` carries -a / -am / --all (stages all tracked).

    Excludes --amend / --author (long opts) which merely contain the letters.
    """
    if "--all" in rest:
        return True
    # short-flag clusters only (single dash, not --); a cluster containing 'a'
    # means -a/-am/-amp etc. -> stages all tracked changes.
    for tok in rest.split():
        if tok.startswith("-") and not tok.startswith("--") and "a" in tok:
            return True
    return False


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # malformed input: stay out of the way

    if data.get("tool_name") not in (None, "Bash"):
        sys.exit(0)
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if "git" not in cmd:
        sys.exit(0)  # fast path: not a git command

    if RE_EGRESS.search(cmd):
        decide("deny",
               "Off-machine git egress is a hard rule violation: this repo is "
               "local-git-only — never add a remote or push. The full "
               "pseudonymized health record must never leave this machine "
               "except through the gated VPS mirror. (Curator override: run it "
               "yourself with the reason, or `git push --no-verify` bypasses "
               "the pre-push backstop.)")

    if RE_ADD_ALL.search(cmd):
        decide("ask",
               "Blanket staging (git add -A/./--all) is against the "
               "concurrency hard rule — shared working tree, so a broad add "
               "can sweep another session's in-progress files into your "
               "commit. Stage explicit paths instead, or confirm only your "
               "files are dirty before proceeding.")

    m = RE_COMMIT_ALL.search(cmd)
    if m and commit_is_blanket(m.group("rest")):
        decide("ask",
               "git commit -a/-am/--all stages every tracked change, including "
               "other sessions' in-progress edits in this shared working tree. "
               "Stage explicit paths with `git add <path>` then commit, or "
               "confirm the tree holds only your files.")

    sys.exit(0)


if __name__ == "__main__":
    main()
