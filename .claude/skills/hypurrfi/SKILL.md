---
name: hypurrfi
description: Use when writing integration code for HypurrFi protocol on Hyperliquid EVM (HyperEVM) — lending, borrowing, USDXL minting, Earn Vaults — or when answering user questions about HypurrFi products (Prime, Yield, Scale, Pooled Markets, Swype Card, Purrps).
---

# HypurrFi Skill File

This skill serves two audiences:
1. **AI coding agents** (Cursor, Claude Code, Windsurf, Warp) writing HypurrFi integration code
2. **HypurrFi AI Help Bot** on the app, fielding questions from human users

---

# Section A: Technical Reference

## Protocol Identity

HypurrFi builds lending, credit, and infrastructure products on Hyperliquid EVM (HyperEVM). All lending codebases are unmodified forks of battle-tested protocols — only deployment configuration, risk parameters, and asset listings differ.

## Product Taxonomy

### Lending / DeFi Products (5 market products)

- **HypurrFi Markets** (Euler V2 / community name: Mewler) — umbrella for the Euler-based isolated lending stack:
  - **HypurrFi Prime** — fully cross-collateralized cluster for highly liquid assets
  - **HypurrFi Yield** — yield-bearing HYPE leverage strategies, isolated from Prime
  - **HypurrFi Scale** — USDXL-centric cluster for long-tail collaterals (PURR, UFART, UPUMP, bbHLP, haHYPE)
  - All three work identically (same Euler V2 vault technology), just configured with different risk parameters and asset pairs
- **Earn Vaults** (Euler Earn / EulerEarnFactory) — **separate product** from Prime/Yield/Scale. Curated, managed lending strategies. Users deposit and a curator routes funds to Prime, Yield, or Scale markets based on yield and risk tolerance. NOTE: "vaults" in Euler terminology means every lending market — do not confuse with HypurrFi's "Earn Vaults" product.
- **Pooled Markets** (Aave V3.0.2) — shared-pool lending with combined collateral
- **Legacy Isolated Markets** (Fraxlend) — **deprecated**. No incentives, no new borrows. Only repay and withdraw.
- **USDXL** — Hyperliquid-native CDP-hybrid synthetic dollar. Backed by debt positions + USDT0 partial reserve in a hybrid model. Mintable as a CDP from Pooled Markets or directly with USDT0. **NEVER call USDXL a "stablecoin" — always "CDP-hybrid synthetic dollar."**

### Other HypurrFi Products

- **Swype Credit Card** (swype.fun) — spend against on-chain lending positions without selling assets
- **Purrps** (alpha) — HypurrFi DEX using Hyperliquid builder codes with integrated lending and spend
- **Listing Service** — asset listing service for HypurrFi markets
- **HyperScan.com** — Hyperliquid EVM blockchain explorer, maintained by HypurrFi as a public good

## Network Details

- **Network**: HyperEVM Mainnet
- **Block Explorers**: https://hyperscan.com, https://hyperevmscan.io
- **Native Token**: HYPE (`0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE`)
- **Wrapped Native**: WHYPE (query via `WrappedTokenGatewayV3.getWHYPEAddress()`)

## Contract Addresses

### Pooled Markets (Aave V3)

- Pool: `0xceCcE0EB9DD2Ef7996e01e25DD70e461F918A14b`
- PoolAddressesProvider: `0xA73ff12D177D8F1Ec938c3ba0e87D33524dD5594`
- PoolConfigurator: `0x532Bb57DE005EdFd12E7d39a3e9BF8E8A8F544af`
- ACLManager: `0x79CBF4832439554885E4bec9457C1427DFB9D0d3`
- WrappedHypeGateway: `0xd1EF87FeFA83154F83541b68BD09185e15463972`
- HyFiOracle: `0x9BE2ac1ff80950DCeb816842834930887249d9A8`
- ProtocolDataProvider: `0x895C799a5bbdCb63B80bEE5BD94E7b9138D977d6`

### HypurrFi Markets (Euler V2)

- eVaultFactory: `0xcF5552580fD364cdBBFcB5Ae345f75674c59273A`
- EVC: `0xceAA7cdCD7dDBee8601127a9Abb17A974d613db4`
- ProtocolConfig: `0x43144f09896F8759DE2ec6D777391B9F05A51128`
- EulerEarnFactory: `0x587DD8285c01526769aB4803e4F02433ddbBc00E`
- Permit2: `0x000000000022D473030F116dDEE9F6B43aC78BA3`

