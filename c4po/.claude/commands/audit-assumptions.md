---
description: Run the memory-governance audit interactively; optionally apply only verified auto-safe repairs.
---

Run the monthly memory-governance and assumptions audit interactively. Same
audit logic as the launchd job `com.theborg.c4po-assumptions-audit-monthly`,
executed here in the session instead of on a schedule — no duplicated
instructions.

Read and follow the instructions in
`${BORG_ROOT}/c4po/.claude/scheduled/c4po-assumptions-audit-monthly.prompt`.
Treat every occurrence of `${BORG_ROOT}` in that file as the repo root — the
output of `git rev-parse --show-toplevel` (the `theborg` directory).

Six overrides for interactive invocation:
1. Skip **STAGE 1 — GATE** entirely — do not check the state file. An interactive run
   should always execute, regardless of whether the scheduled job already ran
   this month.
2. In **STAGES 2-6**, private paths and contents may be inspected when needed
   because the result stays in this user-visible session. Keep private material
   out of tracked files, generated public snapshot data, and unrelated tool
   output; do not reveal more than the review requires.
3. In **STAGE 5 — SELECT**, the user may request a larger or narrower candidate
   cohort. Otherwise keep the scheduled run's bounded selection policy.
4. In **STAGE 9 — REPORT**, do NOT pipe to `notify-email.sh`. Instead, output the report
   directly into this session, including assumptions that are STILL VALID, so
   the run is legible.
5. Never write the monthly gate state. Without `--apply`, skip **STAGE 10 —
   RECORD GENERATED STATE** entirely. With `--apply`, the candidate public
   snapshot may be included in the verified transaction described below; it
   still must not make the gate state claim scheduled completion.
6. Treat `--apply` as an exact opt-in. Without it, remain report-only. With it,
   finish discovery, validation, review, and remediation planning successfully
   before any write. `propose_patch`, `approval_required`, and `prohibited`
   actions retain their report-only behavior.

For `--apply`, create a unique work directory under `${BORG_ROOT}/tmp/`, write
the validated candidate snapshot there, then use only the deterministic gate:

```sh
python3 ${BORG_ROOT}/.bin/apply-memory-audit.py \
  --root ${BORG_ROOT} plan \
  --candidate-snapshot tmp/<run>/memory-inventory.json \
  --output ${BORG_ROOT}/tmp/<run>/auto-safe-plan.json
python3 ${BORG_ROOT}/.bin/apply-memory-audit.py \
  --root ${BORG_ROOT} apply \
  --plan ${BORG_ROOT}/tmp/<run>/auto-safe-plan.json \
  --receipt ${BORG_ROOT}/tmp/<run>/auto-safe-receipt.json
```

The helper derives bridges from unchanged canonical sources, updates their
existing managed-manifest entries, requires public inventory records whose
effective remediation policy is `auto_safe`, permits the privacy-scanned
snapshot/review ledger at its one generated-state path, prints the exact
proposed diffs, verifies the written bytes, and refuses every other target or
action kind. It never creates or deletes a target. Report each action as applied
or refused and retain the work directory so rollback remains available:

```sh
python3 ${BORG_ROOT}/.bin/apply-memory-audit.py \
  --root ${BORG_ROOT} rollback \
  --receipt ${BORG_ROOT}/tmp/<run>/auto-safe-receipt.json
```

Do not run either bridge's broad sync mode from this audit: orphan removal is a
deletion and therefore remains `approval_required`. The scheduled prompt stays
report-only and must never invoke this helper.
