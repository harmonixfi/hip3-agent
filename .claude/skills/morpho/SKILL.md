---
name: morpho
description: Use when writing integration code for Morpho protocol on HyperEVM, analyzing Felix lending markets or vaults, querying live market APYs and utilization, or comparing Felix-specific pools vs all Morpho markets on HyperEVM.
---

# Morpho Protocol Skill

---

## CRITICAL: Felix vs Morpho Scope

```
┌─────────────────────────────────────────────────────────────┐
│  "Analyze Felix"  →  22 specific markets + 18 MetaMorpho   │
│                       vaults (Felix, Gauntlet, Hyperithm,   │
│                       MEV Capital curators)                 │
│                                                             │
│  "Analyze Morpho" →  all markets on HyperEVM (chain 999)   │
│                       via Morpho Blue (186+ markets)        │
└─────────────────────────────────────────────────────────────┘
```

**Felix** is a DeFi frontend (usefelix.xyz) that integrates Morpho smart contracts.  
**All Felix lending operations go through Morpho Blue** — Felix just curates a subset.  
When the user says "Felix markets" or "Felix pools", use the hardcoded IDs below.  
When the user says "Morpho markets" or "all markets", query chain 999 without ID filter.

---

## Section A: Technical Reference

### Protocol Overview

Morpho Blue is a permissionless isolated lending protocol. Each **market** is defined by exactly 5 immutable parameters:

| Param | Description |
|-------|-------------|
| `loanToken` | ERC20 token to borrow |
| `collateralToken` | ERC20 token posted as collateral |
| `oracle` | Price feed for collateral/loan ratio |
| `irm` | Interest Rate Model contract |
| `lltv` | Liquidation LTV (in WAD, e.g., 770000000000000000 = 77%) |

**MarketId** = `keccak256(abi.encode(loanToken, collateralToken, oracle, irm, lltv))`

**MetaMorpho Vaults** = ERC-4626 curated vaults. Depositors supply to a vault; a curator allocates funds across Morpho markets to optimize yield. APY is pre-computed by the Morpho API.

### Network & Contracts (HyperEVM, Chain 999)

- **RPC**: `https://rpc.hyperliquid.xyz/evm`
- **Chain ID**: 999 (Morpho API field: `chainId: 999`)
- **Morpho Blue** (Felix deployment): `0x68e37de8d93d3496ae143f2e900490f6280c57cd`
- **AdaptiveCurveIRM**: `0xD4a426F010986dCad727e8dd6eed44cA4A9b7483`

### Felix Markets (22 markets, Collateral → Loan)

| Label | MarketId |
|-------|---------|
| UETH/USDT0 | `0xf9f0473b23ebeb82c83078f0f0f77f27ac534c9fb227cb4366e6057b6163ffbf` |
| UETH/USDhl | `0xb5b215bd2771f5ed73125bf6a02e7b743fadc423dfbb095ad59df047c50d3e81` |
| kHYPE/HYPE | `0x64e7db7f042812d4335947a7cdf6af1093d29478aff5f1ccd93cc67f8aadfddc` |
| kHYPE/USDhl | `0xc0a3063a0a7755b7d58642e9a6d3be1c05bc974665ef7d3b158784348d4e17c5` |
| kHYPE/USDT0 | `0x78f6b57d825ef01a5dc496ad1f426a6375c685047d07a30cd07ac5107ffc7976` |
| WHYPE/USDe | `0x292f0a3ddfb642fbaadf258ebcccf9e4b0048a9dc5af93036288502bde1a71b1` |
| WHYPE/USDT0 | `0xace279b5c6eff0a1ce7287249369fa6f4d3d32225e1629b04ef308e0eb568fb0` |
| WHYPE/USDhl | `0x96c7abf76aed53d50b2cc84e2ed17846e0d1c4cc28236d95b6eb3b12dcc86909` |
| UBTC/USDe | `0x5fe3ac84f3a2c4e3102c3e6e9accb1ec90c30f6ee87ab1fcafc197b8addeb94c` |
| UBTC/USDT0 | `0x707dddc200e95dc984feb185abf1321cabec8486dca5a9a96fb5202184106e54` |
| UBTC/USDhl | `0x87272614b7a2022c31ddd7bba8eb21d5ab40a6bcbea671264d59dc732053721d` |
| wstHYPE/HYPE | `0xbcae0d8e381f600b2919194434a0733899697a4c3b6715a5fa75acf8b84bd755` |
| wstHYPE/USDT0 | `0xb39e45107152f02502c001a46e2d3513f429d2363323cdaffbc55a951a69b998` |
| wstHYPE/USDhl | `0x1f79fe1822f6bfe7a70f8e7e5e768efd0c3f10db52af97c2f14e4b71e3130e70` |
| hwHLP/USDhl | `0xe500760b79e397869927a5275d64987325faae43326daf6be5a560184e30a521` |
| hwHLP/USDT0 | `0x86d7bc359391486de8cd1204da45c53d6ada60ab9764450dc691e1775b2e8d69` |
| wHLP/USDhl | `0x920244a8682a53b17fe15597b63abdaa3aecec44e070379c5e43897fb9f42a2b` |
| wHLP/USDT0 | `0xd4fd53f612eaf411a1acea053cfa28cbfeea683273c4133bf115b47a20130305` |
| kHYPE-PT/HYPE | `0x1df0d0ebcdc52069692452cb9a3e5cf6c017b237378141eaf08a05ce17205ed6` |
| kHYPE-PT/USDT0 | `0x888679b2af61343a4c7c0da0639fc5ca5fc5727e246371c4425e4d634c09e1f6` |
| kHYPE-PT/USDhl | `0xe0a1de770a9a72a083087fe1745c998426aaea984ddf155ea3d5fbba5b759713` |
| kHYPE-PT/USDC | `0xcd9898604b9b658fc3295f86d4cd7f02fa3a6b0a573879f1db9b83369f4951fb` |

