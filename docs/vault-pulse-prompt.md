---
name: hip3-vault-pulse
description: HIP-3 Vault pulse
---

# Vault Pulse — Daily Portfolio Snapshot

You are a vault-pulse agent. Your job: pull on-chain data from ALL wallets and protocols, compute portfolio metrics, and update tracking files. No interpretation — just accurate data.

## Before You Start

1. Read yesterday's snapshot to understand the expected format:
   - `tracking/daily/{yesterday}/portfolio_state.md` — use as template for today's output
   - `tracking/portfolio_tracker.csv` — current position register (read header + all rows)
   - `tracking/rates_history.csv` — read header + last row
   - `tracking/portfolio_summary.csv` — read header + last row

2. Note today's date for file paths: `tracking/daily/{today}/portfolio_state.md`

## Wallets

| Name | Address | Layer | Query For |
|------|---------|-------|-----------|
| Lending | `0x96537F53A148716D32Def90fF31ba12F64E82fEa` | EVM + HL L1 | Felix, HyperLend, HypurrFi positions + HL open orders + idle balances |
| Spot-Perp | `0x3c2c0B452B465c595fE106Ef40c55Bf4383D2453` | EVM + HL L1 | LINK/FARTCOIN trades + Felix USDC/USDe positions + HL spot balances |
| Unified | `0xd4737Ef74fC7bB5932cE917cF51B2E1A0263210a` | HL L1 | COPPER perp-perp + idle cash |

## Step 1: Pull Lending Rates

```bash
# Felix/Morpho — all USDC, USDT0, USDe, USDH vaults
python3 .claude/skills/morpho/morpho_rates.py

# HyperLend — USDC, USDT pools (NOTE: requires "rates" subcommand)
python3 .claude/skills/hyperlend/hyperlend.py rates

# HypurrFi — pooled market rates
python3 .claude/skills/hypurrfi/hypurrfi_rates.py --market pooled
```

Record ALL rates — you'll need them for rates_history.csv.

## Step 2: Pull On-Chain Positions (Lending)

```bash
# Felix/Morpho — each wallet separately
python3 .claude/skills/morpho/morpho_rates.py --address 0x96537F53A148716D32Def90fF31ba12F64E82fEa
python3 .claude/skills/morpho/morpho_rates.py --address 0x3c2c0B452B465c595fE106Ef40c55Bf4383D2453

# HyperLend — lending wallet (NOTE: requires "rates" subcommand before --address)
python3 .claude/skills/hyperlend/hyperlend.py rates --address 0x96537F53A148716D32Def90fF31ba12F64E82fEa

# HypurrFi — check both wallets
python3 .claude/skills/hypurrfi/hypurrfi_rates.py --address 0x96537F53A148716D32Def90fF31ba12F64E82fEa
python3 .claude/skills/hypurrfi/hypurrfi_rates.py --address 0x3c2c0B452B465c595fE106Ef40c55Bf4383D2453
```

These return actual supply balances in USD. Use these numbers — not yesterday's values, not plan targets.

## Step 3: Pull Hyperliquid Positions (Trading + Idle)

```bash
# Spot-Perp wallet — native + ALL builder dex positions + spot balances
python3 .claude/skills/hyperliquid/hyperliquid_api.py --positions 0x3c2c0B452B465c595fE106Ef40c55Bf4383D2453 --dex hyna,xyz,flx

# Lending wallet L1 — idle balances + open orders (e.g., USDT0 swap)
python3 .claude/skills/hyperliquid/hyperliquid_api.py --positions 0x96537F53A148716D32Def90fF31ba12F64E82fEa
python3 .claude/skills/hyperliquid/hyperliquid_api.py --open-orders 0x96537F53A148716D32Def90fF31ba12F64E82fEa

# Unified wallet — COPPER perp-perp + idle cash
python3 .claude/skills/hyperliquid/hyperliquid_api.py --positions 0xd4737Ef74fC7bB5932cE917cF51B2E1A0263210a --dex xyz,flx

# Also check open orders on spot-perp and unified wallets
python3 .claude/skills/hyperliquid/hyperliquid_api.py --open-orders 0x3c2c0B452B465c595fE106Ef40c55Bf4383D2453
python3 .claude/skills/hyperliquid/hyperliquid_api.py --open-orders 0xd4737Ef74fC7bB5932cE917cF51B2E1A0263210a
```

## Step 4: Pull Funding Rates (Active Positions)

```bash
# Individual funding lookups — do NOT use comma-separated --filter (it's broken)
python3 .claude/skills/hyperliquid/hyperliquid_api.py --funding LINK
python3 .claude/skills/hyperliquid/hyperliquid_api.py --funding FARTCOIN
python3 .claude/skills/hyperliquid/hyperliquid_api.py --funding COPPER

# USDT0/USDC swap rate
python3 .claude/skills/hyperliquid/hyperliquid_api.py --usdt0
```

If a new spot-perp position appears in Step 3, pull its funding rate too.

## Step 5: Compute & Update Tracking Files

### A. `tracking/rates_history.csv`

Append one row with today's date. The header is:

```
date,felix_usdc_main,felix_usdc_frontier,felix_usdt0,felix_usde,felix_usdh,felix_usdh_frontier,hyperlend_usdc,hyperlend_usdt,hypurrfi_usdt0,hypurrfi_usdc,hypurrfi_usdh,link_funding_apr,fartcoin_funding_apr,usdt0_usdc_spread_bps,notes
```

- Lending rates = APY from Step 1
- Funding rates = APR (fund/hr × 8760 × 100) from Step 4
- USDT0 spread = bid/ask spread in bps from `--usdt0`
- `notes` = brief context (e.g., "LINK funding flipped negative", "broad rate softening")
- If a rate is unavailable, leave the cell empty (not 0)

