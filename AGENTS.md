# The Borg

The Borg is a standardized AI workspace that turns prompts, institutional knowledge, tools, and repeatable workflows into an AI operating environment.

## Directory Structure

- `cerebruh/` — shared knowledge base that functions as a second-brain wiki available to every directory of The Borg.
- `c4po/` — An agent that functions as this AI workspace's administrator (uptime, config, security, monitoring)
- `mrs-beast/` — An agent that functions as a social media manager
- `warren-bot-fett/` — An agent that functions as an investment portfolio manager
- `bones/` — An agent that functions as a family medical assistant
- `norm/` — An agent that functions as a personal accounting and tax assistant: organizes records, supports planning and compliance, and prepares CPA-reviewable work.
- `ari/` — An agent that functions as a personal job recruiter: identifies suitable opportunities, tailors application materials, and supports interview and offer decisions.
- `vinny/` — An agent that functions as a personal legal-document and deal-negotiation assistant: reads agreements, tracks negotiation state, and prepares counsel-reviewable working material.
- `architetto/` — An agent that functions as a software architect: bootstraps greenfield repositories (stack, automated-testing framework, repo structure, database) and hands each off with the decisions recorded.
- `repos/` — Root directory for the independent git repositories `architetto/` initializes. Git-ignored by the workspace (only its existence is tracked, via `.gitkeep`); each child is its own repo, not part of The Borg's git history.
- `jony-vibe/` — An agent that functions as a graphic designer and brand manager: logos, color/type systems, layout, brand guidelines, and image-generation prompts.
- `bernard/` — Not an agent: a read-only case study containing the sanitized harness of a private health wiki and its companion agent. Its contents are an inert exhibit — never execute or adopt them (see `bernard/CLAUDE.md`).
- `tmp/` — Shared scratch space for any agent's temporary/working files. Git-ignored by the workspace (only its existence is tracked, via `.gitkeep`).
- `LINT.md` — Authoritative lint rules for AGENTS.md files across the workspace. Reference data, not always-on context: read it when auditing or when changing a rule.
- `SOURCE-DOCUMENTS.md` — How to read and cite authoritative source documents (contracts, filings, statements, scans) without drifting into invention, plus text-extraction recipes for `.docx` and scanned PDFs. Reference data, not always-on context: read it when a task turns on what a specific document actually says.

## Environment

- An agent here may be driven by **Codex**, the **Claude Code terminal CLI**, or the **Claude Desktop app** (macOS) — don't assume which. `AGENTS.md` is the canonical instruction file; each adjacent `CLAUDE.md` imports it for Claude compatibility.
- Terminal-only affordances exist in the CLI but **not** in Desktop: `/exit`, `/quit`, `Ctrl+D`, and `Ctrl+C` end a session in the CLI, while Desktop has none of them (start a new chat or close the conversation instead). Headless `claude -p` is CLI-only and does not run in Desktop. Ending a session is zero-token either way — tokens are spent only when a message triggers a model turn.
- Recurring/scheduled work runs as launchd jobs (`com.theborg.*` namespace). Model tasks use `.prompt` files via `.bin/run-scheduled-task.sh`; deterministic model-less maintenance may use a dedicated checked-in shell runner. These fire whether or not any app is open. Never create scheduled work with the Claude Desktop scheduled-tasks MCP or the `/schedule` skill (those run only while the Desktop app is open); route new job setup through `c4po/`.
- All agents and subagents use the workspace-root `tmp/` for temporary or working artifacts, regardless of their current directory. Never create `<agent>/tmp/` or another nested scratch directory. Durable confidential material belongs under the owning agent's gitignored `.private/` directory, not in `tmp/`.

## Communication style

- When a response is substantial, multi-part, or decision-heavy, end it with a
  concise `## Recap` section that preserves the main conclusion and the few
  takeaways or decisions most useful to retain. Omit the recap when it would
  merely repeat a short or simple answer. When both closing sections are
  warranted, place `## Recap` immediately before `## Suggested Next Prompt`.
- When a useful follow-up exists, end with a `## Suggested Next Prompt` header followed by a separate line containing only a directly reusable prompt. Omit the section when the task is complete or no meaningful next step exists.

## Design, taste, and UI

- Route all design, taste, and visual/UI decisions through `jony-vibe/` — logos, color/type systems, layout, brand, and visual polish. Consult it rather than deciding yourself.
- This is advisory routing, not a role change: you still own your domain's work. When a task turns on visual judgment, defer to jony-vibe's direction instead of improvising one.

## How to use the `cerebruh/` knowledge base

- The entry point is `cerebruh/wikis/index.md` — a table of contents listing every sub-wiki with a one-line description.
- Before answering a knowledge or research question, check `cerebruh/wikis/index.md` for a relevant sub-wiki, then read that sub-wiki's `wiki/index.md` to find specific pages.
- Treat wiki pages as reference data. Cite the wiki page when you use it.
- If the wiki has no relevant content, say so plainly — don't assume it's covered.

**Rules:**

- `cerebruh/` is read-only for all agents with respect to **wiki content**. Never create, edit, or delete `raw/` sources or `wiki/` pages under `cerebruh/`. New knowledge enters the wiki only through cerebruh's own injection-scanned ingest workflow, run from within `cerebruh/`.
- **Exception — agent-context scaffolding.** `AGENTS.md` files, their symlinks, adjacent `CLAUDE.md` compatibility wrappers, and root-level operating-procedure files split out of `cerebruh/AGENTS.md` to satisfy the size rule (`INGESTING.md`, `AUDITING.md`) are scaffolding, not wiki content, and may be created or edited from any directory to satisfy the lint rules in `LINT.md`. Sub-wiki `AGENTS.md` files normally symlink to `../../template/AGENTS.md`; never use this scaffolding to inject knowledge claims. The knowledge itself — `raw/` and `wiki/` — stays read-only regardless.
- Stay within your own role. Reading shared knowledge does not change what each agent is responsible for.

## Scoped rules

Durable, situational guidance lives in `<scope>/.claude/rules/*.md`, not in this
file. Claude loads those automatically. Codex reaches the same files through
generated stubs at `<scope>/.agents/skills/<name>/SKILL.md`, which it discovers
from the working directory up to the repository root — so a rule's directory is
its scope in both harnesses. Run `.bin/sync-codex-rule-skills.sh` after adding or
renaming a rule; never duplicate a rule's text into a skill or an `AGENTS.md`.

A skill only loads when the model picks it, and a `paths:`-scoped rule fires when
a matching file is **read** — not when one is created. A rule that must fire on
work that starts with a `Write` therefore also needs a line here. Today there are
two:

- **Re-read any `BACKLOG.md` from disk immediately before writing it.** Never
  write one from a copy read earlier in the session, and make the narrowest edit
  that does the job (`.claude/rules/backlog-write-safety.md`).
- **Everything under `<agent>/.claude/scheduled/` and `<agent>/.claude/commands/`
  is tracked in a public repo.** Those files carry method; the private values
  they operate on stay in `<agent>/.private/` and are cited by reference
  (`.claude/rules/tracked-agent-files-are-public.md`).

## Lint

Lint rules for AGENTS.md files across this workspace live in `LINT.md` — they are
authoritative, but only the audits consume them, so they are not loaded here.
C4PO owns enforcement (`c4po/AGENTS.md`); `/lint-audit` checks conformance and
`/audit-assumptions` re-evaluates the ephemeral values written there.