### Felix MetaMorpho Vaults (18 vaults, 4 curators)

Vaults are ERC-4626 contracts. Users deposit the underlying asset; the curator routes it into Felix/Morpho markets. **Felix-curated** vaults are operated by Felix itself; **Gauntlet / Hyperithm / MEV Capital** are third-party curators running their own risk strategies on top of Felix markets.

**Felix-curated (10)**:

| Name | Asset | Address |
|------|-------|---------|
| Felix USDe | USDe | `0x835febf893c6dddee5cf762b0f8e31c5b06938ab` |
| Felix USDT0 | USDT0 | `0xfc5126377f0efc0041c0969ef9ba903ce67d151e` |
| Felix USDT0 (Frontier) | USDT0 | `0x9896a8605763106e57A51aa0a97Fe8099E806bb3` |
| Felix USDhl | USDhl | `0x9c59a9389D8f72DE2CdAf1126F36EA4790E2275e` |
| Felix USDhl (Frontier) | USDhl | `0x66c71204B70aE27BE6dC3eb41F9aF5868E68fDb6` |
| Felix HYPE | HYPE/WHYPE | `0x2900ABd73631b2f60747e687095537B673c06A76` |
| Felix USDC | USDC | `0x8A862fD6c12f9ad34C9c2ff45AB2b6712e8CEa27` |
| Felix USDC (Frontier) | USDC | `0x808F72b6Ff632fba005C88b49C2a76AB01CAB545` |
| Felix USDH | USDH | `0x207ccaE51Ad2E1C240C4Ab4c94b670D438d2201C` |
| Felix USDH (Frontier) | USDH | `0x274f854b2042DB1aA4d6C6E45af73588BEd4Fc9D` |

**Gauntlet (3)**:

| Name | Asset | Address |
|------|-------|---------|
| Gauntlet USDC | USDC | `0x08C00F8279dFF5B0CB5a04d349E7d79708Ceadf3` |
| Gauntlet USDT0 | USDT0 | `0x53A333e51E96FE288bC9aDd7cdC4B1EAD2CD2FfA` |
| Gauntlet WHYPE | WHYPE | `0x264a06Fd7A7C9E0Bfe75163b475E2A3cc1856578` |

**Hyperithm (3)**:

| Name | Asset | Address |
|------|-------|---------|
| Hyperithm USDC | USDC | `0xF0A23671A810995B04A0f3eD08be86797B608D78` |
| Hyperithm USDT0 | USDT0 | `0xe5ADd96840F0B908ddeB3Bd144C0283Ac5ca7cA0` |
| Hyperithm HYPE | WHYPE | `0x92B518e1cD76dD70D3E20624AEdd7D107F332Cff` |

**MEV Capital (2)**:

| Name | Asset | Address |
|------|-------|---------|
| MEV Capital USDT0 | USDT0 | `0x3Bcc0a5a66bB5BdCEEf5dd8a659a4eC75F3834d8` |
| MEV Capital HYPE | WHYPE | `0xd19e3d00f8547f7d108abFD4bbb015486437B487` |

The CLI output sorts by TVL descending — so the largest vaults (Felix USDC ~$20M, Felix USDC Frontier ~$18M, Felix USDT0 ~$12M) show first.

### Rate Model: AdaptiveCurveIRM

Target utilization: **90%**. Rate self-adjusts:
- If U > 90%: rate doubles every 5 days
- If U < 90%: rate halves every 10 days

```
borrowAPY = (e^(borrowRatePerSec × 31_536_000) - 1) × 100
supplyAPY = borrowAPY × utilization × (1 - fee)
```

`borrowRatePerSec` is in WAD (1e18). The Morpho API returns pre-computed `supplyApy` and `borrowApy` as fractions (0.15 = 15%).

### Data Access: Morpho GraphQL API

**Endpoint**: `https://api.morpho.org/graphql`  
HyperEVM = `chainId: 999`

**Fetch specific markets** (Felix scope):
```graphql
query {
  markets(where: { chainId_in: [999], uniqueKey_in: ["0xf9f0..."] }, first: 100) {
    items {
      marketId
      loanAsset { symbol decimals }
      collateralAsset { symbol decimals }
      state { supplyApy borrowApy utilization supplyAssets borrowAssets liquidityAssets }
      lltv
    }
  }
}
```

