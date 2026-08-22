---
name: tracked-agent-files-are-public
description: "When writing an agent's .claude/scheduled/*.prompt or .claude/commands/*.md: those paths are tracked in a PUBLIC repo, so carry the method and cite the private facts by reference instead of inlining them."
paths:
  - "**/.claude/scheduled/*.prompt"
  - "**/.claude/commands/*.md"
---
# A scheduled prompt is public; the workpaper it reads is not

`<agent>/.claude/scheduled/` and `<agent>/.claude/commands/` are **tracked**,
and `johndifini/theborg` is **public**. `<agent>/.private/` is gitignored.
Those two facts sit one directory apart and are easy to conflate while writing
a job that is *about* private material.

On 2026-08-16 a new job under `norm/.claude/scheduled/` carried a spouse's
name, two employers, and a state into a local commit on the public repo.
Unwinding it took a five-commit history rewrite plus deleting the backup tag
that still pointed at the old commits. It was caught by a sibling session, not
by the session that wrote it.

**The split:** the tracked file carries the *method* — which forms, which
thresholds, which dates, which steps. The private *values* stay in
`<agent>/.private/` and the prompt cites them by section reference ("re-read §6
of the workpaper for the two form numbers").

Before saving any file under these paths:

- Name every person, employer, institution, city/state, account, and dollar
  figure in what you just wrote. If it identifies a real party, move it to
  `.private/` and cite it instead.
- `git check-ignore -v <path>` — if it prints nothing, the file is going
  public. There is no in-between.
- Verify the citation you substituted actually resolves. On 2026-08-16 the
  scrubbed prompt cited a section for two form numbers, and one of the two was
  not in that section. Fix the workpaper rather than weakening the reference.
- A commit *message* describing the incident is itself public. Say "a state
  name, two employers"; do not quote them.
- If it has already been committed, do not just fix the file forward — the
  earlier commit still carries it. Escalate to the user before pushing, because
  the remedy is a history rewrite and that is their call.

This is authoring-time enforcement of LINT.md's "Public-repository hygiene".
The monthly privacy audit (`c4po/.claude/scheduled/c4po-privacy-audit-monthly.prompt`)
is the backstop, not the gate.

**Why this rule is also summarised in the root `AGENTS.md`:** the `paths:` above
fire when a matching file is *read*. Probed 2026-08-21: a session whose first
action is a `Write` creating a new file at a matching path does **not** load this
rule — which is exactly the shape of the 2026-08-16 incident. The `AGENTS.md`
line is what covers authoring; these globs cover editing.
