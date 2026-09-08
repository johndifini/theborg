#!/usr/bin/env python3
"""Step-7 checks for the interactive memory-audit ``auto_safe`` tier.

The fixture exercises every implemented deterministic action: regenerate a
rule bridge, regenerate a command bridge, and replace the privacy-safe computed
snapshot/review ledger.  It pins exact diffs, second-run idempotence, atomic
precondition failure, rollback restoration, and rollback conflict refusal.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile


HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.dirname(HERE)
ROOT = os.path.dirname(BIN)
TOOL = os.path.join(BIN, "apply-memory-audit.py")
FIXTURE = os.path.join(HERE, "fixtures", "memory-audit-auto-safe")
RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))


def digest(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


def write_json(path, value):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def cli(root, codex, *args):
    result = subprocess.run([sys.executable, TOOL, "--root", root,
                             "--codex-home", codex, *args],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True)
    return result.returncode, result.stdout


def materialize(base):
    root = os.path.join(base, "borg")
    codex = os.path.join(base, "codex")
    inputs = os.path.join(FIXTURE, "input")
    paths = {
        "registry.yaml": (root, "MEMORY-INVENTORY.yaml"),
        "rule-source.md": (root, ".claude/rules/fixture.md"),
        "rule-target.md": (root, ".agents/skills/fixture/SKILL.md"),
        "command-source.md": (root, ".claude/commands/fixture-command.md"),
        "command-target.md": (codex, "skills/fixture-command/SKILL.md"),
        "snapshot-target.json": (root, "c4po/.claude/scheduled/state/memory-inventory.json"),
        "snapshot-candidate.json": (root, "tmp/candidate-memory-inventory.json"),
        "private-overlay.yaml": (root, "syntheticagent/.private/memory-inventory.yaml"),
        "private-note.md": (root, "syntheticagent/.private/note.md"),
    }
    for fixture_name, (base_dir, relative) in paths.items():
        destination = os.path.join(base_dir, relative)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy(os.path.join(inputs, fixture_name), destination)
    manifest = os.path.join(codex, "skills/.theborg-managed-skills.tsv")
    with open(manifest, "w", encoding="utf-8") as handle:
        handle.write("fixture-command\t%s\t%s\n" % (
            os.path.join(root, ".claude/commands/fixture-command.md"),
            digest(os.path.join(codex, "skills/fixture-command/SKILL.md"))))
    os.makedirs(os.path.join(root, ".bin", "tests"), exist_ok=True)
    shutil.copy(os.path.join(BIN, "build-memory-inventory.py"),
                os.path.join(root, ".bin", "build-memory-inventory.py"))
    shutil.copy(os.path.join(HERE, "audit-privacy-scan.py"),
                os.path.join(root, ".bin", "tests", "audit-privacy-scan.py"))
    return root, codex


def build_plan(root, codex):
    expected = os.path.join(FIXTURE, "expected")
    rule_source = os.path.join(root, ".claude/rules/fixture.md")
    rule_target = os.path.join(root, ".agents/skills/fixture/SKILL.md")
    command_source = os.path.join(root, ".claude/commands/fixture-command.md")
    command_target = os.path.join(codex, "skills/fixture-command/SKILL.md")
    manifest_target = os.path.join(codex, "skills/.theborg-managed-skills.tsv")
    snapshot_target = os.path.join(root, "c4po/.claude/scheduled/state/memory-inventory.json")
    candidate = os.path.join(root, "tmp/candidate-memory-inventory.json")
    return {"version": 1, "actions": [
        {"id": "repair-rule", "tier": "auto_safe", "kind": "generated_rule_bridge",
         "target": {"path_root": "borg_root", "path": ".agents/skills/fixture/SKILL.md",
                    "before_sha256": digest(rule_target),
                    "after_sha256": digest(os.path.join(expected, "rule-SKILL.md"))},
         "source": {"path_root": "borg_root", "path": ".claude/rules/fixture.md",
                    "sha256": digest(rule_source)}},
        {"id": "repair-command", "tier": "auto_safe", "kind": "generated_command_bridge",
         "target": {"path_root": "codex_home", "path": "skills/fixture-command/SKILL.md",
                    "before_sha256": digest(command_target),
                    "after_sha256": digest(os.path.join(expected, "command-SKILL.md"))},
         "source": {"path_root": "borg_root", "path": ".claude/commands/fixture-command.md",
                    "sha256": digest(command_source)}},
        {"id": "repair-command-manifest", "tier": "auto_safe",
         "kind": "generated_command_manifest",
         "target": {"path_root": "codex_home",
                    "path": "skills/.theborg-managed-skills.tsv",
                    "before_sha256": digest(manifest_target),
                    "after_sha256": hashlib.sha256(
                        ("fixture-command\t%s\t%s\n" % (
                            command_source,
                            digest(os.path.join(expected, "command-SKILL.md"))
                        )).encode("utf-8")).hexdigest()}},
        {"id": "refresh-snapshot", "tier": "auto_safe", "kind": "generated_snapshot",
         "target": {"path_root": "borg_root", "path": "c4po/.claude/scheduled/state/memory-inventory.json",
                    "before_sha256": digest(snapshot_target), "after_sha256": digest(candidate)},
         "candidate": {"path_root": "borg_root", "path": "tmp/candidate-memory-inventory.json",
                       "sha256": digest(candidate)}},
    ]}


def targets(root, codex):
    return [os.path.join(root, ".agents/skills/fixture/SKILL.md"),
            os.path.join(codex, "skills/fixture-command/SKILL.md"),
            os.path.join(codex, "skills/.theborg-managed-skills.tsv"),
            os.path.join(root, "c4po/.claude/scheduled/state/memory-inventory.json")]


def test_fixtures_diff_idempotence_and_rollback():
    with tempfile.TemporaryDirectory() as base:
        root, codex = materialize(base)
        plan_path = os.path.join(root, "tmp", "plan.json")
        receipt = os.path.join(root, "tmp", "receipt.json")
        code, out = cli(root, codex, "plan", "--candidate-snapshot",
                        "tmp/candidate-memory-inventory.json", "--output", plan_path)
        check("fixtures: planner finds all four deterministic action kinds",
              code == 0, out)
        plan = json.load(open(plan_path, encoding="utf-8"))
        check("fixtures: plan contains both bridges, their manifest, and the snapshot",
              {action["kind"] for action in plan["actions"]} ==
              {"generated_rule_bridge", "generated_command_bridge",
               "generated_command_manifest", "generated_snapshot"},
              plan)
        before = [read(path) for path in targets(root, codex)]

        code, out = cli(root, codex, "apply", "--plan", plan_path, "--receipt", receipt)
        check("apply: the complete auto_safe fixture applies", code == 0, out)
        check("diff: output contains one exact proposed diff per action",
              all(("--- %s.before" % action["id"]) in out and
                  ("+++ %s.after" % action["id"]) in out for action in plan["actions"]), out)
        expected = os.path.join(FIXTURE, "expected")
        after = [read(os.path.join(expected, "rule-SKILL.md")),
                 read(os.path.join(expected, "command-SKILL.md")),
                 ("fixture-command\t%s\t%s\n" % (
                     os.path.join(root, ".claude/commands/fixture-command.md"),
                     digest(os.path.join(expected, "command-SKILL.md")))).encode("utf-8"),
                 read(os.path.join(root, "tmp/candidate-memory-inventory.json"))]
        check("diff: applied bytes equal the independently stored expected fixtures",
              [read(path) for path in targets(root, codex)] == after)

        code, second = cli(root, codex, "apply", "--plan", plan_path, "--receipt", receipt)
        check("idempotence: a second apply finds nothing to do",
              code == 0 and "Nothing to apply" in second, second)
        check("idempotence: the second apply changes no target bytes",
              [read(path) for path in targets(root, codex)] == after)
        second_plan = os.path.join(root, "tmp", "second-plan.json")
        code, planner_out = cli(root, codex, "plan", "--candidate-snapshot",
                                "tmp/candidate-memory-inventory.json", "--output", second_plan)
        check("idempotence: a second planning run finds zero actions",
              code == 0 and json.load(open(second_plan, encoding="utf-8"))["actions"] == [],
              planner_out)

        code, out = cli(root, codex, "rollback", "--receipt", receipt)
        check("rollback: documented receipt restores every original fixture",
              code == 0 and [read(path) for path in targets(root, codex)] == before, out)
        check("rollback: receipt records the completed restoration",
              os.path.exists(receipt) and
              json.load(open(receipt, encoding="utf-8"))["status"] == "rolled_back")
        code, out = cli(root, codex, "rollback", "--receipt", receipt)
        check("rollback: a second rollback is also idempotent",
              code == 0 and "Nothing to roll back" in out, out)


def test_refusal_gates_are_pre_write():
    with tempfile.TemporaryDirectory() as base:
        root, codex = materialize(base)
        original = [read(path) for path in targets(root, codex)]
        cases = []

        wrong_tier = build_plan(root, codex)
        wrong_tier["actions"][0]["tier"] = "propose_patch"
        cases.append(("non-auto_safe tier", wrong_tier))

        source_drift = build_plan(root, codex)
        source_drift["actions"][1]["source"]["sha256"] = "0" * 64
        cases.append(("changed canonical source", source_drift))

        arbitrary = build_plan(root, codex)
        arbitrary["actions"][0]["kind"] = "replace_file"
        cases.append(("unallowlisted action kind", arbitrary))

        uncoupled = build_plan(root, codex)
        uncoupled["actions"] = [action for action in uncoupled["actions"]
                                if action["kind"] != "generated_command_manifest"]
        cases.append(("command repair without its manifest repair", uncoupled))

        for index, (name, plan) in enumerate(cases):
            plan_path = os.path.join(base, "bad-%d.json" % index)
            write_json(plan_path, plan)
            code, out = cli(root, codex, "apply", "--plan", plan_path,
                            "--receipt", os.path.join(root, "tmp", "bad-%d-receipt.json" % index))
            check("gate: %s is refused" % name, code == 1 and "REFUSED:" in out, out)
            check("gate: %s writes no earlier valid action" % name,
                  [read(path) for path in targets(root, codex)] == original)

        valid_path = os.path.join(base, "valid.json")
        write_json(valid_path, build_plan(root, codex))
        code, out = cli(root, codex, "apply", "--plan", valid_path,
                        "--receipt", os.path.join(base, "outside-receipt.json"))
        check("gate: rollback receipts cannot escape the workspace tmp directory",
              code == 1 and "receipt must stay" in out, out)

        outside = os.path.join(base, "outside")
        os.makedirs(outside)
        with open(os.path.join(outside, "candidate.json"), "w", encoding="utf-8") as handle:
            handle.write('{"generation":"outside"}\n')
        os.symlink(outside, os.path.join(root, "tmp", "escape"))
        code, out = cli(root, codex, "plan", "--candidate-snapshot",
                        "tmp/escape/candidate.json", "--output",
                        os.path.join(root, "tmp", "escape-plan.json"))
        check("gate: a symlinked parent cannot escape an allowlisted path root",
              code == 1 and "through a symlink" in out, out)
        code, out = cli(root, codex, "apply", "--plan", valid_path,
                        "--receipt", os.path.join(root, "tmp", "escape", "receipt.json"))
        check("gate: a receipt cannot escape tmp through a symlinked parent",
              code == 1 and "through a symlink" in out, out)


def test_snapshot_privacy_and_rollback_conflict():
    with tempfile.TemporaryDirectory() as base:
        root, codex = materialize(base)
        candidate = os.path.join(root, "tmp/candidate-memory-inventory.json")
        with open(candidate, "w", encoding="utf-8") as handle:
            handle.write('{"path":"syntheticagent/.private/note.md"}\n')
        plan = build_plan(root, codex)
        plan_path = os.path.join(base, "private-plan.json")
        write_json(plan_path, plan)
        code, out = cli(root, codex, "apply", "--plan", plan_path,
                        "--receipt", os.path.join(root, "tmp", "private-receipt.json"))
        check("privacy: a snapshot naming a private path is refused before writes",
              code == 1 and "privacy scan" in out, out)

    with tempfile.TemporaryDirectory() as base:
        root, codex = materialize(base)
        plan = build_plan(root, codex)
        plan_path = os.path.join(base, "plan.json")
        receipt = os.path.join(root, "tmp", "receipt.json")
        write_json(plan_path, plan)
        code, out = cli(root, codex, "apply", "--plan", plan_path, "--receipt", receipt)
        check("rollback conflict setup applies", code == 0, out)
        target = targets(root, codex)[0]
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("changed after apply\n")
        code, out = cli(root, codex, "rollback", "--receipt", receipt)
        check("rollback: post-apply edits are never clobbered",
              code == 1 and "changed after apply" in out, out)


def main():
    test_fixtures_diff_idempotence_and_rollback()
    test_refusal_gates_are_pre_write()
    test_snapshot_privacy_and_rollback_conflict()
    failed = [result for result in RESULTS if not result[1]]
    for name, ok, detail in RESULTS:
        if not ok:
            print("FAIL  %s\n      %s" % (name, detail))
    print("\n%d/%d checks passed." % (len(RESULTS) - len(failed), len(RESULTS)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
