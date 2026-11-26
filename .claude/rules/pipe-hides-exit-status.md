---
name: pipe-hides-exit-status
description: "When a check's pass/fail matters (validators, audits, coverage gates, tests): $? after `cmd | tail` is tail's status, not the check's. Send the output to a file and read the command's own exit status."
---
# `$?` after a pipe is the last command's

`check 2>&1 | tail -3; echo "exit=$?"` prints tail's status, which is
almost always 0. On 2026-11-22 a session told the user "both inventory
checks pass" this way when `discover --require-coverage` had exited 1; on
2026-11-21 a dossier `audit` printed "exit 0" under its own error.

When the result decides whether a gate passed:

- Send the output to a file, then read the status:
  `cmd > "$T" 2>&1; echo "exit=$?"; tail -20 "$T"`.
- Or start the line with `set -o pipefail`, or read `${pipestatus[1]}`
  (zsh; `${PIPESTATUS[0]}` in bash).
- A gate that exited non-zero did not pass, even when another agent's
  files caused the failure. Report it as failed and say why.
