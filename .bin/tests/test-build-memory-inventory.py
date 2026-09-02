#!/usr/bin/env python3
"""Self-check for .bin/build-memory-inventory.py.

    python3 .bin/tests/test-build-memory-inventory.py

Covers migration steps 1, 2, and 3 of
`c4po/LONG-TERM-MEMORY-INVENTORY-DESIGN.md`.

Step 1 — schema and validator:

  1. the YAML subset reader parses what the registry uses and fails loudly —
     never silently — on anything it does not implement;
  2. the validator rejects a malformed record for each rule the schema and the
     cross-record layer are supposed to enforce, and accepts a valid one;
  3. the real registry and the synthetic private overlay in this repo validate
     clean, end to end, through the CLI's exit codes.

Step 2 — discovery, against a synthetic workspace built in a temp directory so
the expected classification is exact and does not drift as The Borg grows:

  4. every shape in the artifact taxonomy is classified, every exclusion is
     recorded with a reason, and nothing in a memory-bearing location is left
     unaccounted for;
  5. canonical/mirror pairs resolve — wrappers, symlinks, rule bridges, and the
     Codex command bridge read from its manifest — and a bridge with no
     canonical source is reported rather than quietly resolved;
  6. discovery mutates nothing it discovers, and names no private path unless
     `--show-private` is passed;
  7. coverage is measured but not enforced: a wholly unregistered tree still
     exits 0, because the LINT.md rule is gated on migration step 4.

Step 3 — the split between registered and reviewed, and the bootstrap that
produces the difference:

  8. `status: draft` relaxes exactly the human-judgment fields and nothing else;
     omitting the flag is the strict state, a draft cannot claim a review date,
     a draft that has cleared the promotion gate must be promoted, and the flag
     is not defaultable by class;
  9. the YAML writer round-trips through this tool's own reader and refuses the
     shapes it cannot express rather than stringifying them;
 10. bootstrap is a dry run by default, is idempotent, defers artifacts it
     cannot honestly describe, and — over the fixture and over the live
     workspace — puts no private path in a tracked file.

No third-party dependencies: this workspace has neither PyYAML nor jsonschema
and cannot install them, which is why the tool implements both subsets itself.
"""

from __future__ import annotations

import copy
import datetime as _dt
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.dirname(HERE)
ROOT = os.path.dirname(BIN)
TOOL = os.path.join(BIN, "build-memory-inventory.py")

_spec = importlib.util.spec_from_file_location("build_memory_inventory", TOOL)
bmi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bmi)

SCHEMA = json.load(open(os.path.join(ROOT, "MEMORY-INVENTORY.schema.json"), encoding="utf-8"))
TODAY = _dt.date(2026, 8, 26)

_results = []


def check(name, condition, detail=""):
    _results.append((name, bool(condition), detail))


# --------------------------------------------------------------------------
# 1. YAML subset reader
# --------------------------------------------------------------------------

def test_yaml_reader():
    doc = """
# leading comment
version: 1
defaults:
  scoped_rule:
    review_cadence: quarterly     # trailing comment
    review_method: [semantic, usage]
artifacts:
  a-record:
    path: "a/b c.md"
    quoted_hash: "not # a comment"
    single: 'it''s fine'
    empty_flow: []
    explicit_null: null
    tilde_null: ~
    truthy: true
    count: 12
    block_list:
      - first item
      - "second item"
    objects:
      - kind: workspace_decision
        reference: "r one"
      - kind: incident
        reference: "r two"
    same_indent_list:
    - one
    - two
"""
    got = bmi.load_yaml(doc, "t.yaml")
    want = {
        "version": 1,
        "defaults": {"scoped_rule": {"review_cadence": "quarterly",
                                     "review_method": ["semantic", "usage"]}},
        "artifacts": {"a-record": {
            "path": "a/b c.md",
            "quoted_hash": "not # a comment",
            "single": "it's fine",
            "empty_flow": [],
            "explicit_null": None,
            "tilde_null": None,
            "truthy": True,
            "count": 12,
            "block_list": ["first item", "second item"],
            "objects": [{"kind": "workspace_decision", "reference": "r one"},
                        {"kind": "incident", "reference": "r two"}],
            "same_indent_list": ["one", "two"],
        }},
    }
    check("yaml: parses the constructs the registry uses", got == want,
          "got %r" % (got,))

    # A date must stay a string so `format: date` can check it and so the value
    # round-trips through the JSON snapshot unchanged.
    check("yaml: unquoted dates stay strings",
          bmi.load_yaml("d: 2026-08-26")["d"] == "2026-08-26")

    unsupported = [
        ("tab indentation", "a:\n\tb: 1"),
        ("block scalar", "a: |\n  text"),
        ("folded scalar", "a: >\n  text"),
        ("anchor", "a: &anchor 1"),
        ("alias", "a: *anchor"),
        ("tag", "a: !!str 1"),
        ("flow mapping", "a: {b: 1}"),
        ("duplicate key", "a: 1\na: 2"),
        ("unterminated flow sequence", "a: [1, 2"),
        ("bare scalar where a key belongs", "a: 1\nnope"),
        ("over-indented sibling", "a: 1\n  b: 2"),
        ("unterminated double quote", 'a: "b'),
    ]
    for label, text in unsupported:
        try:
            bmi.load_yaml(text, "t.yaml")
            check("yaml: rejects %s" % label, False, "parsed without error")
        except bmi.YamlSubsetError:
            check("yaml: rejects %s" % label, True)


# --------------------------------------------------------------------------
# 2. Schema-support guard
# --------------------------------------------------------------------------

def test_schema_support_guard():
    try:
        bmi.assert_schema_supported(SCHEMA)
        check("schema: the shipped schema uses only implemented keywords", True)
    except bmi.SchemaSupportError as exc:
        check("schema: the shipped schema uses only implemented keywords", False, str(exc))

    # An unimplemented keyword must fail even when it sits in a branch no
    # current record reaches — otherwise it would silently assert nothing.
    buried = {"type": "object",
              "properties": {"x": {"properties": {"y": {"oneOf": [{"type": "string"}]}}}}}
    try:
        bmi.assert_schema_supported(buried)
        check("schema: rejects an unimplemented keyword in an unreached branch", False)
    except bmi.SchemaSupportError:
        check("schema: rejects an unimplemented keyword in an unreached branch", True)

    try:
        bmi.assert_schema_supported({"type": "string", "format": "email"})
        check("schema: rejects an unimplemented format", False)
    except bmi.SchemaSupportError:
        check("schema: rejects an unimplemented format", True)


