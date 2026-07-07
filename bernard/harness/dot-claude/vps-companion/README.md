# vps-companion — deploy bundle for the health-wiki companion agent

Everything needed to stand up the read-only health-wiki companion on the VPS
(`youruser@your-vps`). Designed for one non-technical user who texts the agent
on WhatsApp and reads styled, migraine-friendly HTML briefs via private links.

## Contents

| Path | Purpose |
|---|---|
| `workspace/` | Agent identity files (`AGENTS.md`, `IDENTITY.md`, `SOUL.md`, `TOOLS.md`) with `{{PERSON_NAME}}`/`{{COMPANION_NAME}}` placeholders |
| `workspace/skills/publish-brief/` | Markdown → low-glare large-type **PDF** at `~/health-wiki-workspace/briefs/`, sent as a WhatsApp attachment via a `MEDIA: <path>` reply line — nothing hosted publicly (Funnel must stay off: `tailscale serve reset`) |
| `infra/briefs-cleanup.{service,timer}` | systemd user timer: delete briefs older than 30 days |
| `deploy.sh` | Installs all of the above on the VPS; idempotent; never edits `openclaw.json` |
| `openclaw-config-patch.md` | The agent/channel/binding config additions, applied separately |

## Ship and run

```bash
scp -r .claude/vps-companion youruser@your-vps:~/vps-companion
ssh youruser@your-vps 'cd ~/vps-companion && PERSON_NAME="Jane" COMPANION_NAME="Wren" bash deploy.sh'
```

Then: Funnel setup + config patch + WhatsApp QR (deploy.sh prints the steps).

## Mac-side counterpart

- `.claude/scripts/vps-mirror-sync.sh` — one-way scoped mirror + inbox pull-back
- `.claude/scripts/com.lashawsalta.wiki-mirror-sync.plist` — daily 07:00 + once at login; load with:
  `cp .claude/scripts/com.lashawsalta.wiki-mirror-sync.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.lashawsalta.wiki-mirror-sync.plist`
- On-demand sync any time: `bash .claude/scripts/vps-mirror-sync.sh`
