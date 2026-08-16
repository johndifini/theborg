# Quick Start

Get The Borg running on a Mac in about ten minutes. For what any of it *is*, read the [README](./README.md) first — this page assumes you've decided you want it.

Before your first commit, also read [SECURITY.md](./SECURITY.md). There's a short forker checklist in there that may save you from publishing secrets, personal notes, or API keys.

## Prerequisites

- **macOS.** The scheduled-job framework is launchd-based and doesn't run elsewhere.
- **At least one harness** — Claude Code, Codex, or both. The Borg is harness-agnostic: agents work in either, and each scheduled job picks one independently. Install whichever you use:
  - **Claude Code** — [claude.com/claude-code](https://claude.com/claude-code). The default for scheduled jobs, and what step 3 authenticates.
  - **Codex** — optional. Slash commands reach it through the bridge in step 5, and any job can be switched to it (step 6).

  If you install only Codex, skip step 3 and set `BORG_HARNESS=codex` (step 6) so jobs don't look for a `claude` binary that isn't there.
- **Xcode Command Line Tools**, which is where macOS gets `git`. macOS ships a `git` *shim*, not `git` itself — the first time you run it you get a GUI dialog asking to install the tools. Get it over with up front:

  ```bash
  xcode-select --install
  ```

  Already installed? The command says so and exits. That's fine.

- A **Gmail account with 2FA**, if you want email notifications (step 4).

## 1. Decide where your AI workspace lives

The commands below assume your home directory. `BORG_ROOT` points every script and prompt at the workspace root:

```bash
echo 'export BORG_ROOT="${HOME:?}/theborg"' >> ${HOME:?}/.zshenv
```

**Strictly speaking this variable is optional.** Every script auto-detects the workspace root from its own location in `.bin/`, so nothing breaks without it. Set it anyway: it makes `cd $BORG_ROOT` work from anywhere, and it's the documented override if you ever keep the checkout somewhere other than `~/theborg`.

Open a new terminal tab so the variable takes effect, or run `source ~/.zshenv` in the current one.

## 2. Get the code

The repo is public, so a plain HTTPS clone needs no GitHub account, no SSH key, and no `gh` login:

```bash
git clone https://github.com/johndifini/theborg.git "$BORG_ROOT"
```

```bash
cd "$BORG_ROOT"
```

## 3. Set your Claude OAuth token

```bash
claude setup-token
```

That prints a long-lived token (it requires a Claude subscription). Put it in `.zshenv` and lock the file down:

```bash
echo 'export CLAUDE_CODE_OAUTH_TOKEN=xxxx' >> ${HOME:?}/.zshenv
```

```bash
chmod 600 ${HOME:?}/.zshenv
```

**Is this step necessary?** Only if you want scheduled tasks — they run headless, with no interactive login session to borrow credentials from. For interactive use, `claude` already authenticated you at login and this changes nothing.

## 4. Configure email notifications

Scheduled jobs report by email — it's the only notification channel, so a job with no email configured is a job you'll never hear from.

```bash
cp .env.example .env
```

```bash
chmod 600 .env
```

Open `.env` in your favorite text editor and follow the instructions in its header. The short version: `EMAIL_SMTP_PASS` must be a Gmail **App Password** (16 characters, created at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords), requires 2FA on the sending account) — not your account password.

## 5. Install the git hook

```bash
git config core.hooksPath .githooks
```

This wires up the pre-commit hook that helps keep secrets out of your history. One command, worth doing before your first commit.

**Using Codex as well as Claude Code?** Publish the slash commands and scoped rules as Codex skills:

```bash
.bin/sync-codex-prompts.sh && .bin/sync-codex-rule-skills.sh
```

Claude-only users can skip that.

## 6. Install the scheduled tasks you want

Generate the launchd plists for every registered task:

```bash
.bin/install-scheduled-tasks.sh
```

Writing a plist does **not** start anything. The file just sits in `~/Library/LaunchAgents/` until you register it with launchd, so this step is safe and reversible — you'll see plists for agents you may not use, and they're inert.

Now activate only the ones you want. This is a good starting set — the four c4po audits plus the CLI updater:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.theborg.c4po-security-audit.plist
```

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.theborg.c4po-lint-audit-monthly.plist
```

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.theborg.c4po-assumptions-audit-monthly.plist
```

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.theborg.c4po-retro.plist
```

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.theborg.c4po-cli-update.plist
```

The `.plist` extension is required — `launchctl bootstrap` takes a path to a real file, and dropping the extension gets you a bare `Bootstrap failed: 5: Input/output error`.

For every task and what it does, see [Scheduled Jobs](./README.md#scheduled-jobs) in the README. Two more you may want once you're settled in: `com.theborg.c4po-privacy-audit-monthly` and `com.theborg.c4po-backlog-burndown` (the burndown runs unattended with permissions bypassed and edits files across the whole workspace — read its prompt before enabling it).

**Want everything at once instead?** `.bin/install-scheduled-tasks.sh --load` generates and registers every task in one shot.

### Choosing a harness per job

Every job runs on Claude unless told otherwise. To change the default for all of them:

```bash
echo 'export BORG_HARNESS=codex' >> ${HOME:?}/.zshenv
```

To move a single job, drop a `.conf` sidecar next to its prompt — this puts the backlog burndown on Codex while everything else stays on Claude:

```bash
echo 'HARNESS=codex' > "$BORG_ROOT/c4po/.claude/scheduled/c4po-backlog-burndown.conf"
```

No plist regeneration needed; the runner reads the sidecar at fire time. If the chosen CLI isn't installed, the job fails with exit 127 and emails you rather than silently running on the other one.

### One setting the backlog burndown wants

The burndown deliberately spends the tail of your weekly budget just before it resets, so it needs to know when that happens. On **Codex** it works this out on its own, reading the real reset from your session data. On **Claude** there's nothing to read — no CLI reports it — so tell it once:

```bash
claude
```

Run `/usage` in that session, note the weekly reset day and time, then:

```bash
echo 'export BORG_CLAUDE_RESET="wed 11:00"' >> ${HOME:?}/.zshenv
```

Format is a three-letter weekday and a 24-hour time, in your local timezone. Check it with:

```bash
.bin/weekly-reset.sh --harness claude
```

Skip this and nothing breaks — the burndown runs anyway and tells you the reset is unknown. It just may spend the wrong week's budget. Every other job ignores this setting entirely.

**Changed your mind about one?**

```bash
launchctl bootout gui/$(id -u)/com.theborg.c4po-retro
```

## 7. Verify

Confirm the jobs registered:

```bash
launchctl list | grep com.theborg
```

You should see one line per task you bootstrapped. A `0` in the status column means it hasn't failed.

Then test the email path without waiting for a scheduled fire — start Claude Code in `c4po/` and run `/security-audit`. Every scheduled task has a matching slash command that runs the same logic interactively and reports to your session, which is the fastest way to confirm a job does what you expect before it runs on its own at 10 AM.

## Where to go next

- [README](./README.md) — what each agent is for, the full scheduled-job list, and every slash command.
- [SECURITY.md](./SECURITY.md) — read before your first commit.
- `cerebruh/wikis/index.md` — the shared knowledge base every agent reads from.
- Delete the agents you don't want. Nothing here is load-bearing on the rest.