# --------------------------------------------------------------------------
# 3. Registry validation
# --------------------------------------------------------------------------

def record(**over):
    base = {
        "path": "some/where.md",
        "type": "scoped_rule",
        "owner": "workspace",
        "scope": "workspace",
        "visibility": "public",
        "canonicality": "canonical",
        "rationale": "A rationale long enough to say what failure this prevents.",
        "introduced": "2026-01-01",
        "provenance": [{"kind": "workspace_decision", "reference": "a reference"}],
        "load_mode": "path_triggered",
        "consumers": ["claude-code"],
        "risk": "low",
        "review": {"cadence": "quarterly", "method": ["semantic"], "last_reviewed": None},
        "success_signals": ["An observable signal that it earns its place."],
        "retirement_triggers": ["A concrete condition that would retire it."],
        "remediation_policy": "propose_patch",
        "related": [],
    }
    base.update(copy.deepcopy(over))
    return base


def run(public_artifacts, defaults=None, overlay=None, show_private=False, version=1):
    regs = [bmi.Registry({"version": version, "defaults": defaults or {},
                          "artifacts": public_artifacts},
                         "MEMORY-INVENTORY.yaml", private=False)]
    if overlay is not None:
        regs.append(bmi.Registry({"version": version, "artifacts": overlay},
                                 "c4po/.private/memory-inventory.yaml", private=True))
    return bmi.validate_registries(regs, SCHEMA, TODAY, show_private)


def test_accepts_valid():
    errs = run({"good-rule": record()})
    check("valid: a well-formed record is accepted", errs == [], "; ".join(errs))

    # A generated bridge plus its canonical source, the shape the design needs
    # most: two records, one reviewed semantically and one for drift only.
    errs = run({
        "canonical-rule": record(related=["derived-bridge"]),
        "derived-bridge": record(
            path="a/SKILL.md", type="generated_rule_bridge", canonicality="generated",
            canonical_ref="canonical-rule", load_mode="explicit", consumers=["codex"],
            review={"cadence": "each_audit", "method": ["drift_only"], "last_reviewed": None},
            remediation_policy="auto_safe", related=["canonical-rule"]),
    })
    check("valid: a canonical/generated pair is accepted", errs == [], "; ".join(errs))


def test_rejects_malformed():
    cases = [
        ("missing a required field",
         lambda: run({"rec-one": {k: v for k, v in record().items() if k != "rationale"}}),
         "missing required field 'rationale'"),
        ("an unknown field",
         lambda: run({"rec-one": record(colour="blue")}),
         "unknown field 'colour'"),
        ("a value outside an enum",
         lambda: run({"rec-one": record(type="sticky_note")}),
         "is not one of"),
        ("a rationale too short to be a rationale",
         lambda: run({"rec-one": record(rationale="tidy")}),
         "shorter than"),
        ("an empty provenance list",
         lambda: run({"rec-one": record(provenance=[])}),
         "at least 1 item"),
        ("an empty review.method list",
         lambda: run({"rec-one": record(review={"cadence": "quarterly", "method": [],
                                          "last_reviewed": None})}),
         "at least 1 item"),
        ("a cadence that is neither a named interval nor an on_ trigger",
         lambda: run({"rec-one": record(review={"cadence": "whenever", "method": ["semantic"],
                                          "last_reviewed": None})}),
         "matched none of the allowed forms"),
        ("an impossible calendar date",
         lambda: run({"rec-one": record(introduced="2026-02-30")}),
         "not a YYYY-MM-DD calendar date"),
        ("a date in the future",
         lambda: run({"rec-one": record(introduced="2027-01-01")}),
         "in the future"),
        ("a review that predates the artifact",
         lambda: run({"rec-one": record(review={"cadence": "quarterly", "method": ["semantic"],
                                          "last_reviewed": "2025-06-01"})}),
         "precedes `introduced`"),
        ("an id that disagrees with its map key",
         lambda: run({"rec-one": record(id="something-else")}),
         "the key is the id"),
        ("a malformed artifact id",
         lambda: run({"Not_An_Id": record()}),
         "invalid property name"),
        ("two records claiming one path",
         lambda: run({"rec-one": record(), "rec-two": record()}),
         "already claimed by"),
        ("a generated artifact with no canonical_ref",
         lambda: run({"rec-one": record(canonicality="generated")}),
         "requires `canonical_ref`"),
        ("a canonical artifact carrying a canonical_ref",
         lambda: run({"rec-one": record(canonical_ref="rec-two"), "rec-two": record(path="o.md")}),
         "only meaningful for generated or mirror"),
        ("a canonical_ref that does not resolve",
         lambda: run({"rec-one": record(canonicality="mirror", canonical_ref="ghost")}),
         "does not resolve"),
        ("a related id that does not resolve",
         lambda: run({"rec-one": record(related=["ghost"])}),
         "does not resolve"),
        ("a record related to itself",
         lambda: run({"rec-one": record(related=["rec-one"])}),
         "lists itself"),
        ("a bridge type declared canonical",
         lambda: run({"rec-one": record(type="generated_rule_bridge", canonicality="canonical")}),
         "must have canonicality"),
        ("a raw source declared canonical",
         lambda: run({"rec-one": record(type="knowledge_source", canonicality="canonical",
                                  load_mode="source_only")}),
         "must have canonicality"),
        ("a Cerebruh page the audit could edit unattended",
         lambda: run({"rec-one": record(type="knowledge_page", load_mode="retrieved",
                                  remediation_policy="auto_safe")}),
         "read-only from"),
        ("a private record in the tracked registry",
         lambda: run({"rec-one": record(visibility="private")}),
         "belongs in a gitignored"),
        ("a public record in a private overlay",
         lambda: run({"public-filler": record()},
                     overlay={"priv-one": record(path="priv.md")}, show_private=True),
         "must be `private` or `redacted`"),
        ("private_memory declared public",
         lambda: run({"rec-one": record(type="private_memory", visibility="public")}),
         "requires visibility private or redacted"),
        ("a defaults key that is not an artifact type",
         lambda: run({"rec-one": record()}, defaults={"sticky_note": {"risk": "low"}}),
         "invalid property name"),
        ("a defaults block with an undefaultable field",
         lambda: run({"rec-one": record()}, defaults={"scoped_rule": {"rationale": "nope"}}),
         "unknown field 'rationale'"),
        ("a wrong registry version",
         lambda: run({"rec-one": record()}, version=2),
         "expected the constant"),
    ]
    for label, thunk, expected in cases:
        errs = thunk()
        hit = any(expected in e for e in errs)
        check("rejects %s" % label, hit,
              "expected %r among: %s" % (expected, "; ".join(errs) or "(no errors)"))

    # A tracked record must not be able to name a private one, or the public
    # file would disclose that a private artifact exists.
    errs = run({"rec-one": record(related=["priv-one"])},
               overlay={"priv-one": record(path="p.md", visibility="private")},
               show_private=True)
    check("rejects a tracked record referencing a private overlay id",
          any("points into a private overlay" in e for e in errs),
          "; ".join(errs))

    # Same id declared in both files is a duplicate, not a merge.
    errs = run({"dup-id": record()},
               overlay={"dup-id": record(path="p.md", visibility="private")},
               show_private=True)
    check("rejects the same id in both the registry and an overlay",
          any("duplicate artifact id" in e for e in errs), "; ".join(errs))


