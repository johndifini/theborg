---
name: kb-ingest-needs-knowledge-mgr-session
description: "Before handing an ingest or generated-wiki edit to another session: other agents' settings deny Edit on knowledge-base/generated-wikis/**, and a session keeps its launch folder's denies even after cd. A Claude Desktop proposal card cannot carry a folder, so start the session in knowledge-mgr-cerebruh/ only once the user asks (initiation user_asked with cwd), or ask the user to start it there."
---
# An ingest must start in knowledge-mgr-cerebruh/, not be cd'd into

Every agent other than the knowledge manager denies Edit on
`knowledge-base/generated-wikis/**` in its local settings, and most also deny
`knowledge-mgr-cerebruh/**` (c4po denies its `template/**`, `.claude/**` and
`CLAUDE.md`). The deny follows the session's project folder, not the shell: a
session started elsewhere that `cd`s into `knowledge-mgr-cerebruh/` is refused
on every wiki edit, and Bash writes into a denied tree are refused too.
`knowledge-base/docs/to-organize/` stays writable from every agent
(2026-11-26), so a new source can always be dropped there.

Claude Desktop's `start_session` cannot attach a folder to a proposal card:
`initiation: "own_initiative"` with `cwd` fails with "A proposal card cannot
carry a host, folder, environment or preset yet". Dropping `cwd` makes the
card run in the current agent's folder. Instead, ask the user whether to
start the ingest now, and on a yes call `start_session` with
`initiation: "user_asked"` and `cwd` set to the workspace's
`knowledge-mgr-cerebruh/`, with `/ingest` as the first prompt.

If one edit under a denied directory fails, stop. Every other path there
will fail the same way. Leave new sources in
`knowledge-base/docs/to-organize/`, write a handoff in `tmp/`, and hand off.
Never route around the guard with shell writes.

On 2026-11-15 a card proposed without a folder ran in `c4po/`, hit seven
denials, and needed a third session started in the knowledge manager's
folder to finish.