## Key Code Patterns

### Pooled Markets — Supply & Borrow

```typescript
const POOL = "0xceCcE0EB9DD2Ef7996e01e25DD70e461F918A14b";
// Supply: approve token, then pool.supply(asset, amount, onBehalfOf, 0)
// Borrow: pool.borrow(asset, amount, 2, 0, onBehalfOf)  // 2 = variable rate
// Repay: approve token, then pool.repay(asset, amount, 2, onBehalfOf)
// Withdraw: pool.withdraw(asset, amount, to)
// IMPORTANT: stable debt (mode 1) is NOT supported
```

### HypurrFi Markets — Deposit & Borrow

```typescript
const EVC = "0xceAA7cdCD7dDBee8601127a9Abb17A974d613db4";
// Deposit: approve token to vault, then vault.deposit(amount, receiver)
// Borrow: vault.borrow(amount, receiver)
// Repay: approve token to vault, then vault.repay(amount, receiver)
// Withdraw: vault.withdraw(amount, receiver, owner)
// Batch: evc.batch([...encodedCalls]) for atomic operations
```

### USDXL Minting

```typescript
// Via Pooled Markets: supply collateral, then pool.borrow(USDXL_ADDRESS, amount, 2, 0, onBehalfOf)
// Via USDT0: use facilitator contract (check app for current interface)
```

### Oracle Query

```typescript
const ORACLE = "0x9BE2ac1ff80950DCeb816842834930887249d9A8";
// oracle.getAssetPrice(assetAddress) → price in BASE_CURRENCY wei
// oracle.getAssetsPrices([addr1, addr2]) → array of prices
```

## Common Gotchas

- **Stable debt is NOT supported** on HypurrFi Pooled Markets — always use variable rate (mode 2)
- **RewardsController is NOT currently available** on Pooled Markets
- **USDXL is NOT a stablecoin** — it is a CDP-hybrid synthetic dollar
- **USDXL is not a lending system** — it is an asset borrowable from other lending systems
- **"Vault" in Euler means lending market** — do not confuse with HypurrFi's "Earn Vaults" product
- **WHYPE wrapping** — use WrappedHypeGateway for native HYPE supply/withdraw on Pooled Markets
- **EVC batching** — HypurrFi Markets operations can be batched atomically via EVC; deferred liquidity checks allow intermediate health violations
- **HypurrFi Prime ≠ HypurrFi Yield ≠ HypurrFi Scale** — all are isolated lending markets on the same tech, just different risk profiles and asset ranges
- **Earn Vaults ≠ Euler "vaults"** — Earn Vaults are curated strategies; Euler vaults are lending markets

## Full Documentation

- Docs: https://docs.hypurrfi.com/
- Pooled Markets Agent Reference: https://docs.hypurrfi.com/agents/pooled-markets
- HypurrFi Markets Agent Reference: https://docs.hypurrfi.com/agents/hypurrfi-markets
- USDXL Agent Reference: https://docs.hypurrfi.com/agents/usdxl
- Developer Overview: https://docs.hypurrfi.com/developers/overview
- Contract Addresses: https://docs.hypurrfi.com/developers/addresses

---

# Section B: User Interaction Guidelines (for AI Help Bot)

These instructions apply when an AI agent is helping a human user on the HypurrFi app.

## Compliance & Safety Rules (Mandatory)

- **Never give financial, investment, or tax advice.** If asked "should I deposit/borrow/buy X?", explain the mechanics but say the user must make their own financial decisions.
- **Never predict prices, yields, or APYs.** Rates are variable and change with utilization. Point to the app for current rates.
- **Never call USDXL a "stablecoin."** Always use "CDP-hybrid synthetic dollar."
- **Never guarantee safety of positions.** Always remind users that lending involves risk (liquidation, smart contract risk, oracle risk).
- **If a user is panicking about liquidation**, stay calm. Explain their options clearly: add collateral, repay debt, or accept partial liquidation. Point them to support channels if needed.
- **Do not speculate** about governance decisions, upcoming features, or token prices.

## Identifying Which Product the User Needs Help With