def test_overlay_accepts_private_and_redacted():
    for vis in ("private", "redacted"):
        errs = run({"public-filler": record()},
                   overlay={"priv-one": record(path="p.md", type="private_memory",
                                               visibility=vis, load_mode="explicit")},
                   show_private=True)
        check("overlay: accepts a %s private_memory record" % vis, errs == [], "; ".join(errs))

    # An overlay with no records at all is fine; the tracked registry needs one.
    errs = run({"public-filler": record()}, overlay={}, show_private=True)
    check("overlay: an empty overlay is valid", errs == [], "; ".join(errs))
    errs = run({}, overlay={"priv-one": record(path="p.md", visibility="private")},
               show_private=True)
    check("overlay: an empty tracked registry is not valid",
          any("at least 1 propert" in e for e in errs), "; ".join(errs))


def test_defaults_merge():
    thin = {k: v for k, v in record().items()
            if k not in ("risk", "remediation_policy")}
    # cadence and method come from the class default; last_reviewed never can,
    # because it is per-artifact review history rather than class policy.
    thin["review"] = {"last_reviewed": None}
    defaults = {"scoped_rule": {"risk": "high", "remediation_policy": "approval_required",
                                "review_cadence": "quarterly", "review_method": ["semantic"]}}
    errs = run({"rec-one": thin}, defaults=defaults)
    check("defaults: fill fields the record omits", errs == [], "; ".join(errs))

    merged = bmi.apply_defaults(thin, defaults)
    check("defaults: land in the right place",
          merged["risk"] == "high" and merged["review"]["cadence"] == "quarterly",
          repr(merged.get("review")))

    # A record always wins over its class default.
    merged = bmi.apply_defaults(record(risk="critical"), defaults)
    check("defaults: never override a value the record states", merged["risk"] == "critical")

    # A default for a different class must not leak across.
    merged = bmi.apply_defaults(thin, {"knowledge_page": {"risk": "low"}})
    check("defaults: do not apply across artifact classes", "risk" not in merged)

    # Without the default, the same thin record is incomplete — proving the
    # merge is doing real work rather than the schema being lax.
    errs = run({"rec-one": thin})
    check("defaults: a record that relies on a missing default is rejected",
          any("missing required field 'risk'" in e for e in errs), "; ".join(errs))


def test_private_redaction():
    secret_id = "operation-nightingale"
    secret_path = "sensitive/dir/plans.md"
    bad = record(path=secret_path, visibility="private", type="not_a_type")
    errs = run({"public-filler": record()}, overlay={secret_id: bad}, show_private=False)
    leaked = [e for e in errs if secret_id in e or secret_path in e]
    check("private: ids and paths are redacted by default",
          errs and not leaked,
          "leaked: %s" % "; ".join(leaked))

    errs = run({"public-filler": record()}, overlay={secret_id: bad}, show_private=True)
    check("private: --show-private opts back in to full detail",
          any(secret_id in e for e in errs), "; ".join(errs))


# --------------------------------------------------------------------------
# 4. End-to-end through the CLI
# --------------------------------------------------------------------------

def cli(*args):
    proc = subprocess.run([sys.executable, TOOL] + list(args),
                          capture_output=True, text=True, cwd=ROOT)
    return proc.returncode, proc.stdout + proc.stderr


def test_cli():
    # No --today here, unlike the synthetic registries below. Since the step-3
    # bootstrap, this repo's records carry `introduced` dates derived from git
    # and the filesystem, and the newest advances every time an artifact is
    # added — a pinned date would start failing on its own the next time someone
    # writes a rule. The real check is that the registry is valid TODAY.
    code, out = cli("validate")
    check("cli: this repo's registry validates clean", code == 0, out.strip())

    overlay = os.path.join(ROOT, "c4po/.private.example/memory-inventory.example.yaml")
    code, out = cli("validate", "--overlay", overlay)
    check("cli: the synthetic private overlay validates clean", code == 0, out.strip())
    check("cli: it is counted as private, not public", "2 private record" in out, out.strip())
    check("cli: and the example covers both a reviewed record and a draft stub",
          bmi.status_counts([bmi.Registry(bmi.load_yaml(open(overlay, encoding="utf-8").read(),
                                                        overlay), overlay, private=True)])
          == (0, 0, 1, 1), out.strip())

    with tempfile.TemporaryDirectory() as tmp:
        broken = os.path.join(tmp, "broken.yaml")
        with open(broken, "w", encoding="utf-8") as fh:
            fh.write("version: 1\nartifacts:\n  r:\n    path: a.md\n    type: scoped_rule\n")
        code, out = cli("validate", "--registry", broken, "--today", "2026-08-26")
        check("cli: a malformed registry exits 1", code == 1, "exit %d: %s" % (code, out.strip()))
        check("cli: and names the missing fields", "missing required field" in out, out.strip())

        unparseable = os.path.join(tmp, "tabs.yaml")
        with open(unparseable, "w", encoding="utf-8") as fh:
            fh.write("version: 1\nartifacts:\n\tr: 1\n")
        code, out = cli("validate", "--registry", unparseable, "--today", "2026-08-26")
        check("cli: an unparseable registry exits 1 rather than passing", code == 1,
              "exit %d: %s" % (code, out.strip()))

        missing = os.path.join(tmp, "absent.yaml")
        code, out = cli("validate", "--registry", missing)
        check("cli: a missing registry is a usage error, not an invalid one", code == 2,
              "exit %d: %s" % (code, out.strip()))




