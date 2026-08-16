# Quick Start

Get The Borg running on a Mac in about ten minutes. For additional information, see the [README](./README.md).

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

## 1. Set `BORG_ROOT`

The commands below assume your home directory. `BORG_ROOT` points every script and prompt at the workspace root:

```bash
echo 'export BORG_ROOT="${BORG_ROOT:-${HOME:?}/theborg}"' >> ${HOME:?}/.zshenv
```

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

If you only plan to use Codex, skip this step.

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

## 4. Configure email notifications

Scheduled jobs report by email — it's the only notification channel, so a job with no email configured is a job you'll never hear from.

```bash
cp .env.example .env
```

```bash
chmod 600 .env
```

Open `.env` in your favorite text editor and follow the instructions in its header. The short version: `EMAIL_SMTP_PASS` must be a Gmail **App Password** (16 characters, created at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords), requires 2FA on the sending account) — not your account password.

## 5. Expose the slash commands to Codex

If you only plan to use Claude, skip this step.

Publish the slash commands and scoped rules as Codex skills:

```bash
.bin/sync-codex-prompts.sh && .bin/sync-codex-rule-skills.sh
```

## 6. Install the scheduled tasks you want

Generate the launchd plists for every registered task:

```bash
.bin/install-scheduled-tasks.sh
```

Writing a plist does **not** start anything. The file just sits in `~/Library/LaunchAgents/` until you register it with launchd, so this step is safe and reversible — you'll see plists for agents you may not use, and they're inert.

Now activate only the ones you want. This is a good starting set — the four c4po jobs plus the CLI updater:

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

For every task and what it does, see [Scheduled Jobs](./README.md#scheduled-jobs) in the README.

### Choosing a harness per job

Every job runs on Claude unless told otherwise. To change the default for all of them:

```bash
echo 'export BORG_HARNESS=codex' >> ${HOME:?}/.zshenv
```

To move a single job, drop a `.conf` sidecar next to its prompt — this puts the security audit on Codex while everything else stays on Claude:

```bash
echo 'HARNESS=codex' > "$BORG_ROOT/c4po/.claude/scheduled/c4po-security-audit.conf"
```

No plist regeneration needed; the runner reads the sidecar at fire time. If the chosen CLI isn't installed, the job fails with exit 127 and emails you rather than silently running on the other one.

## 7. Verify

Confirm the jobs registered:

```bash
launchctl list | grep com.theborg
```

You should see one line per task you bootstrapped. A `0` in the status column means it hasn't failed.

Then test the email path without waiting for a scheduled fire — start Claude Code in `c4po/` and run `/security-audit`, or `codex` in the same directory and run `$security-audit` (the skill published by step 5). Every scheduled task has a matching command that runs the same logic interactively and reports to your session, which is the fastest way to confirm a job does what you expect before it runs on its own at 10 AM.

## Where to go next

- [README](./README.md) — what each agent is for, the full scheduled-job list, and every slash command.
- [SECURITY.md](./SECURITY.md) — read before your first commit.
- `cerebruh/wikis/index.md` — the shared knowledge base every agent reads from.
- Delete the agents you don't want. Nothing here is load-bearing on the rest.