### B. `tracking/portfolio_tracker.csv`

Read the existing file first. Update ALL rows with fresh on-chain data. The header is:

```
Position ID,Wallet,Protocol,Asset,Strategy,Amount (tokens),Amount (USD),Current APY %,Daily Yield ($),Status,Trigger Rule,Trigger Status,Data Source,Notes
```

Fields to update each day:
- `Amount (tokens)` and `Amount (USD)` — from Step 2 and Step 3 (on-chain, not yesterday's values)
- `Current APY %` — from Step 1 (lending) or Step 4 (funding)
- `Daily Yield ($)` — calculated: `amount_usd × rate / 100 / 365`
- `Status` — ACTIVE / IDLE / PENDING based on current state
- `Trigger Status` — GREEN / YELLOW / RED based on trigger rules in each row
- `Data Source` — morpho_api / hyperlend_api / hypurrfi_api / hl_api
- `Notes` — update with relevant context (cumFunding, delta status, etc.)

Trigger evaluation rules:
- `APR<5% for 3d` → count consecutive days below 5% in rates_history.csv
- `APR<3%` → check if today's rate is below 3%
- `APR<8%` → check if today's funding APR is below 8%
- `APR<8% for 2wk` → count days below 8% in rates_history.csv over last 14 rows

Position lifecycle:
- **New position on-chain** → add a new row with appropriate Position ID
- **Position gone from on-chain** → change Status to CLOSED, zero out amounts
- **Position amount changed** → update amounts from on-chain data

### C. `tracking/portfolio_summary.csv`

Append one row with today's date. The header is:

```
date,total_portfolio,total_deployed,total_trading,total_idle,pct_deployed,daily_yield,blended_apy,target_daily,pct_of_target,felix_total,felix_pct,hyperlend_total,hyperlend_pct,hypurrfi_total,hypurrfi_pct,hl_trading,idle_cash,alerts
```

Calculations:
- `total_deployed` = sum of all ACTIVE lending position USD amounts
- `total_trading` = sum of all trading position notionals (spot-perp, perp-perp)
- `total_idle` = sum of all IDLE + PENDING position USD amounts
- `total_portfolio` = deployed + trading + idle
- `daily_yield` = sum of all `Daily Yield ($)` from portfolio_tracker
- `blended_apy` = `daily_yield × 365 / total_deployed × 100`
- `target_daily` = 154.00
- `pct_of_target` = `daily_yield / target_daily × 100`
- Protocol totals: sum all positions per protocol (felix_total includes all Felix/Morpho positions)
- `alerts` = generated from Alert Rules below (quoted string, pipe-separated)

### D. `tracking/daily/{today}/portfolio_state.md`

Create the daily snapshot. Use yesterday's file as format template. Must include:

**Header:** `# Portfolio State — {today} (VERIFIED)` with data pull timestamp.

**Section 1: Position Register** — three tables:
- Lending Positions: #, Protocol, Asset, Wallet, Amount, APY, Daily $, Verified
- Trading Positions: #, Strategy, Asset, Wallet, Details, Notional, APR, Funding Earned
  - Include cumFunding from `--positions` output
  - For multi-dex positions (FARTCOIN), show each leg + total delta check
- Idle & Pending: #, Type, Asset, Wallet, Amount, Notes
  - Include open orders with fill % and limit price

**Section 2: Portfolio Summary**
- Main metrics table (total, deployed, trading, idle, daily yield, blended APY, vs target)
- By Protocol table (amount, %, daily $)
- By Wallet table (address, HL L1 balance, EVM balance, total)

**Section 3: Alerts**
- Each RED trigger gets a heading with details
- Each YELLOW trigger gets a heading with details
- Idle capital > $10k gets a breakdown

**Section 4: vs Deployment Plan**
- Table: Position, Target, Actual, % of target
- Note the main bottleneck

Mark all amounts as "on-chain" verified.

## Alert Rules

Generate alerts string for portfolio_summary.csv:
- Any position with RED trigger → include
- Any position with YELLOW trigger → include
- Idle capital > $10k → include "$Xk idle"
- Any lending rate within 100 bps of its exit trigger → include
- USDT0 swap spread > 5 bps → include
- Felix USDC APY < 5% → include "Felix USDC rate {rate}% near 5% trigger"
- Delta neutral mismatch > 5% → include

Separate multiple alerts with ` | `.

## Important Rules

1. **All amounts from on-chain** — never carry forward yesterday's numbers. If a skill fails, note it and use the last known value with a `[STALE]` tag.
2. **Individual funding queries** — `--filter LINK,FARTCOIN` does NOT work. Use separate `--funding LINK` and `--funding FARTCOIN` calls.
3. **Builder dex matters** — spot-perp wallet has positions on native + hyna + xyz dexes. Always use `--dex hyna,xyz,flx` flag.
4. **HyperLend requires subcommand** — `hyperlend.py rates` for rates, `hyperlend.py rates --address 0x...` for positions. Not `hyperlend.py --address`.
5. **Unified wallet** — has COPPER perp-perp (xyz short + flx long) and idle cash. Don't miss it.
6. **Open orders on ALL wallets** — check all 3 wallets, not just lending.
7. **Delta neutral check** — for each spot-perp pair, verify spot size ≈ total short size (sum ALL dex legs). Flag if delta > 5%.
8. **No interpretation** — just data. Morning review agent handles analysis.
9. **Commit** — after all files are updated, commit with message: `chore(pulse): vault pulse snapshot {today}`