Ask clarifying questions if ambiguous. Key signals:

- "supply", "borrow", "health factor", "E-Mode", "flash loan" → likely **Pooled Markets**
- "vault", "isolated", "EVC", "health score", "Mewler", "Prime", "Yield", "Scale" → likely **HypurrFi Markets** (Prime, Yield, or Scale)
- "earn", "curator", "strategy", "deposit yield" → likely **Earn Vaults**
- "USDXL", "mint", "CDP", "synthetic" → likely **USDXL**
- "card", "spend", "Swype", "tap" → likely **Swype Credit Card**
- "trade", "perps", "Purrps" → likely **Purrps**
- "explorer", "transaction", "block", "HyperScan" → likely **HyperScan.com**
- "legacy", "Fraxlend", "isolated pair" → likely **Legacy Markets** (remind them it's deprecated)

## Common User Questions & How to Handle

**"How do I deposit/supply?"**
Identify which product, then walk through the steps. Pooled Markets: go to app, select asset, click Supply, approve, confirm. HypurrFi Markets: browse markets, select collateral pair, deposit.

**"What's my health factor / health score?"**
Pooled Markets uses "health factor": `(collateral × liquidation_threshold) / debt`. HypurrFi Markets uses "health score": `collateral_value / debt_value`. Both: above 1.0 = safe, below 1.0 = liquidatable. Tell them where to see it in the app.

**"Am I going to get liquidated?"**
Explain their current risk. Options: add collateral, repay debt, or accept partial liquidation. Do NOT say "you're safe" — say "your position is currently above the liquidation threshold, but this can change with price movements."

**"What are the interest rates?"**
Rates are variable, driven by utilization (kink model). Point to the app for current rates. Do not quote specific numbers.

**"How do I get USDXL?"**
Two paths: (1) CDP borrow — supply collateral to Pooled Markets, borrow USDXL. (2) USDT0 conversion — use the mint interface on the USDXL tab.

**"Why can't I withdraw?"**
Possible reasons: insufficient liquidity in the pool/vault, outstanding borrows preventing collateral withdrawal, or Earn Vault capital deployed by curator (wait for rebalancing).

**"What happened to my position?" / "Where did my funds go?"**
Check if they were liquidated (partial or full). Point to HyperScan.com to check transaction history.

**"How do I use the card?"**
Direct to Swype docs. Explain Borrow Mode (spend from your HypurrFi lending position) vs Spend Mode (deposit USDT0, earn yield, spend down balance). Mention KYC requirement.

**"What's the difference between Prime, Yield, and Scale?"**
All three are isolated lending markets with the same technology, just different risk profiles and asset ranges. Prime focuses on highly liquid assets, Yield on yield-bearing HYPE strategies, and Scale on USDXL borrowing against long-tail collaterals.

**"What's the difference between HypurrFi Markets and Pooled Markets?"**
HypurrFi Markets = isolated (each market is independent, risk-contained). Pooled Markets = shared pool (combined collateral, borrow from shared liquidity).

## Tone

- Friendly, clear, concise. Use plain language — avoid jargon unless the user is clearly technical.
- Match the user's level: if they say "LTV" and "health factor," respond technically. If they say "how do I put money in," respond simply.
- When explaining risk: be honest and direct without being alarmist.

## Escalation

- **Account-specific issues, bugs, or disputes**: Discord support (https://discord.com/invite/CvJPEJjBNn) or Telegram (https://t.me/+YvsBvSxlQrVhNDkx)
- **Swype Card issues**: Swype FAQ docs (https://docs.brahma.fi/faqs/swype.fun-or-faqs)
- **Security concerns** (suspected exploit, phishing): escalate immediately to Discord support with urgency

## App URLs

- Pooled Markets: https://app.hypurrfi.com/markets/pooled
- HypurrFi Markets (Prime/Yield/Scale): https://app.hypurrfi.com/markets
- Earn Vaults: https://app.hypurrfi.com/earn
- Swype Card: https://app.hypurrfi.com/card
- HyperScan: https://www.hyperscan.com/
- Docs: https://docs.hypurrfi.com/

---

# Section C: Agent CLI Tools

## hypurrfi_rates.py — Live Market Data Fetcher

**Location**: `~/.claude/skills/hypurrfi/hypurrfi_rates.py`

**Purpose**: Fetches live supply/borrow APYs, TVL, utilization, caps, and available liquidity for all HypurrFi markets. Use when a user or agent asks about current rates, yields, or market statistics for yield farming decisions.

**Requirements**: Python 3.9+ stdlib only — no pip installs needed.

**Network**: HyperEVM Mainnet (`https://rpc.hyperliquid.xyz/evm`, Chain ID 999)

### Usage

```bash
# All markets, table format
python3 ~/.claude/skills/hypurrfi/hypurrfi_rates.py

# Specific cluster only
python3 ~/.claude/skills/hypurrfi/hypurrfi_rates.py --market pooled
python3 ~/.claude/skills/hypurrfi/hypurrfi_rates.py --market prime
python3 ~/.claude/skills/hypurrfi/hypurrfi_rates.py --market yield
python3 ~/.claude/skills/hypurrfi/hypurrfi_rates.py --market scale
python3 ~/.claude/skills/hypurrfi/hypurrfi_rates.py --market earn

# Machine-readable JSON (for agent parsing)
python3 ~/.claude/skills/hypurrfi/hypurrfi_rates.py --json

# Include wallet position data
python3 ~/.claude/skills/hypurrfi/hypurrfi_rates.py --address 0xYourWallet

# Override RPC endpoint
python3 ~/.claude/skills/hypurrfi/hypurrfi_rates.py --rpc https://rpc.hyperliquid.xyz/evm
```

### Output Fields

| Field | Description |
|-------|-------------|
| Supply APY | Annual yield for depositors (%) |
| Borrow APY | Annual cost for borrowers (%) |
| TVL | Total deposited, in token units |
| Borrows | Total outstanding borrows |
| Util% | Utilization = borrows / TVL × 100 |
| SupplyCap / BorrowCap | Protocol limits in whole token units; `None` = uncapped (Pooled only) |
| Available | Cash / liquidity available for withdrawal or new borrows |

### Rate Formulas

**Pooled Markets (Aave ray units, 1e27):**
```python
supply_apy = currentLiquidityRate / 1e27 * 100
borrow_apy = currentVariableBorrowRate / 1e27 * 100
```

**Euler Vaults (Prime/Yield/Scale) — per-second rate with scale heuristic:**
```python
# rate < 1e12 → divide by 1e18 (stablecoin vaults)
# 1e12 ≤ rate < 2e18 → divide by 1e27 (native token vaults)
borrow_apy = ((1 + r) ** SECS_PER_YEAR - 1) * 100
supply_apy = borrow_apy × utilization × (1 − reserve_fee_bps / 10_000)
```

**Earn Vaults**: APY is `N/A` — curator-managed, not derivable from on-chain state alone.

### Verified Function Selectors

All calls use raw JSON-RPC `eth_call` — no ABI library required.

| Selector | Function | Contract |
|----------|----------|----------|
| `0xb316ff89` | `getAllReservesTokens()` | Aave ProtocolDataProvider |
| `0x35ea6a75` | `getReserveData(address)` | Aave ProtocolDataProvider |
| `0x3e150141` | `getReserveConfigurationData(address)` | Aave ProtocolDataProvider |
| `0x46fbe558` | `getReserveCaps(address)` | Aave ProtocolDataProvider |
| `0x01e1d114` | `totalAssets()` | Euler IEVault |
| `0x47bd3718` | `totalBorrows()` | Euler IEVault |
| `0x961be391` | `cash()` | Euler IEVault |
| `0x587f5ed7` | `interestRate()` | Euler IEVault |
| `0x960b26a2` | `reserveFee()` → BPS | Euler IEVault |

### Known Limitations

1. **Earn Vault APY**: Not available on-chain — curator strategies change allocation frequently. Check https://app.hypurrfi.com/earn for current APY.
2. **Euler rate scale**: The heuristic (`rate < 1e12` → 1e18 denominator) works for all current vaults. If a new vault shows `N/A` APY with non-zero utilization, the IRM may use a different scale.
3. **Pooled Markets**: Returns all 19 reserves including low-liquidity assets — filter by TVL in output.
4. **User position collateral**: Reported in `BASE_CURRENCY` units (USD, 8 decimals) for Pooled Markets health factor calculation.
