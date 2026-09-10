#!/usr/bin/env python3
"""Contract tests for /remember and memory-audit review policy."""

from __future__ import annotations

import os
import subprocess
import tempfile


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REMEMBER = os.path.join(ROOT, ".claude", "commands", "remember.md")
AUDIT_COMMAND = os.path.join(
    ROOT, "c4po", ".claude", "commands", "audit-assumptions.md"
)
AUDIT_PROMPT = os.path.join(
    ROOT, "c4po", ".claude", "scheduled",
    "c4po-assumptions-audit-monthly.prompt",
)
DESIGN = os.path.join(ROOT, "c4po", "LONG-TERM-MEMORY-INVENTORY-DESIGN.md")
README = os.path.join(ROOT, "README.md")
SYNC = os.path.join(ROOT, ".bin", "sync-codex-prompts.sh")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_remember_contract_and_generated_bridge() -> None:
    command = read(REMEMBER)
    readme = read(README)
    require("Keep `MEMORY.md` as a\nconcise index" in command,
            "/remember must define MEMORY.md as a concise index")
    require("first 200 lines or\n25 KB" in command,
            "/remember must preserve the native index load boundary")
    require("topic files" in command and "link those files" in command,
            "/remember must route detail to linked topic files")
    require("the only correct place" not in command,
            "/remember must not describe MEMORY.md as the sole store")
    require("visible to sibling agents" in command,
            "/remember must retain its cross-agent privacy warning")
    require("Keeps `MEMORY.md` as a concise index" in readme and
            "linked topic files" in readme,
            "README must describe the current /remember storage contract")

    with tempfile.TemporaryDirectory() as skills:
        environment = os.environ.copy()
        environment["BORG_ROOT"] = ROOT
        environment["BORG_CODEX_SKILLS_DIR"] = skills
        result = subprocess.run(
            [SYNC], env=environment, text=True, capture_output=True, check=False
        )
        require(result.returncode == 0, result.stdout + result.stderr)
        bridge = read(os.path.join(skills, "remember", "SKILL.md"))
        require("Keep `MEMORY.md` as a\nconcise index" in bridge,
                "generated Codex bridge must carry the index contract")
        require("topic files" in bridge and "visible to sibling agents" in bridge,
                "generated Codex bridge must carry routing and privacy rules")


def test_bulk_bootstrap_review_is_retired() -> None:
    command = read(AUDIT_COMMAND)
    prompt = read(AUDIT_PROMPT)
    design = read(DESIGN)
    readme = read(README)

    for surface, body in (("command", command), ("prompt", prompt),
                          ("README", readme)):
        require("--bootstrap-review" not in body,
                surface + " must not expose the retired bulk-review mode")
    require("at most 12 public semantic" in prompt and
            "at most 6 knowledge pages/sources" in prompt,
            "ordinary scheduled audit limits must remain bounded")
    require("bulk first-review campaign" in command and
            "registered draft remains honestly marked" in command,
            "interactive command must preserve honest draft status")
    require("Complete first-review coverage is not an invariant" in design,
            "design must state that exhaustive bootstrap review is not required")
    require("first-review bootstrap campaign was retired by user decision" in design,
            "design must preserve why the campaign ended")
    require("not bulk-promoted" in design and "historical evidence" in design,
            "design must preserve draft and review-ledger integrity")
    require("Registered drafts are not treated as failures or bulk-promoted" in readme,
            "README must describe the current draft disposition")


def main() -> int:
    tests = (
        test_remember_contract_and_generated_bridge,
        test_bulk_bootstrap_review_is_retired,
    )
    for test in tests:
        test()
        print("PASS", test.__name__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