**Fetch all markets** (Morpho scope) — paginate with `skip`:
```graphql
query {
  markets(where: { chainId_in: [999] }, first: 100, skip: 0, orderBy: SupplyAssets, orderDirection: Desc) {
    items { ... }
    pageInfo { countTotal }
  }
}
```

**Fetch vaults**:
```graphql
query {
  vaults(where: { chainId_in: [999], address_in: ["0x835f..."] }, first: 20) {
    items {
      address name
      asset { symbol decimals }
      state { totalAssets apy }
    }
  }
}
```

**User positions**:
```graphql
query {
  marketPositions(where: { chainId_in: [999], userAddress_in: ["0x..."] }) {
    items { market { marketId loanAsset { symbol decimals } collateralAsset { symbol decimals } } supplyAssets borrowAssets collateral }
  }
  vaultPositions(where: { chainId_in: [999], userAddress_in: ["0x..."] }) {
    items { vault { address name asset { symbol decimals } } assets }
  }
}
```

**API field notes**:
- `supplyApy`, `borrowApy`: fraction (0.15 = 15%), multiply by 100 for %
- `supplyAssets`, `borrowAssets`, `liquidityAssets`: raw token units (divide by 10^decimals)
- For 18-decimal tokens: `totalAssets` may return as JSON string (big integer)
- `lltv`: WAD (divide by 1e16 to get %)

### Integration Code Patterns

```typescript
// Supply to Felix vault (ERC-4626)
const vault = new ethers.Contract(FELIX_USDT0_VAULT, ERC4626_ABI, signer);
await token.approve(vault.address, amount);
await vault.deposit(amount, receiver);

// Borrow from Morpho market directly
const morpho = new ethers.Contract(MORPHO_ADDR, MORPHO_ABI, signer);
await morpho.supplyCollateral(marketParams, collateralAmount, onBehalfOf, "0x");
await morpho.borrow(marketParams, borrowAmount, 0, onBehalfOf, receiver);

// Liquidate
await morpho.liquidate(marketParams, borrower, seizedAssets, 0, "0x");
```

---

## Section B: Agent CLI Tool

### `morpho_rates.py` — Live Market Data Fetcher

**Location**: `.claude/skills/morpho/morpho_rates.py`  
**Requirements**: Python 3.9+ stdlib only  
**Data source**: Morpho GraphQL API (`https://api.morpho.org/graphql`)

#### Usage

```bash
# Felix markets + vaults (default)
python3 .claude/skills/morpho/morpho_rates.py

# Felix markets only (21 markets)
python3 .claude/skills/morpho/morpho_rates.py --market markets

# Felix MetaMorpho vaults only (6 vaults)
python3 .claude/skills/morpho/morpho_rates.py --market vaults

# All Morpho markets on HyperEVM (186+ markets, ordered by TVL)
python3 .claude/skills/morpho/morpho_rates.py --market morpho

# Felix markets + vaults + all other Morpho markets
python3 .claude/skills/morpho/morpho_rates.py --market all

# JSON output for agent parsing
python3 .claude/skills/morpho/morpho_rates.py --json

# Include user positions
python3 .claude/skills/morpho/morpho_rates.py --address 0xYourWallet

# Override chain (default 999 = HyperEVM)
python3 .claude/skills/morpho/morpho_rates.py --chain 1
```

#### Output Fields

**Markets table** (`Felix Markets` / `All Morpho Markets`):

| Field | Description |
|-------|-------------|
| Market | `CollateralToken/LoanToken` — you supply collateral, borrow loan token |
| Supply APY | Annual yield for lenders (%) |
| Borrow APY | Annual cost for borrowers (%) |
| TVL | Total loan token supplied (normalized) |
| Borrows | Total outstanding borrows |
| Util% | `borrowAssets / supplyAssets × 100` |
| LLTV | Liquidation LTV threshold |
| Available | Cash available to borrow or withdraw (`liquidityAssets`) |

**Vaults table** (`Felix Vaults`):

| Field | Description |
|-------|-------------|
| Vault | MetaMorpho vault name |
| Asset | Underlying deposit token |
| APY | Computed supply yield (curator-managed allocation) |
| TVL | Total assets in vault (normalized) |

#### Amount Display

- 6-decimal stablecoins (USDT0, USDhl, USDe): shown as `$1.2M` / `$800K`
- 18-decimal native tokens (WHYPE, HYPE): shown as `871K WHYPE`

#### Known Limitations

1. **100% utilization markets**: Available = $0, no new borrows/withdrawals possible. Signal: check `util_pct` before entering.
2. **All Morpho markets**: 186+ markets, includes illiquid and zero-TVL markets. Filter by TVL and utilization.
3. **wstHYPE/USDe**: Shows very high APY (~750%) from tiny TVL + high utilization. Not a practical market.
4. **Felix HYPE vault**: The underlying is WHYPE (wrapped HYPE); API reports symbol as WHYPE.
5. **Price in USD**: Non-stablecoin loan markets (WHYPE, HYPE) show token amounts, not USD — no price oracle in this tool.
