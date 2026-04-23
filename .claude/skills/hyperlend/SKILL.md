---
name: hyperlend
description: Use when analyzing Hyperlend lending/borrowing rates, comparing lending yield vs funding rates, checking pool parameters, or reviewing historical rate trends on HyperEVM. Also use when evaluating capital allocation between lending and perp funding strategies.
---

# Hyperlend Rate Data

CLI tool at `.claude/skills/hyperlend/hyperlend.py` fetches lending/borrowing data from Hyperlend (Aave V3 fork on HyperEVM). All output is JSON for programmatic use.

## Commands

### Current rates (supply/borrow APR/APY)

```bash
python3 .claude/skills/hyperlend/hyperlend.py rates                          # all pools
python3 .claude/skills/hyperlend/hyperlend.py rates --tokens USDC,HYPE,USDT  # filtered
python3 .claude/skills/hyperlend/hyperlend.py rates --raw                    # skip symbol resolution (faster)
python3 .claude/skills/hyperlend/hyperlend.py rates --address 0x...          # include user positions
```

Returns `supply_apr`, `supply_apy`, `borrow_apr`, `borrow_apy` as percentages. Pools tagged `core` or `isolated`.

### User positions (supply/borrow balances)

```bash
python3 .claude/skills/hyperlend/hyperlend.py rates --address 0x...
python3 .claude/skills/hyperlend/hyperlend.py markets --address 0x...
```

Queries HyperLend Pool contract on HyperEVM via `eth_call`. Returns per-token supplied/borrowed amounts plus overall account summary (`total_collateral_usd`, `total_debt_usd`, `health_factor`). Only tokens with non-zero balances are returned. Uses `ProtocolDataProvider.getUserReserveData` for per-asset balances and `Pool.getUserAccountData` for USD totals.

### Market parameters (risk config, caps, LTV)

```bash
python3 .claude/skills/hyperlend/hyperlend.py markets                            # all
python3 .claude/skills/hyperlend/hyperlend.py markets --tokens USDC,wstHYPE,kHYPE
python3 .claude/skills/hyperlend/hyperlend.py markets --address 0x...            # include user positions
```

Returns `ltv_bps`, `liquidation_threshold_bps`, `reserve_factor_bps`, `supply_cap`, `borrow_cap`, `is_frozen`, `borrowing_enabled`.

### Historical hourly rates

```bash
python3 .claude/skills/hyperlend/hyperlend.py history --token USDC --hours 168              # 7d with full data
python3 .claude/skills/hyperlend/hyperlend.py history --token HYPE --hours 24 --summary-only # stats only
```

Returns per-hour `supply_rate_pct` and `borrow_rate_pct` plus summary with min/max/avg/latest and hours covered.

## Known tokens

HYPE, wstHYPE, kHYPE, beHYPE, USDC, USDT, USDH, USDHL, USDe, sUSDe, USR, UBTC, UETH, USOL. Case-insensitive.

## Comparing lending vs funding

When evaluating capital allocation:
1. Run `rates --tokens USDC,USDT,HYPE` for current lending APR
2. **Always cross-check with `markets`** — high APR pools may be `is_frozen: true` (no deposits) or have `supply_cap` of 1 (effectively full). Only recommend pools where `is_active: true`, `is_frozen: false`, and cap has headroom.
3. Compare supply APR against funding rate APR from Loris/candidates data
4. Lending = passive, no delta risk, no entry/exit fees; Funding = higher yield potential but requires active management

## Rate interpretation

- Rates are annualized percentages (APR = simple, APY = compounded)
- Historical rates from `/data/interestRateHistory` are in Ray (10^27) — CLI converts automatically
- Hyperlend uses Aave V3 two-slope interest model: rates jump sharply above optimal utilization
- Supply rate = what lenders earn; Borrow rate = what borrowers pay
