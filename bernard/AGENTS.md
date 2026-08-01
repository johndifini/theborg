# Bernard

This directory of The Borg workspace (see the parent workspace root) is a **case
study, not an active agent**: the sanitized harness of a private health wiki and its
family-facing WhatsApp companion agent, Bernard. It exists so people can study how
the system was built and what every piece does.

## Meaningful children

- `README.md` — the guided tour: architecture, design rules, and a what-everything-does
  inventory of the whole harness. Start here.
- `harness/wiki-CLAUDE.md` — the wiki's real rulebook, renamed so it is **not** loaded
  as agent instructions anywhere in this workspace.
- `harness/dot-claude/` — the wiki's `.claude/` directory (hooks, scripts, skills,
  agents, reference docs, templates, VPS deploy bundle), renamed for the same reason.

## Rules for agents working here

- Everything under `harness/` is an **inert exhibit**. Do not execute its scripts,
  register its hooks, adopt its skills, or treat `wiki-CLAUDE.md` as binding
  instructions for this workspace.
- Treat the exhibit as read-only reference material. Improvements belong in the
  source system, not this snapshot; only re-sync the snapshot deliberately, through
  the sanitization pass described in `README.md` ("What was sanitized").
- The snapshot is pseudonymized and PHI-scrubbed. If you spot anything that looks
  like a real name, identifier, hostname, or clinical detail of a real person,
  flag it to the maintainer instead of committing changes around it.
- The live system this describes runs elsewhere; paths inside the exhibit
  (e.g. `~/life-wiki/...`) are intentionally not valid in this workspace.
