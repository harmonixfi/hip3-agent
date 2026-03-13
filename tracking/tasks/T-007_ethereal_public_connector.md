# T-007 — Ethereal public market-data connector

## Goal
Pull Ethereal perps mark price + funding.

## Data to pull
- Instrument list (perp contracts)
- Funding rate (current)
- Mark price + Index price + Last price
- Orderbook (bid/ask for basis)

## Deliverables
- `tracking/connectors/ethereal_public.py` ✓
- `scripts/pull_ethereal_market.py` ✓
- `scripts/test_ethereal_public.py` ✓

## Acceptance
- Script stores latest funding + mark price for a list of symbols ✓
- No auth required (public endpoints only) ✓

## Status
**DONE** - Completed 2026-02-07

## Implementation Notes

### API Endpoints Used
- Base URL: `https://api.ethereal.trade`
- **Products**: `GET /v1/product?order=asc&orderBy=createdAt`
  - Returns instrument list with funding rates
- **Market Price**: `GET /v1/product/market-price?productIds=<uuid>`
  - Returns bestBid, bestAsk, oraclePrice (mark price)

### Data Mapping
- `ticker` → symbol (e.g., "BTCUSD")
- `displayTicker` → display ticker (e.g., "BTC-USD")
- `id` → inst_id (UUID)
- `fundingRate1h` → funding rate (hourly)
- `oraclePrice` → mark price (from Pyth oracle)
- `bestBidPrice` → top bid
- `bestAskPrice` → top ask

### Limitations
1. **Orderbooks**: Only available via WebSocket (BOOK_DEPTH/L2Book streams)
   - This connector uses bestBid/bestAsk from market-price endpoint as a top-level fallback
   - For full orderbook depth (multiple levels), WebSocket integration would be needed

2. **Last Price**: Not explicitly provided in REST API
   - Using `(bid + ask) / 2` as last price estimate

3. **Index Price**: Same as mark price (both from Pyth oracle)
   - Ethereal uses Pyth Lazer as their oracle provider

### Functions Implemented
- `get_instruments()` - Fetch all active perp contracts
- `get_funding()` - Get current 1h funding rates for all instruments
- `get_mark_prices(limit=20)` - Fetch mark/index/last prices
- `get_orderbook(symbol, limit=20)` - Get top bid/ask/mid (uses REST fallback)

### Test Results
```
All tests passed (4/4):
- get_instruments() ✓ (15 instruments)
- get_funding() ✓ (15 funding entries)
- get_mark_prices() ✓ (15 price entries)
- get_orderbook() ✓ (bid/ask/mid for BTCUSD, ETHUSD, SOLUSD)
```

### Database Insertion
Pull script successfully inserts data into `arbit.db`:
- 15 instruments
- 15 funding entries
- 15 price entries
- 10 orderbook entries (top 10 symbols)

### Validation Run (2026-02-07)
- `python3 scripts/test_ethereal_public.py` → PASS (4/4)
- `python3 scripts/pull_ethereal_market.py` → OK
- DB counts (venue='ethereal'): instruments=30, funding=30, prices=30

### Commands to Run

Test connector:
```bash
python3 scripts/test_ethereal_public.py
```

Pull market data:
```bash
python3 scripts/pull_ethereal_market.py
```

Verify data:
```bash
python3 << 'EOF'
import sqlite3
from pathlib import Path

DB_PATH = Path("tracking/db/arbit.db")
conn = sqlite3.connect(DB_PATH)

print("=== Instruments (ethereal) ===")
cursor = conn.execute("SELECT symbol, base_currency, quote_currency FROM instruments WHERE venue='ethereal' LIMIT 5")
for row in cursor:
    print(f"  {row}")

print("\n=== Funding (ethereal) ===")
cursor = conn.execute("SELECT symbol, funding_rate FROM funding WHERE venue='ethereal' LIMIT 5")
for row in cursor:
    print(f"  {row}")

print("\n=== Prices (ethereal) ===")
cursor = conn.execute("SELECT symbol, mark_price, bid, ask FROM prices WHERE venue='ethereal' LIMIT 5")
for row in cursor:
    print(f"  {row}")

conn.close()
EOF
```

## Docs
- docs/CONNECTORS.md
- docs/CONVENTIONS.md
- docs/RUNBOOK.md
- docs/DESIGN_v3.md

