# MCP Server Registry

Authoritative list of MCP servers approved for use in The Borg. Maintained by C4PO. See `../LINT.md` → MCP servers for the governing rules.

## Approved servers

| Server | Scope | Source | Loaded by | Justification |
|---|---|---|---|---|
| _(none)_ | | | | Telegram plugin decommissioned 2026-07-18 (user no longer uses Telegram); no MCP servers currently approved. |

## Bundled but not loaded

Third-party plugins that ship an MCP server which is **not currently registered** (no `mcpServers` entry in the plugin manifest or `~/.claude.json`), so it does not run. Recorded here so a future audit can diff it and catch the day it goes live.

| Plugin | Bundled server | Reviewed version | Notes |
|---|---|---|---|
| `last30days@last30days-skill` (GitHub `mvanhorn/last30days-skill`) | `last30days-pp-mcp` (Go binary, outbound web search) | skill 3.8.3 / mcp manifest 3.6.0 (reviewed 2026-07-05) | Installed intentionally by the user. Currently inert — the skill runs via CLI, not the MCP server. Also ships a **SessionStart hook** (`hooks/scripts/check-config.sh`) that runs in every session: inspected 2026-07-05, non-malicious (status banner, Keychain presence check, chmod-600 of loose config). Promote to **Approved servers** if the MCP server is ever registered. |

## Out of scope

Servers loaded by the Claude Code harness, FleetView, or claude.ai connectors (e.g., session management, browser automation, scheduled tasks, claude.ai Gmail/Calendar/Drive) are not configured by The Borg and are not governed by this registry. If one of those starts being relied on as part of an agent's workflow, promote it to a Borg-level dependency and add an entry here.

The same exclusion applies on the Codex side. The ChatGPT desktop app and the Codex Computer Use app write their own `[mcp_servers.*]` stanzas into `~/.codex/config.toml`, which is global — so any Borg agent or scheduled job running under `HARNESS=codex` inherits them. They are app-managed, rewritten by the apps on update, and not configured by The Borg. As of 2026-09-01 there are two:

| Server | State | Source |
|---|---|---|
| `node_repl` | **Live** (no `enabled` key, so on by default) | `ChatGPT.app/Contents/Resources/cua_node/bin/node_repl` |
| `computer-use` | **Disabled** (`enabled = false`) | `Codex Computer Use.app/…/SkyComputerUseClient` |

The daily security audit already tracks these — it records them under `codex_mcp_servers_unregistered` and diffs `~/.codex/config.toml` by SHA-256 each run, so a new stanza or a flip of `computer-use` to enabled surfaces there. Promote either to **Approved servers** above if a Borg agent's workflow ever starts depending on it.
