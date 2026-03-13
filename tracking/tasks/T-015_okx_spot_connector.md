# T-015: OKX SPOT Connector Implementation

**Status:** ✅ Complete
**Date:** 2025-01-02
**Model:** zai/glm-4.7

## Goal
Extend OKX connector + pull script to ingest SPOT instruments + spot prices + orderbook top to enable spot↔perp basis trades.

## Completed Tasks

### 1. Updated `tracking/connectors/okx_public.py`
- ✅ Added `get_spot_instruments()` function
  - Pulls SPOT instruments using `instType=SPOT`
  - Returns list with instId, base, quote, tickSize, contractSize
  - fundingIntervalHours set to 0 (no funding for spot)

- ✅ Added `get_spot_tickers()` function
  - Uses `/market/tickers` endpoint (not `/public/tickers`)
  - Fetches last, bid, ask for all SPOT instruments in one call
  - Calculates mid price from bid/ask
  - Avoids expensive individual orderbook calls

- ✅ Updated `_get()` helper function
  - Added support for `/market/` endpoints
  - Maintains backward compatibility with `/public/` endpoints

- ✅ Updated test harness
  - Added SPOT function tests to main block

### 2. Updated `scripts/pull_okx_market.py`
- ✅ Modified `insert_instruments()` to accept `contract_type` parameter
  - Supports both "PERP" and "SPOT" contract types

- ✅ Added `insert_spot_prices()` function
  - Inserts spot prices with bid/ask/mid/last
  - Uses last price as mark_price (no mark price for spot)
  - Stores full orderbook top data

- ✅ Updated `main()` function
  - Pulls and inserts SPOT instruments (contract_type='SPOT')
  - Pulls and inserts SPOT tickers (bid/ask/mid/last)
  - Keeps existing PERP ingestion intact
  - Uses `normalize_symbol()` and `normalize_instrument_id()` for canonicalization

### 3. Created `scripts/test_okx_spot_public.py`
- ✅ Tests SPOT public API endpoints
- ✅ Validates DB insertion for instruments and prices
- ✅ Verifies spot↔perp pairs with basis calculations
- ✅ Checks for major pairs (BTC/ETH/SOL)

### 4. DB Verification
- ✅ OKX SPOT instruments: 725 (initial pull)
- ✅ OKX SPOT prices: 725 (initial pull)
- ✅ Sample spot↔perp pairs verified:
  - BTC: SPOT and PERP prices available
  - ETH: SPOT and PERP prices available
  - SOL: SPOT and PERP prices available

### 5. Documentation
- ✅ Created task notes (this file)
- ✅ All functions documented with docstrings
- ✅ Constraints met:
  - Public endpoints only
  - No individual orderbook calls (uses tickers endpoint)
  - Symbol normalization via `tracking/symbols.py`

## Implementation Details

### API Endpoints Used
- **SPOT Instruments:** `GET /api/v5/public/instruments?instType=SPOT`
- **SPOT Tickers:** `GET /api/v5/market/tickers?instType=SPOT`

### Data Model
- **SPOT Instruments:** stored with `contract_type='SPOT'`
  - `funding_interval_hours` = 0 (no funding)
  - `contract_size` = minimum lot size
- **SPOT Prices:** stored in `prices` table
  - `mark_price` = last price (no mark price for spot)
  - `index_price` = NULL (not applicable to spot)
  - `bid`, `ask`, `mid` from tickers endpoint

### Symbol Normalization
- Uses `normalize_symbol("okx", instId)` → canonical base asset
- Uses `normalize_instrument_id("okx", instId)` → full instId
- Example: "BTC-USDT" → symbol="BTC", inst_id="BTC-USDT"

## Testing Results

```
=== Testing OKX SPOT Public Endpoints ===

1. Testing get_spot_instruments()...
   ✓ Retrieved 725 SPOT instruments
   Sample: USDT-SGD
   - Base: USDT, Quote: SGD
   - Tick size: 0.0001, Contract size: 0.001

2. Testing get_spot_tickers()...
   ✓ Retrieved 725 SPOT tickers
   Sample: ENA-USD
   - Last: 0.1232, Bid: 0.1255, Ask: 0.1259, Mid: 0.1257

3. Checking major pairs...
   ✓ BTC/USDT: mid = 69306.95
   ✓ ETH/USDT: mid = 2055.855
   ✓ SOL/USDT: mid = 86.205
```

## Notes

- The `/market/tickers` endpoint returns bid/ask for all instruments efficiently
- SPOT instruments include multiple quote currencies (USDT, USD, USDC, EUR, etc.)
- Symbol normalization correctly handles all OKX formats
- Data is stored in same DB tables as PERP, distinguished by `contract_type`

## Next Steps

The SPOT connector is fully functional. To compute spot↔perp basis trades:
1. Query latest SPOT mid prices by symbol
2. Query latest PERP mark prices by symbol
3. Calculate basis = PERP_price - SPOT_price
4. Calculate basis percentage = (basis / SPOT_price) * 100
5. Filter for basis exceeding thresholds

Example query:
```sql
SELECT
  p1.symbol,
  p1.mid as spot_mid,
  p2.mark_price as perp_mid,
  (p2.mark_price - p1.mid) as basis,
  ((p2.mark_price - p1.mid) / p1.mid * 100) as basis_pct
FROM prices p1
JOIN instruments i1 ON p1.venue = i1.venue AND p1.symbol = i1.symbol
JOIN prices p2 ON p1.symbol = p2.symbol
JOIN instruments i2 ON p2.venue = i2.venue AND p2.symbol = i2.symbol
WHERE i1.contract_type = 'SPOT' AND i2.contract_type = 'PERP'
  AND p1.venue = 'okx' AND p2.venue = 'okx'
  AND p1.ts = (SELECT MAX(ts) FROM prices WHERE venue='okx' AND symbol=p1.symbol)
  AND p2.ts = (SELECT MAX(ts) FROM prices WHERE venue='okx' AND symbol=p2.symbol)
```

## Docs
- docs/CONNECTORS.md
- docs/CONVENTIONS.md
- docs/RUNBOOK.md
- docs/DESIGN_v3.md

