# PORTFOLIO.md — Portfolio Manager Long-Term Memory

> Template. Copy to `PORTFOLIO.md` (gitignored) and replace the example
> values below with your own portfolios, accounts, and data source.
> The structure is what the scheduled jobs
> (`warren-bot-fett-daily-market-scan.prompt`,
> `warren-bot-fett-ai-sleeve-monthly.prompt`) expect to find.

## EXAMPLE-TRUST

**Structure:** Irrevocable trust, <STATE> law, established <MONTH YEAR>. Settlor deceased <MONTH YEAR>. Surviving spouse still living — trust terminates at their death.

**Owner's roles:** Co-Trustee, Trust Advisor, Co-Beneficiary.

**Tax framework:**
- No step-up in basis (no 706 filed, no estate inclusion)
- All current positions purchased by the trust (not transferred in-kind) — brokerage basis should be accurate
- Carryover basis to beneficiaries at termination
- Trust compressed brackets — tax efficiency is a priority
- At termination: assets distribute per stirpes to living children/descendants

**Investment authority:** Trust Advisor must approve sales/investments/exchanges (Article 7.4). Trustee has broad powers (Article 8). Owner wears both hats.

**Key constraint:** Low-frequency trading (~1 trade/week max per owner's preference). Tax-aware management critical given no step-up and compressed trust brackets.

---

## Asset Allocation Principles (All Portfolios)

### Equity/Bond Split (Age-Based Glide Path)
- **High Risk:** Equity % = 120 − age of youngest spouse/beneficiary
- **Medium Risk:** Equity % = 115 − age of youngest spouse/beneficiary
- Bond % = remainder (100 − Equity %)

### International/Domestic Splits
- **International Equity:** 25–30% of total equity (high risk → 30%, medium risk → 25%)
- **Domestic Equity:** remainder of equity bucket
- **International Bonds:** 20% of total bonds
- **Domestic Bonds:** 80% of total bonds

### Security Selection Rules
- **ETFs preferred**, mutual funds acceptable (lesser extent)
- **Individual equities OK** — including for tax-advantaged or alternative strategies
- **Individual bonds NOT allowed** — use bond ETFs/funds instead
- Freedom to choose tax-advantaged investments (e.g., muni ETFs for trust tax efficiency)
- Freedom to include alternative investments (REITs, commodities, etc.) via ETFs/equities

### Portfolio Participants & Risk
- **PORTFOLIO_A:** youngest born <YEAR> (age <N> in <YEAR>), risk 3.0 (high)
- **PORTFOLIO_B:** youngest born <YEAR> (age <N> in <YEAR>), risk 2.2
- **EXAMPLE-TRUST:** youngest beneficiary born <YEAR> (age <N> in <YEAR>), risk 2.5

Risk scale: 1–3 continuous. 2 = medium (factor 115, 25% int'l eq), 3 = high (factor 120, 30% int'l eq). Interpolate for fractional values. Int'l bonds = 20% at all levels.

### Current-Year Target Allocations
**PORTFOLIO_A** (factor 120, age <N>): Dom Eq <pct>% | Int'l Eq <pct>% | Dom Bonds <pct>% | Int'l Bonds <pct>%
**PORTFOLIO_B** (factor 116, age <N>): Dom Eq <pct>% | Int'l Eq <pct>% | Dom Bonds <pct>% | Int'l Bonds <pct>%
**EXAMPLE-TRUST** (factor 117.5, age <N>): Dom Eq <pct>% | Int'l Eq <pct>% | Dom Bonds <pct>% | Int'l Bonds <pct>%

*Recalculate annually as ages increment.*

## Asset Category Framework

Categories within asset classes are **tactical, not formulaic**. Priority order:

1. **Tax consequences** in taxable accounts (highest priority)
2. **Current market conditions**
3. **Diversification** across the following dimensions:

### Bond Diversification
**Duration:** Short | Intermediate | Long
**Quality:** Low (high-yield/junk) | Mid | High (investment-grade) | Treasury
- TIPS may be included at PM discretion for inflation protection

### Equity Diversification
**Capitalization:** Large | Mid | Small
**Style:** Value | Blend | Growth
**Sector/Industry:** Consider concentration risk across sectors (tech, healthcare, financials, etc.)

### Notes
- Factor exposure (momentum, quality, low-vol) — not in scope for now
- Muni bonds preferred in trust accounts for tax efficiency (compressed brackets)
- Category allocation is flexible and judgment-driven, unlike the rigid class allocation formula

## Portfolio Data Source
- Google Sheet CSV Export: `<paste-your-csv-export-url-here>`
- Contains all positions across all portfolios (PORTFOLIO_A, PORTFOLIO_B, EXAMPLE-TRUST)

### Accounts by Portfolio
**PORTFOLIO_A:** <acct> (Rollover IRA), <acct> (Brokerage), <acct> (Trad Non-deductible IRA), <acct> (Roth IRA), <acct> (Roth IRA), <acct> (Trad Non-deductible IRA), <acct> (Rollover IRA), 403b, 401k
**PORTFOLIO_B:** <acct> (Traditional IRA), <acct> (Traditional IRA), <acct> (Roth IRA), <acct> (Roth IRA), <acct> (Brokerage)
**EXAMPLE-TRUST:** <acct> (Irrevocable Trust)

## Rebalancing Parameters
- **Drift threshold:** 8% deviation in any asset class triggers alert
- **Trading cadence:** ~1 trade/week max per portfolio
- **Market data:** free sources only
- **Daily scan:** 9:00 AM local on trading days (Mon-Fri, skip market holidays)
- **Cron thinking level:** high

## Rebalancing Principles (Learned)
- **NEVER sell into a selloff.** If a position is down, that's not a reason to sell — it's a reason to hold or buy more.
- **High VIX = opportunity.** Elevated volatility means assets are on sale. Look for buying opportunities, not exits.
- **Rebalance by buying the underweight,** not by selling beaten-down overweight positions. Use cash or trim positions that are *elevated* relative to their history.
- **High-conviction holdings:** If you have a core holding you want to keep through drift, name it here and require a fundamental case before any sell recommendation. "Rebalancing drift" alone is never a sufficient reason.
- **Don't be a dumb algorithm.** Mechanical "drift → sell overweight" ignores market context. Think like an investor: buy low, sell high.
