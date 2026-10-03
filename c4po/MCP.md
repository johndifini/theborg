# MCP Server Registry

Authoritative list of MCP servers approved for use in The Borg. Maintained by C4PO. See `../LINT.md` → MCP servers for the governing rules.

## Approved servers

| Server | Scope | Source | Loaded by | Justification |
|---|---|---|---|---|
| _(none)_ | | | | Telegram plugin decommissioned 2026-07-18 (user no longer uses Telegram); no MCP servers currently approved. |

## Bundled but not loaded

Third-party plugins that ship an MCP server which does not run here, either because it is **not registered** or because it is **registered but denied** by a `deniedMcpServers` entry. A plugin registers a server through an `mcpServers` key in its manifest *or* through a `.mcp.json` file at the plugin root, so check both. Verify with `claude mcp list` from the directory where the plugin is enabled. Recorded here so a future audit can diff it and catch the day it goes live.

| Plugin | Bundled server | Reviewed version | Notes |
|---|---|---|---|
| `last30days@last30days-skill` (GitHub `mvanhorn/last30days-skill`) | `last30days-pp-mcp` (Go binary, outbound web search) | skill 3.8.3 / mcp manifest 3.6.0 (reviewed 2026-07-05) | Installed intentionally by the user. Currently inert — the skill runs via CLI, not the MCP server. Also ships a **SessionStart hook** (`hooks/scripts/check-config.sh`) that runs in every session: inspected 2026-07-05, non-malicious (status banner, Keychain presence check, chmod-600 of loose config). Promote to **Approved servers** if the MCP server is ever registered. |
| `vercel@claude-plugins-official` (GitHub `vercel/vercel-plugin`) | `vercel` (HTTP, `https://mcp.vercel.com`, OAuth, read-only in initial release) | plugin 0.50.0 installed; hooks last reviewed at 0.49.0 (2026-09-13) | Installed 2026-09-07 at **project scope only** (`ari/career-dossier`), for that project's Vercel deployment surface. **Registered but denied.** The manifest has no `mcpServers` key, but the plugin ships a root `.mcp.json`, and Claude Code registers that file. On 2026-10-02, `claude mcp list` in `ari/career-dossier` showed `plugin:vercel:vercel` (never authenticated). An earlier version of this row called the server inert, and that was wrong. It is now blocked by `"deniedMcpServers": [{"serverName": "plugin:vercel:vercel"}]` in `ari/career-dossier/.claude/settings.json`. The deny matches only the full `plugin:<plugin>:<server>` name: a bare `vercel` entry did not take effect. After the deny, `claude mcp list` there reports no servers. Ships **5 hooks**: 3 SessionStart, 1 SessionEnd (gated on Vercel/Next.js markers or an empty directory), and, since 0.49.0, a **PostToolUse hook** on `matcher: Skill` (`hooks/posttooluse-skill-telemetry.mjs`). That hook re-invokes itself detached to POST skill-usage events. Reviewed at source on 2026-09-13 (0.49.0): it honours `VERCEL_PLUGIN_TELEMETRY=off` (set in the project's `.claude/settings.json`). It sends only plugin-shipped skill slugs plus a plugin-minted UUID, never the harness session id, which is used only as a local temp-file key. Its only outbound host is `telemetry.vercel.com`. Subprocess calls are fixed-arg and shell-free: `vercel --version`, `npm view vercel version`, and a self-spawn of the sender. **0.50.0 is not yet fully re-reviewed.** It keeps the same 5 hooks and the same single outbound host (`telemetry.vercel.com`), and its `.mcp.json` is unchanged from 0.49.2. But `telemetry.mjs`, `pretooluse-skill-inject.mjs`, and `skill-map-frontmatter.mjs` changed. **NOTE: plugin updates are automatic and bypass review (0.48.0 → 0.49.0 was security-audit findings 24/26). `gitCommitSha` did NOT change across that update, so diff the VERSION, never the sha.** To use the server, remove the deny entry and promote this row to **Approved servers** with a justification. |

## Out of scope

Servers loaded by the Claude Code harness, FleetView, or claude.ai connectors (e.g., session management, browser automation, scheduled tasks, claude.ai Gmail/Calendar/Drive) are not configured by The Borg and are not governed by this registry. If one of those starts being relied on as part of an agent's workflow, promote it to a Borg-level dependency and add an entry here.

The same exclusion applies on the Codex side. The ChatGPT desktop app and the Codex Computer Use app write their own `[mcp_servers.*]` stanzas into `~/.codex/config.toml`, which is global — so any Borg agent or scheduled job running under `HARNESS=codex` inherits them. They are app-managed, rewritten by the apps on update, and not configured by The Borg. As of 2026-09-01 there are two:

| Server | State | Source |
|---|---|---|
| `node_repl` | **Live** (no `enabled` key, so on by default) | `ChatGPT.app/Contents/Resources/cua_node/bin/node_repl` |
| `computer-use` | **Disabled** (`enabled = false`) | `Codex Computer Use.app/…/SkyComputerUseClient` |

The daily security audit already tracks these — it records them under `codex_mcp_servers_unregistered` and diffs `~/.codex/config.toml` by SHA-256 each run, so a new stanza or a flip of `computer-use` to enabled surfaces there. Promote either to **Approved servers** above if a Borg agent's workflow ever starts depending on it.
