# OpenClaw config additions — companion agent + WhatsApp

Apply by hand (or let Claude apply over SSH) to `~/.openclaw/openclaw.json`.
The file is JSON5 with comments — never sed it; deploy.sh backs it up first.
**Key names below follow the 2026.3.x schema as documented; validate against the
installed version** (`openclaw doctor`, then restart and check `openclaw status`).

## 1. New agent (isolated workspace)

Add to the agents list — do not touch `main` or `ops`:

```json5
{
  id: "wikicare",
  name: "COMPANION_NAME",            // e.g. "Wren" — match IDENTITY.md
  workspace: "~/health-wiki-workspace",
  model: "anthropic/claude-sonnet-4-6", // same auth profile as main
  // keep this agent OUT of any shared-session or group features
}
```

## 2. WhatsApp channel — sender allowlist (DM + one family group)

```json5
whatsapp: {
  enabled: true,
  dmPolicy: "allowlist",
  groupPolicy: "allowlist",                       // was "disabled"; enables groups
  allowFrom:      ["19723521352", "16513417421"], // patient + family member, E.164 (no '+')
  groupAllowFrom: ["19723521352", "16513417421"], // SENDER allowlist for group msgs (see note)
}
```

Linking: the gateway will print a QR on first start with WhatsApp enabled
(`openclaw channels login whatsapp` on some builds). Link a **dedicated number**
— the bot speaks as whatever account is linked.

### 2a. How group access actually works on 2026.6.x (verified 2026-06-26)

- **`groupAllowFrom` is a *sender* allowlist, not a group-JID allowlist.** The
  whatsapp extension matches it against `sender.jid`
  (`isWhatsAppSupplementalSenderAllowed`). With `groupPolicy: "allowlist"` the
  startup log reads `Listening … (DM + all groups; sender allowlist configured)`
  — Bernard will engage in **any** group he is a member of, but only acts on
  messages from allowlisted senders. **There is no built-in per-group lock.**
- **Therefore the group-membership boundary lives on the WhatsApp side, not in
  `openclaw.json`** — see §2b. Treat the WhatsApp group settings as part of the
  security config.
- **Mention-gated by default.** Groups default to require-mention
  (`requireMention = groupActivation !== "always"`), so Bernard ignores
  human-to-human chatter and only answers when addressed.

### 2b. WhatsApp-side group lockdown (curator-only, in the app — the real boundary)

The single family group must be locked so membership
can't drift (a new member = a new reader of the full PHI record):

- Group settings → **Edit group info → Only admins**
- **Add members → Only admins**
- **Invite link → Reset link**, then never share it (an active link is a back door)
- **Patient stays the sole admin** — do not promote the family member
- Disappearing messages on (90 days is fine; limits PHI lingering on phones —
  does not touch the wiki or briefs)

### 2c. Group reply mechanics — REQUIRED, or Bernard receives but can't answer

wikicare **denies the `message` tool** (egress containment — keep it denied).
But `messages.groupChat.visibleReplies: "message_tool"` makes group output
*require* that tool → Bernard would go silent in groups. Fix at the top-level
`messages` block (least-privileged — no new tool exposure):

```json5
messages: {
  ackReactionScope: "group-mentions",
  groupChat: {
    visibleReplies: "automatic",      // was "message_tool"; mentioned replies post directly
    unmentionedInbound: "room_event", // unaddressed chatter = quiet context → Bernard stays silent
    mentionPatterns: ["bernard"],     // case-insensitive text trigger (backs up native @-mention)
  },
}
```

`messages.groupChat` is **global** — `unmentionedInbound: "room_event"` and
`visibleReplies: "automatic"` also apply to `main` in Telegram groups (main can
use the `message` tool, so it's unaffected functionally; it just posts normal
text). Net: **mentioned → Bernard answers; unmentioned → silent.**

## 3. Routing — WhatsApp → wikicare, everything else unchanged

```json5
bindings: [
  { agentId: "wikicare", match: { channel: "whatsapp" } },
  { agentId: "main",     match: { channel: "telegram" } },  // make explicit
]
```

## 4. Tool restriction for wikicare

Per-agent tool policy: deny everything except filesystem reads and exec of the
publish script. At minimum mirror the global denies and add: no web fetch, no
cron management, no email/gog, no access outside `~/health-wiki-workspace`,
`~/health-wiki-mirror`, `/tmp`, and `~/briefs`. Exact mechanism (sandbox profile
vs `tools.allow/deny` per agent) depends on installed version — check
`openclaw config schema agents` and prefer the strictest available.

## 5. Exec sandbox for wikicare — LIVE as of 2026-06-12

OpenClaw embeds `@openclaw/fs-safe` for its file tools; Bernard's `exec` runs
in a per-agent Docker container. The deployed, verified config:

