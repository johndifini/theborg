#!/usr/bin/env python3
"""Contract tests for /remember and the temporary semantic-review campaign."""

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


def test_bootstrap_policy_is_bounded_and_temporary() -> None:
    command = read(AUDIT_COMMAND)
    prompt = read(AUDIT_PROMPT)
    design = read(DESIGN)
    readme = read(README)

    require("exact `--bootstrap-review` argument" in command,
            "interactive command must require the exact campaign opt-in")
    require("Exact opt-in `--bootstrap-review`" in readme and
            "weekly 15-unit first-review cohort" in readme,
            "README must advertise the exact bootstrap-review mode")
    require("scheduled mode remains capped at 12 public semantic units and 6\n"
            "knowledge pages/sources" in prompt,
            "campaign must not enlarge scheduled audit limits")
    require("Select exactly 15 eligible public canonical semantic units" in prompt,
            "campaign must select a 15-unit cohort")
    require("select at least 12 knowledge\n  pages/sources" in prompt,
            "campaign must preserve its knowledge-throughput floor")
    require("bootstrap-review YYYY-Www" in prompt,
            "campaign must record an ISO-week idempotence marker")
    require("contains any entry with that run marker" in prompt and
            "Later content changes do not reopen that weekly\n  capacity" in prompt,
            "weekly guard must remain closed even if reviewed content changes")
    require("does not imply `--apply`" in prompt,
            "campaign selection must remain report-only without --apply")
    require("registry draft promotions remain `approval_required`" in prompt,
            "campaign must not bypass approval for canonical records")
    require("campaign ends when no eligible public canonical semantic unit\n"
            "  remains" in prompt,
            "campaign must have an explicit retirement condition")

    for phrase in (
        "one cohort per ISO week",
        "exactly 15 current-hash-unreviewed public canonical semantic units",
        "at least 12 selected units are knowledge pages/sources",
        "Rollback verifies the applied hash",
        "never delete or merge them automatically",
    ):
        require(phrase in design, "design is missing policy/rollback text: " + phrase)


def main() -> int:
    tests = (
        test_remember_contract_and_generated_bridge,
        test_bootstrap_policy_is_bounded_and_temporary,
    )
    for test in tests:
        test()
        print("PASS", test.__name__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
