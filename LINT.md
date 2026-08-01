# Lint
Rules for AGENTS.md files in this workspace. These exist to keep agent context
consistent, discoverable, and low-maintenance.
**This file is reference data, not always-on context.** It lives outside
`AGENTS.md` deliberately: only the lint audit and the assumptions audit consume
it, so loading it into every agent's every session was pure overhead. Read it
when auditing or when changing a rule; it is authoritative when you do.
Consumers: `c4po/.claude/scheduled/c4po-lint-audit-monthly.prompt` (and its
paired `/lint-audit`) enforce these rules;
`c4po/.claude/scheduled/c4po-assumptions-audit-monthly.prompt` re-evaluates the
ephemeral values written here — today the **Size** ceiling. C4PO owns
enforcement (see `c4po/AGENTS.md`).
### Scope
- The lint audit walks every AGENTS.md in the workspace tree **and** recurses into each independent repo under `repos/*` (enumerate the filesystem — `repos/` is git-ignored, so its children never appear in workspace git status).
- `repos/*` inherit the **generic** rules — Coverage, Size, Cross-references, Paths, Imports — with each repo's root AGENTS.md treated like the workspace root (no parent-directory mention required).
- The **workspace-specific** rules — Repo design folders, README, MCP servers, Slash commands, Scheduled tasks — bind The Borg itself, not `repos/*`; a repo documents its own commands and automation in its own README. (MCP servers loaded from a repo's config are still covered by the registry rule via the daily security audit.)
### Coverage
- AGENTS.md is required at **context boundaries** — places where an agent's operating rules, role, or domain changes. Concretely: the workspace root, each top-level directory (e.g., `cerebruh/`), and any subdirectory with rules that meaningfully differ from its parent.
- AGENTS.md is **not** required in every directory. Skip auto-generated dirs (`node_modules/`, `dist/`, `build/`, `.git/`), vendored code, and leaf directories whose purpose is obvious from context.
- Every `AGENTS.md` has an adjacent `CLAUDE.md` containing exactly `@AGENTS.md` so Claude Code loads the same canonical instructions.
### Size
- AGENTS.md files should stay under **150 lines**. This ceiling is a moving target — C4PO's monthly assumptions audit re-evaluates the number against current OpenAI, Anthropic, and community guidance and updates it here; the lint audit enforces conformance to whatever number is written above.
- Content that is durable, reusable, or domain-specific — procedures, multi-step workflows, knowledge that doesn't need to load every session — belongs in a skill or a scoped rule, not in AGENTS.md. When a file approaches the ceiling, relocate such content rather than padding the file.
### Cross-references
- With the exception of the root-level `AGENTS.md`, every AGENTS.md file mentions its parent directory.
- Every AGENTS.md lists its meaningful children. A child is "meaningful" if it shapes the agent's context or behavior — regardless of file format. Specifically:
   - A subdirectory is meaningful if it either contains its own AGENTS.md, or holds files the agent is expected to read, update, or treat as authoritative (e.g., ai-sleeve/ holding rebalance snapshots and the investable universe).
   - A file is meaningful if the agent is expected to read, update, or treat it as authoritative (e.g., USER.md, persona/soul files, role definitions).
   - Source code, build artifacts, generated data, and files discoverable through normal task exploration are not considered meaningful.
- **Fully-untracked private directories are exempt.** A top-level directory that is git-ignored in its entirety — no `.gitkeep`, nothing tracked — is intentionally omitted from the root-level `AGENTS.md` Directory Structure block and from `README.md`, and must not be flagged as a missing child. A forker never receives the directory, so listing it would document something absent from their checkout while disclosing the private role it serves. Contrast `repos/`, whose *existence* is tracked via `.gitkeep` and which is therefore listed. Currently exempt: `vinny/`.
- Reference cerebruh **only when adding domain-specific routing** (e.g., "for accounting questions, see `cerebruh/wikis/accounting/`"). Do not restate the general cerebruh usage policy — that lives in the root-level `AGENTS.md` and is inherited.
### Repo design folders
- `jony-vibe/AGENTS.md` lists every `repos/*/design/` directory that exists on disk, and every repo design path it lists exists. Check the filesystem, not git — `repos/` is git-ignored, so its children never appear in workspace git status.
- This is the one sanctioned cross-reference from an agent's AGENTS.md into `repos/` (design deliverables live inside the target repo, so Jony Vibe needs the pointer). Other agents do not list `repos/` children.
### README
- The `Directory Structure` block in the root-level `AGENTS.md` is similar to the `## Directory Structure` in `README.md`.
- `README.md` documents all **non-private** scheduled tasks and slash commands of this AI workspace.
- **Private items are exempt from README.** A scheduled task or slash command marked private is intentionally omitted from `README.md` and must not be flagged as a coverage gap. Mark a command private with `private: true` in its YAML frontmatter; mark a scheduled task private with a `<!-- Private: true -->` marker line at the top of its `.prompt`. Private items still obey every other lint rule (the scheduled-task↔command pairing, step-reference and override completeness, paths) — privacy only excuses them from the public-facing README, not from consistency checks.
### Paths
- All paths and symlink targets in `AGENTS.md` scaffolding and compatibility files are correct. Relative paths resolve from the file or symlink containing them, not the working directory.
### Imports
- `AGENTS.md` files never use Claude's `@file` import syntax; Codex does not expand it. Shared canonical instructions use filesystem symlinks instead.
- Every `CLAUDE.md` is only the compatibility wrapper `@AGENTS.md`; canonical instructions never live in or directly import another `CLAUDE.md`.
### MCP servers
- Every MCP server loaded by any Borg agent must have an entry in `c4po/MCP.md` with scope, source, which agent(s) load it, and a one-line justification.
- A server not listed in `c4po/MCP.md` is unapproved — remove it or add an entry.
- Prefer the narrowest scope that works.
### Slash commands
- Markdown files under the workspace or a live agent's `.claude/commands/` are the canonical command sources for both harnesses. Claude Code invokes them as `/name`; `.bin/sync-codex-prompts.sh` exposes them to Codex as `/prompts:name` because Codex reserves direct slash-command names.
- After adding, renaming, or removing a command, run `.bin/sync-codex-prompts.sh`; `.bin/sync-codex-prompts.sh --check` must pass. Unique basenames keep their name; collisions are scope-prefixed. The bridge never overwrites an unrelated file in `~/.codex/prompts/`.
- Command bodies must work in either harness. Harness-specific frontmatter may refine behavior but cannot be required for correctness; Codex ignores Claude-only metadata such as `model:` and `private:`.
- In Claude command frontmatter, `model:` uses a stable Claude Code alias (`haiku`, `sonnet`, `opus`, or `fable`), never a dated/full model ID. Command bodies must still work when another harness ignores that metadata.
### Public-repository hygiene
- Treat every tracked file as public. Before committing, inspect added text for personal home-directory paths, hostnames, usernames, LAN/tailnet details, account identifiers, and private infrastructure instructions.
- Use checkout-relative placeholders such as `<workspace-root>` in tracked documentation and prompts. Keep machine-specific instructions in gitignored `*.local.md` or `settings.local.json` files.
- Keep repo-specific automation inside its owning `repos/*` repository; The Borg may document or invoke it without duplicating its private implementation.
### Scheduled tasks
- Every scheduled task (a launchd job under the `com.theborg.*` namespace, driven by a `.prompt` file) has a corresponding canonical interactive slash command in the owning agent's `.claude/commands/`; the slash-command bridge makes the same source available to Codex. A workspace-level command may host the companion instead when the task is the wider-scope twin of something that command already does — then one command carries both scopes, dispatched on an explicit argument token, rather than two near-duplicate commands existing side by side. `c4po-retro` / `/retro sessions` is the standing example.
- That command **delegates to the same `.prompt` file** the launchd job runs — it must not duplicate the task logic. It applies only the overrides needed for interactive use: skip once-per-month state gates and any state/data-file writes, and report to the session instead of piping to `notify-email.sh`.
- **Step references must line up.** When a command's overrides cite specific steps of its `.prompt` (e.g. "SKIP STEP 1", "STEP 3 — output to session"), every cited step number must exist in that `.prompt` and must still denote what the override targets: a skip-the-gate override must point at the step that checks/writes the state or data file; the report-to-session override must point at the step that pipes to `notify-email.sh`. If a `.prompt` is renumbered or restructured, update the command's references in the same change.
- **Overrides must be complete.** Conversely, every side-effecting step in the `.prompt` has a matching override in the command: each state gate and each state/data-file write is skipped, and each `notify-email.sh` pipe is rerouted to the session. A side effect added to a `.prompt` without a corresponding override in its command is a violation.