```json5
sandbox: {
  mode: "all",
  scope: "agent",                 // one persistent container per agent
  workspaceAccess: "rw",
  workspaceRoot: "/home/lashaws/health-wiki-workspace",
  docker: {
    image: "wikicare-sandbox:py313",   // python:3.13-slim + /usr/bin/python3 symlinks
                                       // (host venv expects /usr/bin/python3.13)
    readOnlyRoot: true,
    network: "none",
    user: "1001:1001",
    capDrop: ["ALL"],
    tmpfs: ["/tmp"],
    pidsLimit: 256,
    memory: "1g",
    env: { HOME: "/home/lashaws", MPLCONFIGDIR: "/tmp/mpl",
           PATH: "/home/lashaws/health-wiki-workspace/.venv/bin:/usr/local/bin:/usr/bin:/bin" },
    binds: [
      "/home/lashaws/health-wiki-mirror:/home/lashaws/health-wiki-mirror:ro",   // hard-enforced read-only
      "/home/lashaws/health-wiki-workspace:/home/lashaws/health-wiki-workspace:rw" // same paths in+out of container → MEDIA paths resolve on host
    ],
    dangerouslyAllowExternalBindSources: true,  // required for the two binds above; both are ours
  },
}
```

Hard-won operational notes:
- **Gateway needs the docker group.** The systemd user manager predates
  `usermod -aG docker`, so `openclaw-gateway.service.d/docker-group.conf` wraps
  ExecStart in `sg docker -c "..."`. Drop that file after the next server reboot.
- **`scope: agent` containers survive gateway restarts.** After ANY change to
  `sandbox.docker.*`, `docker rm -f <openclaw-sbx-agent-wikicare-*>` or the old
  mounts persist.
- **The codex harness does NOT inject workspace `AGENTS.md` in sandbox mode**
  (IDENTITY/SOUL/TOOLS/USER + skills still load). All operative behavior rules
  (chart workflow, briefs-not-/tmp, search discipline) therefore live in
  **TOOLS.md** — keep AGENTS.md and TOOLS.md in sync when editing rules.
- **`/tmp` is container-local tmpfs**: a `MEDIA: /tmp/...` reply cannot be
  attached by the gateway. All attachments must land under
  `~/health-wiki-workspace/briefs/` (rw bind → host-visible).

Verified 2026-06-12: chart request end-to-end in 31 s via `make_chart.py` (3 tool
calls); `cat ~/.openclaw/openclaw.json` inside the container → No such file;
`touch` on the mirror → Read-only file system; PNG lands on host in `briefs/`.

## 6. Verify

- `openclaw doctor` → no config errors
- restart gateway → Telegram ping still routes to `main`
- WhatsApp from the allowlisted number → `wikicare` answers
- WhatsApp from any other number → silence (pairing/allowlist rejection in logs)

## 7. Daily score summaries — gateway crons + sandbox matplotlib (curator applies)

> **✅ APPLIED 2026-07-04 (curator-authorized session).** matplotlib 3.11.0 committed
> into `wikicare-sandbox:py313` (rollback tag `wikicare-sandbox:py313.bak-daily-score`;
> CMD preserved through the commit; verified importable under `--network none`).
> Native gateway crons created (`openclaw cron`): `daily-score-brief`
> (`12da5d1c-4c3f-41db-942c-30b9e0a02b18`, 07:30 America/Denver daily) and
> `weekly-score-deepdive` (`834064ef-4a57-44bc-b897-d62b0ef8e3ad`, Sun 18:00
> America/Denver), both `--announce → whatsapp → group JID`, agent session isolated,
> wikicare tool denies untouched. First live run delivered to the group 2026-07-04
> (`delivered: true`, fallback announce path as designed) and logged in the
> conversation log in parseable format. Ad-hoc sandbox charting verified (June chart,
> correct stats). The systemd-timer fallback below was NOT needed.

**CURATOR APPLIES — VPS data-flow rule; two new scheduled outbound messages to
the already-locked family group, no other surface change.**

### 7a. Sandbox matplotlib (the per-agent Docker image, §5)

Bernard's exec runs in the `wikicare-sandbox:py313` image (§5). Add
matplotlib to that image — check what the installed OpenClaw version
documents for extending the sandbox image before hand-editing:

- If a Dockerfile/requirements file backs the image, add `matplotlib` there
  and rebuild: `docker build -t wikicare-sandbox:py313 .` (or the equivalent
  build command for the installed version).
- Tag-back the current image before rebuilding so rollback is a re-tag, not a
  rebuild: `docker tag wikicare-sandbox:py313 wikicare-sandbox:py313.bak-daily-score`.
