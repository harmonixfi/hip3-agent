# API Inventory — Public Endpoints

## Overview
List of public endpoints (no auth required) for 5 venues.

---

## OKX

**Base URL:** `https://www.okx.com/api/v5/public`

**SDK:** Not using SDK initially; direct REST calls

**Rate Limits:**
- Based on IP address (public unauthenticated)
- See docs for per-endpoint limits

**Public Endpoints:**

### Instruments
- `GET /api/v5/public/instruments?instType=SWAP`
  - Returns list of perpetual contracts
  - Fields: instId, tickSz, ctVal, ctMult, lever, etc.

### Funding Rate
- `GET /api/v5/public/funding-rate`
  - Current funding rates for all perps
  - Returns: fundingRate, fundingTime, nextFundingTime

### Funding Rate History
- `GET /api/v5/public/funding-rate-history`
  - Historical funding rates (useful for stability analysis)
  - Params: instId, after, before, limit

### Mark Price / Index Price
- `GET /api/v5/public/mark-price?instType=SWAP`
  - Mark price + index price for all perps
  - Returns: instId, markPx, idxPx

### Orderbook
- `GET /api/v5/public/order-book?instId={symbol}`
  - Top of book for basis/slippage estimation
  - Returns: bids[0], asks[0], ts

**Notes:**
- OKX supports both spot + perp → can compute spot↔perp basis on one venue
- Cross-cycle settlement rules may affect funding calculations

---

## Hyperliquid

**Base URL:** `https://api.hyperliquid.xyz`

**SDK:** https://github.com/hyperliquid-dex/hyperliquid-python-sdk

**Rate Limits:** None documented (public endpoints typically lenient)

**Public Endpoints:**

### Meta / Info
- `POST /info`
  - Exchange metadata (funding interval = 1h)
  - **Preferred** over `POST /meta` (may be deprecated)

### Instruments
- `GET /info` → returns all markets with perps (use `info` endpoint)
  - Alternative: `POST /meta` or `POST /perp`

### Funding Rate
- `POST /funding` (or via SDK `Funding.get_funding()`)
  - Current funding rates for perps

### Orderbook
- `POST /orderbook` or `POST /l2Book`
  - Orderbook L2 snapshot
  - Returns: levels (price, size)

**Notes:**
- 1-hour funding interval
- SDK provides typed Python bindings
- **Prefer `GET /info`** for market metadata

---

## Paradex

**Base URL:** `https://api.paradex.trade`

**SDK:** https://github.com/tradeparadex/paradex-py

**Rate Limits:** Not clearly documented in public docs

**Public Endpoints:**

### Instruments / Markets
- Likely: `/markets` or `/contracts`
- SDK provides methods to query perps
- Need to explore SDK for exact method names

### Funding Rate
- SDK likely has funding-related method
- May need to inspect SDK code/examples

### Orderbook
- SDK likely provides orderbook access
- Documentation minimal; SDK exploration required

**Notes:**
- API docs are minimal for public data
- SDK provides Python bindings — prefer using SDK over raw REST


---

## Lighter

**Base URL:** `https://api.lighter.xyz`

**SDK:** https://github.com/elliottech/lighter-python

**Rate Limits:** Not documented

**Public Endpoints:**

### Instruments / Markets
- Likely: `/markets` or `/perpetuals`
- SDK docs folder: https://github.com/elliottech/lighter-python/tree/main/docs

### Funding Rate
- Need to check SDK methods for funding data
- Docs minimal; may need SDK inspection

### Orderbook
- Likely: `/orderbook` endpoint
- May be accessible via SDK

**Notes:**
- Documentation sparse; SDK exploration required

---

## Ethereal

**Base URL:** Need to extract from docs

**SDK:** https://meridianxyz.github.io/ethereal-py-sdk/

**Rate Limits:** Not documented in quick review

**Public Endpoints:**

### Instruments
- Likely perp market list endpoint
- SDK reference needed

### Funding Rate
- Funding endpoint (may be under `/funding` or market data)

### Orderbook
- Orderbook snapshot endpoint

**Notes:**
- SDK provides Python bindings
- Public data structure needs verification via docs/SDK

---

## Summary

| Venue | Instruments | Funding | Mark/Index/Last | Orderbook | SDK |
|--------|------------|---------|----------------|-----------|-----|
| OKX     | ✅         | ✅      | ✅            | ✅   | -   |
| Hyperliquid | ✅         | ✅      | ✅            | ✅   | ✅   |
| Paradex    | ⚠️   | ⚠️      | ⚠️           | ⚠️   | ✅   |
| Lighter    | ⚠️   | ⚠️      | ⚠️           | ⚠️   | ✅   |
| Ethereal   | ⚠️   | ⚠️      | ⚠️           | ⚠️   | ✅   |

**Legend:**
- ✅ = Clear docs/example
- ⚠️ = Needs investigation/testing
- ❌ = Not available

**Priority for Implementation:**
1. OKX (all endpoints documented)
2. Hyperliquid (all endpoints documented + SDK)
3. Paradex (needs API investigation)
4. Lighter (needs SDK exploration)
5. Ethereal (needs SDK exploration)
