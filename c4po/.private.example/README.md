# Private context example

Synthetic templates for C4PO's git-ignored `.private/` directory. This directory
is public and must stay synthetic — no real path, hostname, credential, or
artifact name belongs in it.

- `memory-inventory.example.yaml` → copy to `.private/memory-inventory.yaml`.
  The private overlay of the long-term memory inventory: records for durable
  memory artifacts whose path or rationale is itself sensitive, and which
  therefore must not appear in the tracked `MEMORY-INVENTORY.yaml`. Validate it
  with `python3 .bin/build-memory-inventory.py validate --overlay
  c4po/.private/memory-inventory.yaml`. See
  `c4po/LONG-TERM-MEMORY-INVENTORY-DESIGN.md` for the architecture.
