# AI Sleeve — Candidate Universe

Curated set of names for the AI sleeve, organized by theme. The monthly rebalance derives the active candidate set from the union of all category `members`, drops anything in `soft_excludes`, then ranks by total market cap and takes the top N (where N = `basket_size`). Categories with a `min` value enforce minimum representation — shortfall categories displace the lowest-cap unconstrained name. Categories without `min` are thematic groupings only. Names below their floor get pinned at the floor; names above absorb the residual pro-rata by market cap. Each name's floor is the global `floor_pct` unless overridden by a per-ticker entry in `ticker_floors`.

Edit this file freely between runs. To temporarily exclude a name, move it to `soft_excludes` with a one-line note.

## Charter — what belongs

This sleeve targets picks-and-shovels of the AI compute buildout: suppliers of chips, memory, power, networking, datacenters, and the equipment/materials behind them. AI *adopters* — firms that merely deploy AI to widen their own margins (banks, insurers, consultancies, most application software) — are off-profile and admitted sparingly if at all: a name earns a slot by supplying the buildout, not by using AI. When an off-profile name is added on owner instruction, keep its category deliberately thin and give it no `min`, so it must re-earn its basket slot on market cap every month.

## Tunables

```yaml
basket_size: 17
floor_pct: 2.0
ticker_floors: {}   # FLKR proxy retired 2026-07-14 — SK Hynix now held directly via SKHY, which competes on market cap
```

## Categories

```categories
hyperscalers:
  members: [MSFT, GOOGL, AMZN, META, ORCL, SPCX]

ai_neoclouds:
  members: [CRWV, NBIS, IREN]
  min: 1

chip_designers:
  members: [NVDA, AMD, AVGO, MRVL, QCOM, INTC, ARM, CBRS]

foundry_semicap:
  members: [TSM, ASML, AMAT, LRCX, KLAC, INTC, Q]

networking_and_systems:
  members: [ANET, DELL, NOK, CSCO, HPE]

memory:
  members: [MU, SKHY]
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

datacenter_reits:
  members: [EQIX, DLR]
```

## Soft excludes (this month)

```soft_excludes
IBM       # watsonx narrative weak; revisit if AI-revenue mix improves
SMCI      # auditor resignation / governance overhang from late 2024 not fully resolved
CEG       # existing nuclear fleet — unconvinced it can scale with AI demand pace
VST       # legacy gas/coal/nuclear mix — unconvinced it can scale with AI demand pace
OPENAI    # pending IPO — at listing, replace placeholder with real ticker, add to a new frontier_labs category, then remove this line
ANTHROPIC # pending IPO — at listing, replace placeholder with real ticker, add to a new frontier_labs category, then remove this line
```

## Inclusion theses (notes for monthly review)

