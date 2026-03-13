# Test Contracts

This file defines the minimum checks to run after changing report, pull, ingest, or data-contract logic.

## 1. Report regression

Script:

- `scripts/test_harmonix_report.py`

This must verify:

- position rows render all required economics fields
- `amount_usd` and `open_fees_usd` survive registry load
- 1d / 2d / 3d / 15d funding windows are computed correctly
- breakeven becomes `n/a` when average funding is non-positive
- rotation analysis computes close cost, open cost, switch cost, and switch breakeven
- Hyperliquid namespaced perps resolve to correct Loris exchange keys:
  - `xyz -> tradexyz`
  - `flx -> felix`
  - `km -> kinetiq`
  - `hyna -> hyena`
- carry lookup works from:
  - latest Loris CSV row
  - historical Loris CSV window
  - net-series smoothing path

## 2. Loris ingest regression

Scripts:

- `scripts/test_pull_loris_exchange_filters.py`
- `scripts/test_pull_loris_backfill_history.py`

These must verify:

- exchange alias normalization works for config inputs like `xyz`, `HL`, `tradexyz_perp`
- normalized target exchanges include:
  - `hyperliquid`
  - `tradexyz`
  - `felix`
  - `kinetiq`
  - `hyena`
- historical timestamps ending in `Z` parse correctly as UTC
- OI-rank filtering still keeps missing-rank rows and drops clearly out-of-range rows

## 3. Funding sign and private ingest regression

Scripts:

- `scripts/test_hyperliquid_cashflows.py`
- `scripts/test_funding_sign_convention.py`

These must verify:

- Hyperliquid `userFunding` sign is stored using account-PnL sign directly
- no extra flip is applied for short perps
- builder-dex namespaced perps ingest under the correct `dex + coin`
- fees remain negative cashflows

## 4. Smoke checks after runtime changes

When changing production-facing scripts, run these smoke checks:

```bash
python3 -m py_compile \
  scripts/report_daily_funding_with_portfolio.py \
  scripts/pull_loris_funding.py \
  scripts/pull_loris_backfill_history.py \
  scripts/pm_cashflows.py
```

```bash
python3 scripts/test_harmonix_report.py
python3 scripts/test_pull_loris_exchange_filters.py
python3 scripts/test_pull_loris_backfill_history.py
```

If private env is available, also run:

```bash
source .arbit_env
.venv/bin/python scripts/pull_loris_funding.py
.venv/bin/python scripts/report_daily_funding_with_portfolio.py --top 5
```

## 5. Acceptance criteria by change type

### If changing report formatting or economics

Must re-check:

- field names and section order
- advisory reasons
- breakeven math
- rotation analysis output

### If changing Loris ingest or exchange mapping

Must re-check:

- alias normalization
- builder-dex exchange mapping
- latest live pull contains expected exchanges
- carry no longer reports false `missing funding data`

### If changing registry or DB sync

Must re-check:

- `amount_usd` survives JSON -> PM DB sync
- `open_fees_usd` survives JSON -> PM DB sync
- `qty` remains base-unit sized in PM legs

## 6. Non-goals for current tests

The current minimum regression suite does not guarantee:

- exact Telegram delivery behavior
- cron correctness on the host machine
- perfect venue fee truth for every exchange
- candidate ranking on builder-dex exchanges

Those require separate operational tests.
