# Vault Pulse — 2026-04-22

**Data pulled:** 2026-04-22 ~15:31 UTC  
**Yesterday delta:** N/A (no prior snapshot found)

---

## Lending Rates

| Protocol | Pool | Asset | APY | Δ 1d | TVL/Cap | Util% | Our $ | Daily Yield | Status |
|---|---|---|---|---|---|---|---|---|---|
| Felix | USDT0 Vault | USDT0 | 14.72% | — | $11.69M | — | $100,000 | ~$40.33 | 🟢 GREEN |
| Felix | USDC Vault | USDC | ⚠️ NOT FOUND | — | — | — | $300,000 | — | ⚠️ DATA GAP |
| HyperLend | Core | USDC | 4.75% | — | — | — | $230,000 | ~$29.96 | 🟡 YELLOW |
| HyperLend | Core | USDT | 5.92% | — | — | — | $50,000 | ~$8.11 | 🟢 GREEN |
| HypurrFi | Pooled | USDT0 | 6.37% | — | $2.66M / $40M | 73.1% | $100,000 | ~$17.45 | 🟢 GREEN |

> **Felix USDC ($300k) data gap:** No Felix USDC vault found in Morpho/Felix vault list. Felix vaults currently: USDT0 (14.72%), USDT0 Frontier (15.56%), USDhl (12.97%), USDe (10.28%), HYPE (1.08%). Felix markets use USDT0/USDhl/USDe as loan assets — no USDC loan market detected. **Action required: verify current Felix USDC position status.**

---

## Additional Felix Vault Reference

| Vault | Asset | APY | TVL |
|---|---|---|---|
| Felix USDT0 | USDT0 | 14.72% | $11.69M |
| Felix USDT0 (Frontier) | USDT0 | 15.56% | $1.80M |
| Felix USDhl | USDHL | 12.97% | $220.2K |
| Felix USDe | USDe | 10.28% | 1.13M USDe |
| USDhl (Frontier) | USDHL | 22.95% | $137.9K |
| Felix HYPE | WHYPE | 1.08% | 1.16M WHYPE |

---

## Funding Rates

APR = fund/hr × 8760 × 100

| Symbol | Fund/hr | APR | Mark Price | OI | 24h Vol | 24h% | Status |
|---|---|---|---|---|---|---|---|
| LINK | +0.001250% | +10.95% | $9.497 | $29.56M | $3.20M | +1.11% | 🟢 GREEN |
| FARTCOIN | +0.001250% | +10.95% | $0.2109 | $46.13M | $28.26M | +4.61% | 🟢 GREEN |

---

## USDT0 Peg Check

| Metric | Value | Status |
|---|---|---|
| Best Bid | 1.000300 USDC/USDT0 | — |
| Best Ask | 1.000400 USDC/USDT0 | — |
| Mid | 1.000350 | +0.035% vs $1 |
| Spread | 1.00 bps | — |
| Bid Depth (20L) | $935.1K | — |
| Ask Depth (20L) | $1.68M | — |
| Peg Status | 🟢 GREEN | Δ from $1: +3.5 bps (<100 bps threshold) |

---

## Open Orders

| Coin | Side | Type | TIF | Limit Px | Size | Notional | Filled | Age | Status |
|---|---|---|---|---|---|---|---|---|---|
| @166 (USDT0) | Buy | Limit | GTC | 1.0003 | 4,830 | $4.8K | 0.0% | 1.2h | Pending |

---

## Trigger Monitor

| Trigger | Threshold | Current | Status |
|---|---|---|---|
| Felix USDT0 APY | < 8% | 14.72% | 🟢 GREEN |
| Felix USDC APY | < 8% | NOT FOUND | ⚠️ DATA GAP |
| USDT0 depeg | > 1% | +0.035% | 🟢 GREEN |
| USDT0 depeg severe | > 3% | +0.035% | 🟢 GREEN |
| HyperLend USDC APY | < 5% | 4.75% | 🟡 YELLOW |
| HyperLend USDC APY | < 3% | 4.75% | 🟢 GREEN |
| HyperLend USDT APY | < 5% | 5.92% | 🟢 GREEN |
| HypurrFi USDT0 APY | < 5% | 6.37% | 🟢 GREEN |
| Spot-perp LINK APR | < 8% | 10.95% | 🟢 GREEN |
| Spot-perp FARTCOIN APR | < 8% | 10.95% | 🟢 GREEN |

---

## Alerts

### 🟡 YELLOW
- **HyperLend USDC at 4.75% APY** — below 5% threshold ($230k deployed). Supply APY has dipped under the lower soft-limit. Monitor; if it drops below 3%, evaluate reallocation to HypurrFi USDC (currently at 20.74%) or Felix vaults.

### ⚠️ DATA GAP
- **Felix USDC vault not found** — $300k position cannot be verified or rate-monitored. Felix protocol does not expose a USDC-loan vault via the Morpho API. Possible explanations: (1) position is in an unlisted market, (2) funds were reallocated, (3) position label is stale. **Recommend: manually verify in Felix app.**

---

## Daily Yield Estimate (known positions)

| Position | Our $ | APY | Est. Daily |
|---|---|---|---|
| Felix USDT0 | $100,000 | 14.72% | ~$40.33 |
| HyperLend USDC | $230,000 | 4.75% | ~$29.96 |
| HyperLend USDT | $50,000 | 5.92% | ~$8.11 |
| HypurrFi USDT0 | $100,000 | 6.37% | ~$17.45 |
| **Subtotal (excl. Felix USDC)** | **$480,000** | — | **~$95.85** |
| Felix USDC | $300,000 | UNKNOWN | — |

> Excludes funding income from LINK/FARTCOIN spot-perp positions.