- `scope: agent` containers persist across gateway restarts (per §5's
  existing note) — after rebuilding, `docker rm -f
  <openclaw-sbx-agent-wikicare-*>` so the next exec turn picks up the new image.

Verify (either from the host or as a wikicare exec turn):
```bash
docker exec <openclaw-sbx-agent-wikicare-*> python3 -c "import matplotlib; print(matplotlib.__version__)"
```

Rollback:
```bash
docker tag wikicare-sandbox:py313.bak-daily-score wikicare-sandbox:py313
docker rm -f <openclaw-sbx-agent-wikicare-*>
```

Data-flow framing (per the VPS data-flow rule): this is render-only —
matplotlib reads the already-mirrored, read-only CSV
(`daily-symptom-scores.csv`, bound `ro` per §5) and writes a PNG to the
already-rw `briefs/` bind. `network: "none"` and every existing bind stay
untouched — no new network surface, no new bind, no new tool grant.

### 7b. Daily brief cron (~07:30 America/Denver, after the 07:00 mirror sync)

A **gateway-level** scheduled job — NOT a wikicare tool grant (wikicare's
cron deny from §4 stays denied) — that runs the equivalent of:

```bash
openclaw agent --agent wikicare --deliver --channel whatsapp \
  --to "<FAMILY-GROUP-JID>@g.us" \
  --message "Compose today's family summary from wikis/health/personal-tracking/wiki/daily-symptom-score.md in the mirror: 2–4 sentences — latest daily symptom score (explain: higher = worse, vs her own past year), 7-day vs 30-day direction, top symptom drivers, and the Data-through date. If the Data-through date is more than 7 days old, instead post one line noting no fresh data since that date. Do not give advice."
```

(exact delivery flags depend on the installed version — confirm per §7d.)

> `<FAMILY-GROUP-JID>` = the family WhatsApp group's numeric JID. Not written
> here (long digit strings trip the leak-scan account tripwire, 2026-07-07
> triage); read it from the deployed crons on the VPS: `openclaw cron list`,
> or the gateway journal's `@g.us` session ids.

### 7c. Weekly deep-dive cron (Sunday ~18:00 America/Denver)

Same mechanism as 7b, targeting the same group JID, fixed prompt:

```bash
openclaw agent --agent wikicare --deliver --channel whatsapp \
  --to "<FAMILY-GROUP-JID>@g.us" \
  --message "Compose this week's family deep-dive from wikis/health/personal-tracking/wiki/daily-symptom-score.md in the mirror: this week vs the prior week, per-domain trends (from the page's domain table), notable movers, this month's context, and the Data-through date. Attach charts/score-30d.png as a chart. If the Data-through date is more than 7 days old, instead post one line noting no fresh data since that date. Do not give advice."
```

Attach `wikis/health/personal-tracking/wiki/charts/score-30d.png` (the
mirror-root-relative path from TOOLS.md) as media on this one, same staleness
rule as 7b.

### 7d. Cron mechanism — check the installed version, then pick

Exact cron/schedule syntax depends on the installed OpenClaw version. Before
writing anything:
```bash
openclaw cron --help
openclaw config schema     # look for a cron/scheduled-job block
```
- **If native scheduling exists**: add two entries, one per 7b/7c, each
  firing the fixed `openclaw agent --agent wikicare ... --deliver` invocation
  above. Back up first — same convention as §1's config edits:
  `cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.bak-daily-score`,
  then `chmod 600 ~/.openclaw/openclaw.json.bak-daily-score` (the backup
  carries the full agent/channel config, same sensitivity as the live file).
- **Fallback** (the plain-systemd-timer pattern verified 2026-06-26 elsewhere
  in this doc): a user systemd `.service` + `.timer` pair per cron, each
  shelling out to the same `openclaw agent --agent wikicare --deliver ...`
  command, `OnCalendar=*-*-* 07:30` (daily) and `OnCalendar=Sun *-*-* 18:00`
  (weekly) — set `Environment=TZ=America/Denver` in the unit or confirm host
  TZ already matches.

Verify:
- First scheduled post lands in the family group at the
  expected time, with the freshness line present.
- Gateway log (or `journalctl --user -u <timer-name>` for the systemd
  fallback) shows the invocation and a successful delivery.
- No other group or DM receives the message — the JID is hardcoded to the
  one locked group (§2b), not derived from any broader match.

Rollback:
- Native cron: remove the two entries from `openclaw.json`, restore from
  `openclaw.json.bak-daily-score` if needed, restart the gateway.
- systemd fallback: `systemctl --user disable --now <timer-name>.timer && rm
  ~/.config/systemd/user/<timer-name>.{service,timer} && systemctl --user
  daemon-reload`.