# --------------------------------------------------------------------------
# 9. Discovery (migration step 2)
# --------------------------------------------------------------------------
#
# Built against a synthetic tree rather than the live workspace so the expected
# classification is exact and stays stable as The Borg grows. A separate smoke
# test below runs discovery over the real workspace for the properties that must
# hold there no matter what it currently contains.

FIXTURE_FILES = {
    # Always-on instructions and their wrappers.
    "AGENTS.md": "# root\n",
    "CLAUDE.md": "@AGENTS.md\n",
    "agentx/AGENTS.md": "# agentx\n",
    "agentx/CLAUDE.md": "@AGENTS.md\n",
    "cerebruh/template/AGENTS.md": "# template\n",
    "cerebruh/template/CLAUDE.md": "@AGENTS.md\n",

    # Policy, design, and the registry that governs this inventory.
    "LINT.md": "# lint\n",
    "agentx/MCP.md": "# mcp\n",
    "MEMORY-INVENTORY.yaml": "version: 1\nartifacts:\n",
    "MEMORY-INVENTORY.schema.json": "{}\n",
    "SOMETHING-DESIGN.md": "# design\n",

    # Deliberately not memory.
    "BACKLOG.md": "- item\n",
    ".gitignore": "x\n",
    ".claude/settings.local.json": "{}\n",

    # Rules and their generated Codex bridges, including the gitignored pair.
    ".claude/rules/alpha.md": "---\nname: alpha\n---\n",
    ".claude/rules/beta.local.md": "---\nname: beta\n---\n",
    ".agents/skills/alpha/SKILL.md": "stub\n",
    ".agents/skills/beta.local/SKILL.md": "stub\n",
    ".agents/skills/gone/SKILL.md": "stub\n",          # canonical rule deleted

    # Commands, skills, scheduled prompts, and their companions.
    ".claude/commands/doit.md": "# doit\n",
    "agentx/.claude/skills/pack/SKILL.md": "# pack\n",
    "agentx/.claude/skills/pack/reference.md": "# ref\n",
    "agentx/.claude/skills/pack/helper.sh": "#!/bin/sh\n",
    "agentx/.claude/skills/pack/.DS_Store": "noise\n",
    "agentx/.claude/scheduled/job.prompt": "do the thing\n",
    "agentx/.claude/scheduled/job.settings.json": "{}\n",
    "agentx/.claude/scheduled/logs/run.log": "noise\n",
    "agentx/.claude/scheduled/state/job.json": "{}\n",

    # Private: notes, wrappers, the overlay, and domain documents.
    "agentx/CLAUDE.local.md": "@.private/AGENTS.md\n",
    "agentx/.private/AGENTS.md": "# private\n",
    "agentx/.private/CLAUDE.md": "@AGENTS.md\n",
    "agentx/.private/note.md": "# note\n",
    "agentx/.private/contract.docx": "binary-ish\n",
    "agentx/.private/scheduled-tasks/jobs.tasks": "table\n",
    "agentx/.private/memory-inventory.yaml": "version: 1\nartifacts:\n",
    "agentx/.private.example/AGENTS.example.md": "# synthetic\n",

    # Cerebruh.
    "cerebruh/wikis/index.md": "# index\n",
    "cerebruh/wikis/w1/CLAUDE.md": "@AGENTS.md\n",
    "cerebruh/wikis/w1/wiki/index.md": "# w1 index\n",
    "cerebruh/wikis/w1/wiki/page.md": "# page\n",
    "cerebruh/wikis/w1/raw/Source.pdf": "%PDF-fake\n",
    "cerebruh/wikis/w1/raw/.DS_Store": "noise\n",
    "cerebruh/ingest/pending.md": "# not yet knowledge\n",

    # Excluded subtrees.
    "bernard/AGENTS.md": "# exhibit\n",
    "repos/thing/AGENTS.md": "# other repo\n",
    "repos/thing/.claude/commands/other.md": "# other\n",
    "tmp/scratch.md": "# scratch\n",
}

