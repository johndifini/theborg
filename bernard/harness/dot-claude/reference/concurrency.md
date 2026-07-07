# Concurrency and multi-agent safety

Multiple writers can touch this one working tree at once — Claude Code, Codex, Gemini, the curator in a terminal, and the scheduled write jobs (`daily-synthesis`, `daily-ingest-check`, `build-backlinks --apply`). The shared git index is the fragile point: on 2026-06-15 a broad `git add` in one context swept an in-progress session's files into another commit. Three layers keep this clean.

## 1. Explicit-path staging + verify-after (all agents and the curator)

Never `git add -A` / `git add .`. Stage only the files you touched, `git status` to confirm nothing foreign is staged, commit, then re-check `HEAD`. This is the load-bearing rule — it makes the index-sweep impossible regardless of who else is active. (Hard rule, top of `CLAUDE.md`.)

## 2. The shared wiki-write lock

`.claude/scripts/wiki-lock.sh` (CLI) + `.claude/scripts/lib/wiki-lock.sh` (lib). Advisory, atomic (`mkdir`), TTL 2 h. Unit tests: `lib/test_wiki-lock.sh`.

- **Interactive agents: take it for write-heavy work** (ingest, synthesis, backlink rebuilds, multi-file entity edits) and release when done:
  - `bash .claude/scripts/wiki-lock.sh acquire "ingest (claude)"`
  - `bash .claude/scripts/wiki-lock.sh release`
- The three scheduled write jobs **acquire it and defer** (exit 0, retry next run) **if held** — so a cron can't rewrite a file mid-session, and two jobs can't collide. `build-backlinks` dry-run takes no lock.
- A forgotten hold self-frees after the 2 h TTL; `harness-health.sh` also sweeps a stale `wiki-write.lock`. Inspect/clear by hand: `wiki-lock.sh status` / `clean`.
- It does **not** stop a raw `git commit` typed in another terminal — that's what rules 1 and 3 cover.

## 3. One writer at a time (operational)

When an agent is mid-session, let it finish and commit, or commit yourself with explicit paths — don't do both at once. For deliberately parallel agents, isolate them in **git worktrees** (one checkout each, merge after) so they can't share an index at all.

---

Inventory entry: `harness-map.md` Known-gaps #8 (closed 2026-06-15).
