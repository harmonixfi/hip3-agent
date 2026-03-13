# Report Scripts Spec

## Primary script

- `scripts/report_daily_funding_with_portfolio.py`

Purpose:

- render one daily report section at a time
- emit machine-readable section status on `stderr`
- preserve on-demand rotation-cost analysis

## CLI contract

Supported flags:

- `--db <path>`
- `--section portfolio-summary|rotation-general|rotation-equities`
- `--top <n>`
- `--oi-max <n>`
- `--rotate-from <position_id|ticker>`
- `--rotate-to <symbol>`

Rules:

- `--section` and `--rotate-from/--rotate-to` are mutually exclusive
- omitting both section mode and rotation mode is invalid
- `--equities` is rejected
- `--top` must be `>= 1`

## Section commands

Examples:

```bash
.venv/bin/python scripts/report_daily_funding_with_portfolio.py --section portfolio-summary
.venv/bin/python scripts/report_daily_funding_with_portfolio.py --section rotation-general --top 10
.venv/bin/python scripts/report_daily_funding_with_portfolio.py --section rotation-equities --top 10
```

Section output contract:

- `stdout`: section body only
- `stderr`: single JSON status line
- exit `0`: rendered `NORMAL` or `DEGRADED`
- non-zero exit: hard failure
- ranked and flagged rotation rows identify candidates by `symbol` plus `venue`

## Daily section order

The upstream agent should assemble sections in this order:

1. `Portfolio Summary`
2. `Top 10 Rotation Candidates - General`
3. `Top 10 Rotation Candidates - Equities`

`Rotation Cost Analysis` is not a required daily block.

## Rotation analysis mode

On-demand only:

```bash
.venv/bin/python scripts/report_daily_funding_with_portfolio.py --rotate-from GOLD --rotate-to BTC
```

This prints:

- source position id and ticker
- target symbol
- `amount_usd`
- close fees
- open fees
- total switch cost
- expected daily funding
- switch breakeven time
- candidate APR metrics and stability score