# path -> (type, canonicality, visibility)
EXPECTED = {
    "AGENTS.md": ("always_on_instruction", "canonical", "public"),
    "CLAUDE.md": ("compatibility_wrapper", "mirror", "public"),
    "agentx/AGENTS.md": ("always_on_instruction", "canonical", "public"),
    "agentx/CLAUDE.md": ("compatibility_wrapper", "mirror", "public"),
    "cerebruh/template/AGENTS.md": ("always_on_instruction", "canonical", "public"),
    "cerebruh/template/CLAUDE.md": ("compatibility_wrapper", "mirror", "public"),
    "LINT.md": ("policy_registry", "canonical", "public"),
    "agentx/MCP.md": ("policy_registry", "canonical", "public"),
    "MEMORY-INVENTORY.yaml": ("policy_registry", "canonical", "public"),
    "MEMORY-INVENTORY.schema.json": ("policy_registry", "canonical", "public"),
    "SOMETHING-DESIGN.md": ("design_decision", "canonical", "public"),
    ".claude/rules/alpha.md": ("scoped_rule", "canonical", "public"),
    ".claude/rules/beta.local.md": ("scoped_rule", "canonical", "private"),
    ".agents/skills/alpha/SKILL.md": ("generated_rule_bridge", "generated", "public"),
    ".agents/skills/beta.local/SKILL.md": ("generated_rule_bridge", "generated", "private"),
    ".agents/skills/gone/SKILL.md": ("generated_rule_bridge", "generated", "public"),
    ".claude/commands/doit.md": ("command", "canonical", "public"),
    "agentx/.claude/skills/pack/SKILL.md": ("procedural_skill", "canonical", "public"),
    "agentx/.claude/scheduled/job.prompt": ("scheduled_prompt", "canonical", "public"),
    "agentx/CLAUDE.local.md": ("compatibility_wrapper", "mirror", "private"),
    "agentx/.private/AGENTS.md": ("always_on_instruction", "canonical", "private"),
    "agentx/.private/CLAUDE.md": ("compatibility_wrapper", "mirror", "private"),
    "agentx/.private/note.md": ("private_memory", "canonical", "private"),
    "cerebruh/wikis/index.md": ("retrieval_index", "canonical", "public"),
    "cerebruh/wikis/w1/AGENTS.md": ("compatibility_wrapper", "mirror", "public"),
    "cerebruh/wikis/w1/CLAUDE.md": ("compatibility_wrapper", "mirror", "public"),
    "cerebruh/wikis/w1/wiki/index.md": ("retrieval_index", "canonical", "public"),
    "cerebruh/wikis/w1/wiki/page.md": ("knowledge_page", "canonical", "public"),
    "cerebruh/wikis/w1/raw/Source.pdf": ("knowledge_source", "source", "public"),
}