- **AAPL** — Mac demand for running local AI tools (e.g., Mac Minis for inference workloads). Reevaluate if Mac unit growth stalls.
- **TSLA** — FSD, robotaxi, Optimus. Reevaluate if AI-driven product roadmap slips materially.
- **CAT** — heavy equipment for hyperscaler data center construction. Picks-and-shovels of the buildout.
- **GLW** — fiber-optic glass for AI data center connectivity.
- **SNDK / STX / WDC** — NAND and HDD storage demand from AI workloads.
- **MU** — DRAM/HBM supplier for GPU memory; principal beneficiary of HBM3/HBM4 ramp. Forced in via `memory` constraint.
- **SKHY** — SK Hynix, Nasdaq ADR (listed 2026-07-10; traded as SKHYV during the when-issued period, converting to SKHY ~2026-07-15). HBM market leader (HBM3E/HBM4) and lead memory supplier to NVIDIA; with MU this gives the sleeve direct HBM exposure. **Replaced the FLKR Korea-ETF proxy on 2026-07-14 per owner instruction** — MU + SK Hynix are deemed sufficient HBM exposure, so the ETF proxy (and its `ticker_floors` pin) is retired. Unlike FLKR, SKHY is a large-cap that competes into the basket on market cap; the `memory` min:2 remains as a safety guarantee. Reevaluate if HBM pricing/share erodes materially. **Samsung note:** Samsung Electronics is no longer represented in the sleeve — it has no US exchange listing (only the London-listed unsponsored GDR/ADR SMSN as of 2026-07-14). Per owner instruction, add Samsung to the universe if and when it lists a US ADR.
- **BE** — fuel cells for on-site/distributed power at AI data centers; complements GEV (grid + turbines) when grid interconnection wait times are the binding constraint. Forced in via `power_generation` constraint.
- **INTC** — x86 CPU franchise plus Intel Foundry buildout. Dual-listed in `chip_designers` and `foundry_semicap` to reflect IDM model. Reevaluate if foundry roadmap slips materially.
- **Q** — Qnity Electronics, DuPont's electronics-materials spin-off (NYSE, S&P 500 from 2025-11-01). Semiconductor and interconnect materials — picks-and-shovels of chip fabrication, levered to AI-driven wafer demand. Reevaluate if semiconductor materials growth decouples from AI capex.
- **ARM** — IP licensor; royalties scale with every AI-capable mobile/edge SoC and increasingly with datacenter Arm-based silicon (Graviton, Grace).
- **CRWV / NBIS** — neocloud GPU-rental capacity; complements hyperscalers when GPU supply is the binding constraint. Forced in via `ai_neoclouds` min.
- **IREN** — vertically integrated neocloud; ex-bitcoin miner (Iris Energy) that owns its power and data-center sites, a structural cost edge over GPU-only renters. Distant third in the public pure-play tier (~$17B cap vs. CRWV/NBIS at $50B+). Reevaluate if the AI-cloud pivot stalls or it reverts toward crypto-mining economics.
- **SPCX** — SpaceX (IPO'd 2026-06-12). **Reclassified to `hyperscalers` 2026-06-27** (was `ai_neoclouds`): the Feb 2026 xAI acquisition brought in Colossus 1 (~220K NVIDIA GPUs) and Grok, and SpaceX is now leasing frontier-scale compute — Anthropic ~$1.25B/mo, Google ~$920M/mo (~110K GPUs from Oct 2026), plus Reflection — ~$76B through 2029 (~$25B/yr, exceeding Starlink + launch + AI combined). Owns the fleet *and* a frontier model it serves: the vertically integrated own-the-infra profile of META/GOOGL/ORCL, not the rent-a-GPU neocloud profile of CRWV/NBIS. Starlink connectivity and the AI1 orbital-datacenter constellation are upside optionality, not the core compute thesis. Reevaluate if the compute-leasing contracts fail to renew past 2029 or orbital economics prove uneconomic.
- **NOK** — optical and data-center networking gear (IP routing, optical transport) for AI buildout interconnect; complements ANET on the systems side. Reevaluate if AI-driven networking demand fails to offset legacy telco-capex softness.
- **CSCO** — data-center switching/routing and optics for AI fabric; Ethernet-for-AI positioning against ANET. Reevaluate if AI orders fail to offset legacy campus-networking softness.
- **HPE** — AI servers (ProLiant, Cray AI supercomputers) and GreenLake consumption infrastructure, plus networking from Aruba and the Juniper acquisition. Reevaluate if AI systems demand fails to offset legacy compute/storage softness or Juniper integration stalls.
- **EQIX** — datacenter REIT; retail colocation + interconnection. Moat is network density at its IBX hubs (carrier/cloud clustering → high switching costs). Levered to AI inference/edge where low-latency interconnect matters.
- **DLR** — datacenter REIT; wholesale/hyperscale capacity leased to the hyperscalers (MSFT/GOOGL/AMZN/META). More direct hyperscaler-capex leverage than EQIX, but more exposed to supply gluts and power-availability constraints.
