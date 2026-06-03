# AI Sleeve — Candidate Universe

Curated set of names for the AI sleeve, organized by theme. The monthly rebalance derives the active candidate set from the union of all category `members`, drops anything in `soft_excludes`, then ranks by total market cap and takes the top N (where N = `basket_size`). Categories with a `min` value enforce minimum representation — shortfall categories displace the lowest-cap unconstrained name. Categories without `min` are thematic groupings only. Names below their floor get pinned at the floor; names above absorb the residual pro-rata by market cap. Each name's floor is the global `floor_pct` unless overridden by a per-ticker entry in `ticker_floors`.

Edit this file freely between runs. To temporarily exclude a name, move it to `soft_excludes` with a one-line note.

## Tunables

```yaml
basket_size: 17
floor_pct: 2.0
ticker_floors:
  FLKR: 2.0   # Korea-ETF proxy for Samsung/SK Hynix — pin until they list US ADRs
```

## Categories

```categories
hyperscalers:
  members: [MSFT, GOOGL, AMZN, META]

datacenter:
  members: [CRWV, ORCL]

ai_neoclouds:
  members: [CRWV, NBIS]
  min: 1

chip_designers:
  members: [NVDA, AMD, AVGO, MRVL, QCOM, INTC, ARM, CBRS]

foundry_semicap:
  members: [TSM, ASML, AMAT, LRCX, KLAC, INTC]

networking_and_systems:
  members: [ANET, DELL, NOK]

memory:
  members: [MU, FLKR]
  min: 2

storage:
  members: [SNDK, STX, WDC]
  min: 1

dc_physical_infra:
  members: [CAT, GLW, VRT]

power_generation:
  members: [GEV, BE, CEG, VST]
  min: 2

ai_devices:
  members: [AAPL]

world_models:
  members: [TSLA]
```

## Soft excludes (this month)

```soft_excludes
IBM       # watsonx narrative weak; revisit if AI-revenue mix improves
SMCI      # auditor resignation / governance overhang from late 2024 not fully resolved
CEG       # existing nuclear fleet — unconvinced it can scale with AI demand pace
VST       # legacy gas/coal/nuclear mix — unconvinced it can scale with AI demand pace
OPENAI    # pending IPO — at listing, replace placeholder with real ticker, add to a new frontier_labs category, then remove this line
ANTHROPIC # pending IPO — at listing, replace placeholder with real ticker, add to a new frontier_labs category, then remove this line
SPACEX    # pending IPO — at listing, replace placeholder with real ticker, add to the same category(ies) as CRWV (datacenter, ai_neoclouds), then remove this line
```

## Inclusion theses (notes for monthly review)

- **AAPL** — Mac demand for running local AI tools (e.g., Mac Minis for inference workloads). Reevaluate if Mac unit growth stalls.
- **TSLA** — FSD, robotaxi, Optimus. Reevaluate if AI-driven product roadmap slips materially.
- **CAT** — heavy equipment for hyperscaler data center construction. Picks-and-shovels of the buildout.
- **GLW** — fiber-optic glass for AI data center connectivity.
- **SNDK / STX / WDC** — NAND and HDD storage demand from AI workloads.
- **MU** — DRAM/HBM supplier for GPU memory; principal beneficiary of HBM3/HBM4 ramp. Forced in via `memory` constraint.
- **FLKR** — Franklin FTSE South Korea ETF, held as a proxy for Samsung Electronics and SK Hynix (the HBM leaders) until they list US ADRs. Forced in via the `memory` min:2 constraint; ETF AUM ranks below the cap-ranked basket, so it relies on the constraint to enter and on its `ticker_floors` entry to pin a 2% weight. Replace with direct ADRs once available and drop this line.
- **BE** — fuel cells for on-site/distributed power at AI data centers; complements GEV (grid + turbines) when grid interconnection wait times are the binding constraint. Forced in via `power_generation` constraint.
- **INTC** — x86 CPU franchise plus Intel Foundry buildout. Dual-listed in `chip_designers` and `foundry_semicap` to reflect IDM model. Reevaluate if foundry roadmap slips materially.
- **ARM** — IP licensor; royalties scale with every AI-capable mobile/edge SoC and increasingly with datacenter Arm-based silicon (Graviton, Grace).
- **CRWV / NBIS** — neocloud GPU-rental capacity; complements hyperscalers when GPU supply is the binding constraint. Forced in via `ai_neoclouds` min.
- **NOK** — optical and data-center networking gear (IP routing, optical transport) for AI buildout interconnect; complements ANET on the systems side. Reevaluate if AI-driven networking demand fails to offset legacy telco-capex softness.
