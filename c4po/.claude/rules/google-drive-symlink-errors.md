---
name: google-drive-symlink-errors
description: "When Google Drive for Desktop reports sync errors on ~/theborg: they are symlinks, they are expected and permanent, and the .env entry is not a secrets leak. Do not 'fix' them by replacing tracked symlinks with real files."
---
# Drive's ~/theborg sync errors are symlinks, and they are supposed to be there

`~/theborg` is an intentional Drive **mirror** sync root. Drive's backend
rejects symlinks at upload time, so it reports an error for each one, and
that error list is persisted state — it does not clear on its own after the
cause is gone.

Two distinct error classes, which look like one problem in the dialog:

| Class | Cause |
|---|---|
| `UNSUPPORTED` on `UploadCreate` | any symlink |
| `FAILED_PRECONDITION: Is a directory` | a symlink pointing at a directory |

**Do not chase a specific error count.** It drifts as symlinks come and go —
it was 13 on 2026-08-30 and 16 by 2026-09-02. Enumerate the real cause
instead, and note that Drive does not honor `.gitignore`, so `repos/` and
`node_modules/` are synced too:

    find ~/theborg -type l

Expected permanent entries:

- 11 x `cerebruh/wikis/*/AGENTS.md` -> `../../template/AGENTS.md`. Required
  by `LINT.md`. **Never** replace these with real files to quiet Drive.
- `.env` -> `~/.borg-secrets/.env`.
- `<project>/.claude/commands` directory symlinks — currently
  `repos/waiq/` and `ari/career-dossier/`. Leave them; deleting one breaks
  that project's commands.
- `node_modules/.bin/*` in any JS project (npm creates these).

**The `.env` entry is not a leak.** Drive failed it with `UNSUPPORTED` on
`UploadCreate` — it rejected the item as an unsupported type rather than
resolving the link and uploading `~/.borg-secrets/.env`. Verified against
Drive's own logs on 2026-08-30, not inferred. Do not escalate it as an
exfiltration event.

What *is* worth acting on is a rising count from a source that should not be
there — usually Swift build caches under `tmp/` (`waiq-*-build`,
`.swiftpm/cache`, derived data). Those are safe to delete once no process
holds them; on 2026-08-30 clearing them took `tmp/` from 719M to 3.7M.

Confirm against Drive's own log rather than the dialog, which lags:

    grep -ohE 'UNSUPPORTED|FAILED_PRECONDITION' \
      ~/Library/Application\ Support/Google/DriveFS/Logs/drive_fs.txt | sort | uniq -c
