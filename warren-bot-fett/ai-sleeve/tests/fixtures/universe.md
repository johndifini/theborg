# Fixture universe for rebalance.py tests (synthetic tickers and caps)

## Tunables

```yaml
basket_size: 6
floor_pct: 5.0
ticker_floors: {LOWB: 4.0}   # per-ticker override
```

## Categories

```categories
giants:
  members: [AAA, BBB, CCC, DDD]

mid:
  members: [EEE, FFF, DDD]

power:
  members: [PWR1, PWR2, PWRX]
  min: 2

tiny:
  members: [LOWA, LOWB]
  min: 1
```

## Soft excludes (this month)

```soft_excludes
PWRX      # excluded for the test
FFF       # excluded for the test
```