def build_fixture(base):
    """Materialize the synthetic workspace, a CODEX_HOME, and a HOME."""
    root = os.path.join(base, "borg")
    for rel, body in FIXTURE_FILES.items():
        target = os.path.join(root, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(body)

    # A sub-wiki AGENTS.md is a symlink to the canonical template, and a
    # directory symlink points back into the tree the way repos/waiq's
    # .claude/commands does.
    os.symlink("../../template/AGENTS.md", os.path.join(root, "cerebruh/wikis/w1/AGENTS.md"))
    os.symlink("../../.claude/commands", os.path.join(root, "agentx/.claude/borrowed"))

    codex_home = os.path.join(base, "codex")
    os.makedirs(os.path.join(codex_home, "skills"), exist_ok=True)
    with open(os.path.join(codex_home, "skills/.theborg-managed-skills.tsv"), "w",
              encoding="utf-8") as fh:
        fh.write("doit\t%s\tdeadbeef\n" % os.path.join(root, ".claude/commands/doit.md"))
        fh.write("orphan\t/somewhere/else/cmd.md\tcafe\n")

    home = os.path.join(base, "home")
    slug = os.path.abspath(root).replace("/", "-")
    memdir = os.path.join(home, ".claude/projects", slug, "memory")
    os.makedirs(memdir, exist_ok=True)
    for name in ("MEMORY.md", "topic.md"):
        with open(os.path.join(memdir, name), "w", encoding="utf-8") as fh:
            fh.write("# %s\n" % name)
    return root, codex_home, home


def _tree_state(root):
    """Every file's size, mtime, and bytes — the read-only proof."""
    state = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in filenames:
            full = os.path.join(dirpath, name)
            st = os.lstat(full)
            body = b"" if os.path.islink(full) else open(full, "rb").read()
            state[os.path.relpath(full, root)] = (st.st_size, st.st_mtime_ns, body)
        for name in dirnames:
            state.setdefault("dir:" + os.path.relpath(os.path.join(dirpath, name), root), None)
    return state


def test_discovery_classification():
    with tempfile.TemporaryDirectory() as base:
        root, codex_home, home = build_fixture(base)
        result = bmi.discover(root, codex_home=codex_home, home=home)

        workspace = {a["path"]: (a["type"], a["canonicality"], a["visibility"])
                     for a in result["artifacts"] if a["path_root"] == "borg_root"}
        check("discover: classifies every taxonomy shape exactly",
              workspace == EXPECTED,
              "missing=%r unexpected=%r wrong=%r" % (
                  sorted(set(EXPECTED) - set(workspace)),
                  sorted(set(workspace) - set(EXPECTED)),
                  sorted(k for k in set(EXPECTED) & set(workspace)
                         if EXPECTED[k] != workspace[k])))

        excluded = dict(result["excluded"])
        for name in ("bernard", "repos", "tmp", "cerebruh/ingest",
                     "agentx/.private.example",
                     "agentx/.claude/scheduled/logs", "agentx/.claude/scheduled/state"):
            check("discover: excludes %s with a stated reason" % name,
                  name in excluded and bool(excluded[name]), sorted(excluded))
        check("discover: does not follow a directory symlink back into the tree",
              "agentx/.claude/borrowed" in excluded
              and not any(a["path"].startswith("agentx/.claude/borrowed")
                          for a in result["artifacts"]),
              sorted(excluded))

        skipped = dict(result["skipped"])
        for name, why in (("BACKLOG.md", "work queue"),
                          (".gitignore", "repository configuration"),
                          (".claude/settings.local.json", "harness configuration"),
                          ("agentx/.private/contract.docx", "domain document"),
                          ("agentx/.private/scheduled-tasks/jobs.tasks", "registration table"),
                          ("cerebruh/wikis/w1/raw/.DS_Store", "OS noise")):
            check("discover: skips %s" % name, name in skipped, sorted(skipped))
        check("discover: a raw/ capture is a source despite its format, "
              "but OS noise beside it is not",
              "cerebruh/wikis/w1/raw/Source.pdf" in workspace
              and "cerebruh/wikis/w1/raw/.DS_Store" in skipped)

        check("discover: nothing in a memory-bearing location is left unclassified",
              result["unclassified"] == [], result["unclassified"])
        check("discover: the private overlay is counted apart from the artifacts",
              result["overlays"] == ["agentx/.private/memory-inventory.yaml"]
              and "agentx/.private/memory-inventory.yaml" not in workspace,
              result["overlays"])


def test_discovery_pairs_and_companions():
    with tempfile.TemporaryDirectory() as base:
        root, codex_home, home = build_fixture(base)
        result = bmi.discover(root, codex_home=codex_home, home=home)
        by_path = {(a["path_root"], a["path"]): a for a in result["artifacts"]}

        pairs = [
            (".agents/skills/alpha/SKILL.md", ".claude/rules/alpha.md"),
            (".agents/skills/beta.local/SKILL.md", ".claude/rules/beta.local.md"),
            ("CLAUDE.md", "AGENTS.md"),
            ("agentx/CLAUDE.local.md", "agentx/.private/AGENTS.md"),
            ("cerebruh/wikis/w1/AGENTS.md", "cerebruh/template/AGENTS.md"),
            ("cerebruh/wikis/w1/CLAUDE.md", "cerebruh/wikis/w1/AGENTS.md"),
        ]
        for derived, canonical in pairs:
            record = by_path[("borg_root", derived)]
            check("discover: %s resolves to %s" % (derived, canonical),
                  record["canonical_path"] == canonical and record["canonical_resolved"],
                  "got %r resolved=%r" % (record["canonical_path"],
                                          record.get("canonical_resolved")))

        dangling = sorted(d[1] for d in result["pairs"]["dangling"])
        check("discover: a bridge with no canonical source is reported, not resolved",
              dangling == [".agents/skills/gone/SKILL.md", "skills/orphan/SKILL.md"],
              dangling)

        prompt = by_path[("borg_root", "agentx/.claude/scheduled/job.prompt")]
        check("discover: a prompt's configuration is folded into the prompt",
              prompt["companions"] == ["agentx/.claude/scheduled/job.settings.json"],
              prompt["companions"])
        pack = by_path[("borg_root", "agentx/.claude/skills/pack/SKILL.md")]
        # The helper script is the point: a bare `.sh` anywhere else is skipped
        # as code, but inside a skill package it is part of the audit unit.
        check("discover: a skill package's supporting files stay in the package",
              pack["companions"] == ["agentx/.claude/skills/pack/helper.sh",
                                     "agentx/.claude/skills/pack/reference.md"],
              pack["companions"])
        check("discover: OS noise inside a package is still noise",
              ("agentx/.claude/skills/pack/.DS_Store", "OS noise")
              in result["skipped"], result["skipped"])

        bridge = by_path[("codex_home", "skills/doit/SKILL.md")]
        check("discover: the Codex command bridge is read from its manifest",
              bridge["type"] == "generated_command_bridge"
              and bridge["canonical_path"] == ".claude/commands/doit.md"
              and bridge["canonical_resolved"], bridge)
        orphan = by_path[("codex_home", "skills/orphan/SKILL.md")]
        check("discover: a managed skill sourced outside the workspace does not resolve",
              orphan["canonical_path"] is None and not orphan["canonical_resolved"], orphan)

        memory = sorted(a["path"] for a in result["artifacts"] if a["path_root"] == "home")
        check("discover: Auto Memory is found under the computed project slug",
              len(memory) == 2 and memory[0].endswith("/MEMORY.md")
              and all(a["visibility"] == "private" and a["type"] == "private_memory"
                      for a in result["artifacts"] if a["path_root"] == "home"),
              memory)


def test_discovery_is_read_only():
    with tempfile.TemporaryDirectory() as base:
        root, codex_home, home = build_fixture(base)
        before = _tree_state(root)
        result = bmi.discover(root, codex_home=codex_home, home=home)
        join = bmi.join_registry(result["artifacts"], [])
        bmi.format_report(result, join, show_private=True)
        json.dumps(bmi._public_json(result, join, show_private=True))
        after = _tree_state(root)
        check("discover: mutates nothing it discovers", before == after,
              "changed: %r" % sorted(set(before) ^ set(after)
                                     | {k for k in set(before) & set(after)
                                        if before[k] != after[k]}))


def test_discovery_withholds_private_paths():
    with tempfile.TemporaryDirectory() as base:
        root, codex_home, home = build_fixture(base)
        result = bmi.discover(root, codex_home=codex_home, home=home)
        join = bmi.join_registry(result["artifacts"], [])

        report = bmi.format_report(result, join, show_private=False)
        blob = json.dumps(bmi._public_json(result, join, show_private=False))
        for surface, text in (("report", report), ("json", blob)):
            leaks = [line for line in text.replace(",", "\n").splitlines()
                     if ".private/" in line or "CLAUDE.local.md" in line
                     or "beta.local" in line or "/memory/" in line]
            check("discover: the %s names no private path by default" % surface,
                  not leaks, leaks[:3])

        counts = {d["type"]: d["count"]
                  for d in bmi._public_json(result, join, False)["private_counts_by_type"]}
        check("discover: private artifacts survive as redacted counts by type",
              counts.get("private_memory") == 3 and counts.get("scoped_rule") == 1,
              counts)

        # The report is totals and findings; the per-artifact surface is JSON,
        # which is where --show-private has anything to reveal.
        shown = json.dumps(bmi._public_json(result, join, show_private=True))
        check("discover: --show-private does name them",
              "agentx/.private/note.md" in shown and '"private_counts_by_type": []' in shown,
              shown[:200])


def test_discovery_cli():
    with tempfile.TemporaryDirectory() as base:
        root, codex_home, home = build_fixture(base)
        args = ["discover", "--root", root, "--codex-home", codex_home, "--home", home]

        code, out = cli(*args)
        check("cli: discovery over a fully unregistered tree still exits 0",
              code == 0, "exit %d: %s" % (code, out.strip()))
        check("cli: and says coverage is measured rather than enforced",
              "not enforced" in out, out.strip())

        code, out = cli(*(args + ["--json"]))
        check("cli: --json is parseable", code == 0, out.strip())
        payload = json.loads(out)
        check("cli: the JSON view declares itself read-only and unenforced",
              payload["read_only"] is True and payload["coverage_enforced"] is False,
              payload.get("read_only"))
        check("cli: every discovered type is a schema-valid artifact type",
              set(a["type"] for a in payload["artifacts"])
              <= set(SCHEMA["$defs"]["artifactType"]["enum"]),
              sorted(set(a["type"] for a in payload["artifacts"])))
        # EXPECTED plus the two manifest-declared Codex bridges and the two
        # Auto Memory files, none of which the empty fixture registry declares.
        check("cli: coverage counts the unregistered without failing",
              payload["coverage"]["registered"] == 0
              and payload["coverage"]["unregistered"] == len(EXPECTED) + 4,
              payload["coverage"])


def test_discovery_over_this_workspace():
    """Properties that must hold for the live workspace whatever it contains."""
    code, out = cli("discover")
    check("cli: discovery runs clean over this workspace", code == 0, out.strip()[:400])
    check("cli: and leaks no private path into the default report",
          ".private/" not in out and "/memory/MEMORY.md" not in out, out.strip()[:400])

    code, out = cli("discover", "--json")
    check("cli: this workspace's discovery emits parseable JSON", code == 0, out.strip()[:400])
    payload = json.loads(out)
    types = SCHEMA["$defs"]["artifactType"]["enum"]
    found = set(a["type"] for a in payload["artifacts"])
    check("cli: every type it reports is in the taxonomy", found <= set(types), sorted(found))
    for required in ("always_on_instruction", "compatibility_wrapper", "scoped_rule",
                     "generated_rule_bridge", "command", "generated_command_bridge",
                     "scheduled_prompt", "knowledge_page", "knowledge_source",
                     "policy_registry", "retrieval_index", "procedural_skill",
                     "design_decision"):
        check("cli: this workspace's %s artifacts are discovered" % required,
              required in found, sorted(found))
    check("cli: every record declared in MEMORY-INVENTORY.yaml is found on disk",
          payload["coverage"]["missing"] == 0, payload["coverage"])
    check("cli: every generated bridge and mirror resolves to its canonical source",
          payload["pairs"]["unresolved"] == 0, payload["pairs"])


# --------------------------------------------------------------------------
# 10. Draft status and mechanical bootstrap (migration step 3)
# --------------------------------------------------------------------------
#
# The point of step 3 is a distinction that has to be machine-checkable: a
# record can be REGISTERED without being REVIEWED. These tests pin both halves —
# the validator's split requirements, and the bootstrap that produces the stubs.

SCHEMA_PATH = os.path.join(ROOT, "MEMORY-INVENTORY.schema.json")


def draft(**over):
    """A record holding only what a mechanical bootstrap can derive."""
    base = {k: v for k, v in record().items() if k not in bmi.HUMAN_JUDGMENT_FIELDS}
    base["status"] = "draft"
    base.update(copy.deepcopy(over))
    return base


def test_draft_status():
    errs = run({"stub": draft()})
    check("draft: a stub with no human judgment fields is accepted",
          errs == [], "; ".join(errs))

    bare = {k: v for k, v in draft().items() if k != "status"}
    errs = run({"stub": bare})
    check("draft: omitting `status` does not relax anything — strict is the default",
          any("missing required field 'rationale'" in e for e in errs), "; ".join(errs))

    errs = run({"stub": draft(status="reviewed")})
    check("draft: `status: reviewed` demands the full record",
          any("missing required field 'rationale'" in e for e in errs), "; ".join(errs))

    errs = run({"stub": draft(review={"cadence": "quarterly", "method": ["semantic"],
                                      "last_reviewed": "2026-01-02"})})
    check("draft: a stub may not claim a review date",
          any("cannot carry `review.last_reviewed" in e for e in errs), "; ".join(errs))

    errs = run({"stub": draft(
        rationale="A rationale long enough to say what failure this prevents.",
        retirement_triggers=["A concrete condition that would retire it."],
        remediation_policy="propose_patch")})
    check("draft: a stub that has cleared the promotion gate must be promoted",
          any("no longer a stub" in e for e in errs), "; ".join(errs))

    errs = run({"stub": draft()}, defaults={"scoped_rule": {"status": "draft"}})
    check("draft: `status` cannot be set as a class default",
          any("unknown field 'status'" in e for e in errs), "; ".join(errs))

    regs = [bmi.Registry({"version": 1, "artifacts": {"a": draft(), "b": record()}},
                         "MEMORY-INVENTORY.yaml", private=False),
            bmi.Registry({"version": 1, "artifacts": {"c": draft(visibility="private")}},
                         "x/.private/memory-inventory.yaml", private=True)]
    check("draft: public and private, reviewed and draft are counted apart",
          bmi.status_counts(regs) == (1, 1, 0, 1), bmi.status_counts(regs))


def test_emitter_round_trips():
    r = draft(path="agentx/a path/with spaces.md",
              consumers=["claude-code", "codex", "claude-desktop"],
              review={"cadence": "monthly", "method": ["semantic", "best_practice"],
                      "last_reviewed": None},
              related=[])
    r["_comments"] = {"introduced": "first git add"}
    text = "version: 1\n\nartifacts:\n" + "\n".join(bmi.emit_record("some-id", r)) + "\n"
    parsed = bmi.load_yaml(text, "emitted")
    got = parsed["artifacts"]["some-id"]
    check("emit: a record round-trips through this tool's own reader",
          got == bmi.strip_comments(r), got)
    check("emit: a list nested inside `review` survives as a list",
          got["review"]["method"] == ["semantic", "best_practice"], got.get("review"))
    check("emit: a path with spaces survives", got["path"] == r["path"], got.get("path"))
    check("emit: an empty list stays a list", got["related"] == [], got.get("related"))
    check("emit: a trailing comment is a comment, not part of the value",
          got["introduced"] == r["introduced"], got.get("introduced"))
    bmi.verify_roundtrip(text, [("some-id", r)], "emitted")

    for name, bad in (
            ("a list of mappings",
             draft(provenance=[{"kind": "workspace_decision", "reference": "r"}])),
            ("a field missing from the emission order", draft(colour="blue"))):
        try:
            bmi.emit_record("x", bad)
            check("emit: %s is refused, not stringified" % name, False, "no error raised")
        except bmi.YamlSubsetError:
            check("emit: %s is refused, not stringified" % name, True)


def _bootstrap(root, home, codex_home, *extra):
    return cli("bootstrap", "--root", root, "--home", home, "--codex-home", codex_home,
               "--schema", SCHEMA_PATH, "--today", "2026-09-02", *extra)


def test_bootstrap_over_fixture():
    with tempfile.TemporaryDirectory() as base:
        root, codex_home, home = build_fixture(base)

        before = _tree_state(root)
        code, out = _bootstrap(root, home, codex_home)
        check("bootstrap: a dry run exits 0", code == 0, out.strip()[:400])
        check("bootstrap: and writes nothing", _tree_state(root) == before,
              "the dry run mutated the tree")

        code, out = _bootstrap(root, home, codex_home, "--write")
        check("bootstrap: the write run exits 0", code == 0, out.strip()[:600])

        tracked = open(os.path.join(root, "MEMORY-INVENTORY.yaml"), encoding="utf-8").read()
        registry = bmi.load_yaml(tracked, "MEMORY-INVENTORY.yaml")["artifacts"]
        check("bootstrap: every emitted record is flagged `status: draft`",
              registry and all(r.get("status") == "draft" for r in registry.values()),
              sorted(k for k, r in registry.items() if r.get("status") != "draft"))

        # The hard requirement: no private path, in any form, in a tracked file.
        private_paths = [a["path"] for a in
                         bmi.discover(root, codex_home=codex_home, home=home)["artifacts"]
                         if a["visibility"] != "public"]
        check("bootstrap: private artifacts exist in the fixture to be misplaced",
              len(private_paths) >= 4, private_paths)
        leaked = [p for p in private_paths if p in tracked]
        check("bootstrap: no private path reaches the tracked registry", leaked == [], leaked)
        check("bootstrap: and no private directory is named there",
              ".private/" not in tracked and ".local.md" not in tracked,
              [l for l in tracked.splitlines() if ".private/" in l or ".local.md" in l])
        check("bootstrap: the default report withholds the overlay paths",
              ".private/" not in out, [l for l in out.splitlines() if ".private/" in l])

        overlay = os.path.join(root, "agentx/.private/memory-inventory.yaml")
        body = open(overlay, encoding="utf-8").read()
        check("bootstrap: the agent's private records land in its overlay",
              all(p in body for p in private_paths if p.startswith("agentx/")),
              [p for p in private_paths if p.startswith("agentx/") and p not in body])
        check("bootstrap: an overlay it creates is owner-readable only",
              oct(os.stat(os.path.join(root, "c4po/.private/memory-inventory.yaml")).st_mode
                  & 0o777) == "0o600")

        # An orphaned bridge has no canonical source to point at, so no valid
        # record exists for it. It must be named and left uncovered, not guessed.
        check("bootstrap: an orphaned bridge is deferred, with a reason",
              "Deferred" in out and ".agents/skills/gone/SKILL.md" in out, out.strip()[:600])
        check("bootstrap: and never enters the registry",
              ".agents/skills/gone/SKILL.md" not in tracked)

        code, out = cli("validate", "--registry", os.path.join(root, "MEMORY-INVENTORY.yaml"),
                        "--schema", SCHEMA_PATH, "--overlay", overlay,
                        "--overlay", os.path.join(root, "c4po/.private/memory-inventory.yaml"),
                        "--today", "2026-09-02")
        check("bootstrap: the bootstrapped registry and overlays validate", code == 0,
              out.strip()[:600])
        check("bootstrap: and validate says how much of it is merely registered",
              "0 reviewed" in out and "draft" in out, out.strip()[:400])

        code, out = cli("validate", "--registry", os.path.join(root, "MEMORY-INVENTORY.yaml"),
                        "--schema", SCHEMA_PATH, "--overlay", overlay, "--today", "2026-09-02",
                        "--require-reviewed")
        check("bootstrap: --require-reviewed fails while any draft remains", code == 1,
              "exit %d: %s" % (code, out.strip()[:400]))

        code, out = cli("discover", "--root", root, "--home", home,
                        "--codex-home", codex_home, "--json")
        payload = json.loads(out)
        check("bootstrap: discovery now covers everything except the deferred orphans",
              payload["coverage"]["unregistered"] == 2, payload["coverage"])
        check("bootstrap: and finds no registered record without a file",
              payload["coverage"]["missing"] == 0, payload["coverage"])

        code, out = _bootstrap(root, home, codex_home, "--write")
        check("bootstrap: a second run is a no-op", "Nothing to bootstrap" in out,
              out.strip()[:400])


def test_bootstrap_over_this_workspace():
    """The live workspace, where the private/tracked split actually matters."""
    code, out = cli("bootstrap")
    check("cli: this workspace has nothing left to bootstrap",
          code == 0 and "Nothing to bootstrap" in out, out.strip()[:400])

    tracked = open(os.path.join(ROOT, "MEMORY-INVENTORY.yaml"), encoding="utf-8").read()
    code, discovered = cli("discover", "--json")
    payload = json.loads(discovered)
    check("cli: every artifact this workspace has is registered",
          payload["coverage"]["unregistered"] == 0, payload["coverage"])

    result = bmi.discover(ROOT, codex_home=os.environ.get("CODEX_HOME"),
                          home=os.path.expanduser("~"))
    private_paths = [a["path"] for a in result["artifacts"] if a["visibility"] != "public"]
    check("cli: this workspace has private artifacts to protect", private_paths != [],
          len(private_paths))
    check("cli: none of their paths appear in the tracked registry",
          [p for p in private_paths if p in tracked] == [],
          [p for p in private_paths if p in tracked])
    check("cli: nor does any absolute home path",
          os.path.expanduser("~") not in tracked)


# --------------------------------------------------------------------------

def main():
    for fn in (test_yaml_reader, test_schema_support_guard, test_accepts_valid,
               test_rejects_malformed, test_overlay_accepts_private_and_redacted,
               test_defaults_merge, test_private_redaction,
               test_cli,
               test_discovery_classification, test_discovery_pairs_and_companions,
               test_discovery_is_read_only, test_discovery_withholds_private_paths,
               test_discovery_cli, test_discovery_over_this_workspace,
               test_draft_status, test_emitter_round_trips,
               test_bootstrap_over_fixture, test_bootstrap_over_this_workspace):
        fn()

    failed = [r for r in _results if not r[1]]
    for name, ok, detail in _results:
        if not ok:
            print("FAIL  %s\n      %s" % (name, detail))
    print("\n%d/%d checks passed." % (len(_results) - len(failed), len(_results)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
