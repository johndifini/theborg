---
name: memory-inventory-authoring
description: "When creating, moving, or retiring a durable memory artifact: update its governance-registry record and every generated companion's record in the same change, then verify complete coverage."
paths:
  - "AGENTS.md"
  - "**/AGENTS.md"
  - "**/CLAUDE.md"
  - "**/.claude/rules/*.md"
  - "**/.claude/commands/*.md"
  - "**/.claude/skills/**"
  - "**/.claude/scheduled/*.prompt"
  - "cerebruh/wikis/**"
  - "MEMORY-INVENTORY*"
  - "**/*-DESIGN.md"
  - "**/MCP.md"
---
# Register durable memory in the change that creates it

The authoring session owns registration. The lint and assumptions audits are
backstops: they report missing records but do not add them.

For a new artifact:

1. Create the canonical artifact without inventing sensitive facts in a tracked
   file. Generate any required bridge first (`.bin/sync-codex-prompts.sh` for a
   command or `.bin/sync-codex-rule-skills.sh` for a rule), so discovery sees
   the complete canonical/generated pair.
2. From the workspace root, dry-run
   `python3 .bin/build-memory-inventory.py bootstrap --artifact <workspace-relative-path>`.
   Inspect the destinations, then repeat with `--write`. The scope includes the
   selected artifact and its canonical/generated companions; do not use the
   unscoped `bootstrap --write` for ordinary authoring in the shared checkout.
3. Inspect the exact registry diff. Mechanical records stay `status: draft`.
   Do not invent or copy the six semantic fields, and do not promote a draft to
   `reviewed`, without substantive review and explicit approval.

`--artifact` resolves only against `borg_root`. An artifact whose record carries
`path_root: home` (Auto Memory under `~/.claude/projects/`) or
`path_root: codex_home` (a generated skill under `~/.codex/`) cannot be named by
it in any form — workspace-relative, `$HOME`-absolute, `~`-prefixed and bare all
return `error: ... was not discovered as a durable memory artifact`. That is the
addressing limit, not a "nothing to do": an already-registered `borg_root`
artifact instead reports `Nothing to bootstrap`.

For those, the unscoped `bootstrap` is the only path, so substitute a dry run for
the missing scope: run it without `--write`, confirm the summary names exactly
the record count and destinations you intend, and re-run with `--write` in the
same turn. A sibling session creating an artifact between the two runs would
widen the write, which is what `--artifact` would otherwise have prevented.

For a move, preserve the stable record id and update its `path`; update paths and
relationships for generated companions after regenerating them. Do not create a
second record for the relocated artifact. For permanent retirement, remove the
canonical artifact and generated companions, then remove their registry records;
Git history retains the retired declaration. A missing artifact with a live
record is a violation, not an archive state.

Public artifacts belong in `MEMORY-INVENTORY.yaml`. If an artifact's path or
rationale is sensitive, its record belongs only in the owning agent's gitignored
`<owner>/.private/memory-inventory.yaml` overlay; never copy those facts into the
tracked registry.

## Do not leave a dated backup in a memory-bearing directory

A gitignored overlay has no git safety net, so copying it before a write is
sound — but `discover --require-coverage` reports the copy as `UNCLASSIFIED` and
exits 1. Only the **final** extension is consulted: `SKIPPED_PATTERNS` anchors
on end-of-name, so appending anything after a known extension stops the skip
from matching and the file becomes an unclassified candidate.

Measured in `c4po/.private/`, same contents in every case:

| Name | Coverage |
|---|---|
| `x.yaml`, `x.bak`, `x.yaml.bak`, `x.orig` | passes |
| `x.bak-20260914`, `x.tmp`, `x.yaml.save` | **fails, unclassified** |
| `x.bak-20260914.yaml` | passes — known extension is last |

The trap rewards the careful habit: `cp x x.bak` is fine, while making the
backup name unique with a timestamp breaks the gate. Put the stamp before the
extension (`x.bak-20260914.yaml`), or keep the copy out of the directory
entirely. Either way delete it once the write is verified — the gate is not
satisfied until it is gone.

Before considering the change complete, run the relevant bridge `--check`, then:

```sh
python3 .bin/build-memory-inventory.py validate
python3 .bin/build-memory-inventory.py discover --require-coverage
```

Both commands must exit zero. `validate --require-reviewed` is the separate
semantic-review gate and is not part of authoring-time registration.
