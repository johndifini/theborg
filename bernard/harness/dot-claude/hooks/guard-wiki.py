#!/usr/bin/env python3
"""PreToolUse hook: provenance guard for the life wiki.

This is NOT a privacy firewall — wiki content is already pseudonymized and
models have full read access everywhere. It makes the CLAUDE.md write rules
mechanical instead of honor-system:

  * Edit/Write inside ingest/ or any wikis/**/raw/ folder  -> ASK
    (raw files are citation ground truth; curator-authorized cleanups are a
    real recurring exception, so this surfaces the edit rather than blocks it)
  * Writing audio binaries (voice biometrics)              -> DENY
  * Edit/Write of .claude/hooks/ or .claude/settings.json  -> ASK
    (self-protection: the guard can't be silently disabled)

Everything else passes through untouched.
"""
import json
import sys
from pathlib import Path

WIKI = Path(__file__).resolve().parents[2]
AUDIO_EXT = {".m4a", ".mp3", ".wav", ".mp4", ".aac"}


def decide(decision: str, reason: str):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # malformed input: stay out of the way

    tool_input = data.get("tool_input") or {}
    raw_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not raw_path:
        sys.exit(0)

    p = Path(raw_path)
    if not p.is_absolute():
        p = Path(data.get("cwd", str(WIKI))) / p
    try:
        rel = p.resolve().relative_to(WIKI)
    except (ValueError, OSError):
        sys.exit(0)  # outside the wiki: not ours to police

    if p.suffix.lower() in AUDIO_EXT:
        decide("deny",
               f"{rel}: audio binaries are never written to the wiki "
               "(voice-biometric hard rule in CLAUDE.md).")

    parts = rel.parts
    if parts and parts[0] == "ingest":
        decide("ask",
               f"{rel} is in ingest/ — hard rule: read, classify, route, move; "
               "never modify in place. Confirm this edit is curator-authorized.")

    if len(parts) > 2 and parts[0] == "wikis" and "raw" in parts[1:-1]:
        decide("ask",
               f"{rel} is a raw/ source file (citation ground truth) — normally "
               "never modified in place. Confirm this edit is curator-authorized.")

    rel_s = rel.as_posix()
    if rel_s.startswith(".claude/hooks/") or rel_s == ".claude/settings.json":
        decide("ask",
               f"{rel} is part of the hook harness — confirm this "
               "self-modification is intended.")

    sys.exit(0)


if __name__ == "__main__":
    main()
