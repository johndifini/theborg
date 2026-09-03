---
name: second-checkout-launchd-collision
description: "Before running .bin/install-scheduled-tasks.sh, confirm this checkout is the one that owns the com.theborg.* launchd namespace. A second checkout of The Borg shares that namespace and BORG_ROOT, and installing from it silently repoints every live scheduled job."
paths:
  - ".bin/install-scheduled-tasks.sh"
---
# Only one checkout may own com.theborg.*

The repo is fully relocatable — every script derives `BORG_ROOT` from its
own location and no executable path is hardcoded. What is not relocatable
is the machinery *outside* the checkout, which is keyed by name, not by
path:

- **launchd labels.** The installer writes
  `~/Library/LaunchAgents/com.theborg.<task>.plist`, label
  `com.theborg.<task>`. Two checkouts produce identical filenames and
  labels. Running the installer from the second one — *including bare
  no-flag write mode, which looks harmless* — overwrites every live plist
  and repoints the whole schedule at that tree.
- **`~/.zshenv:22`** exports `BORG_ROOT="${BORG_ROOT:-$HOME/theborg}"`. Any
  shell opened in a second checkout still resolves to `~/theborg` unless
  `BORG_ROOT` is exported explicitly, so scripts read the original
  workspace while you believe you are in the new one.
- **`~/.borg-secrets/.env`** is shared by both.

Before running the installer, confirm `git rev-parse --show-toplevel`
matches the tree whose jobs you intend to own, and that `$BORG_ROOT` agrees
with it. If it does not, stop — a second instance needs its label prefix
namespaced away from `com.theborg.*` before it is given any scheduled jobs
at all.

Also worth knowing about a fresh clone: most of the substance is gitignored.
`cerebruh/wikis/*`, every `.private/`, `.env`, `repos/*`, `*.local.md`
rules, `settings.local.json`, and `.private/scheduled-tasks/*.tasks` (which
the installer itself reads) do not come along.
