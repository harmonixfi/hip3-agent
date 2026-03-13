# T-005 — Paradex public market-data connector

## Goal
Pull Paradex perps mark price + funding.

## Data to pull
- Instrument list (perp contracts)
- Funding rate (current + next funding time)
- Mark price + Index price + Last price
- Orderbook (bid/ask for basis)

## Deliverables
- `tracking/connectors/paradex_public.py`
- `scripts/pull_paradex_market.py`

## Acceptance
- Script stores latest funding + mark price for a list of symbols
- No auth required (public endpoints only)

## Funding Rate Implementation (Feb 7, 2026)

### Endpoint
- **WebSocket URL**: `wss://ws.api.prod.paradex.trade/v1`
- **Channel**: `funding_data` (public channel, no auth required)
- **Subscription message**:
  ```json
  {
    "id": 1,
    "jsonrpc": "2.0",
    "method": "subscribe",
    "params": {"channel": "funding_data"}
  }
  ```

### Sample Response
```json
{
  "method": "subscription",
  "params": {
    "channel": "funding_data",
    "data": {
      "market": "BERA-USD-PERP",
      "funding_index": "-2.314983676759534478",
      "funding_premium": "-0.00550913173271130432",
      "funding_rate": "-0.01070340466085",
      "funding_rate_8h": "-0.0107034",
      "funding_period_hours": 8,
      "created_at": 1770444780108
    }
  }
}
```

### Units and Conversion
- **funding_rate**: Decimal per funding interval (typically 8 hours)
  - Example: `-0.0107034` = -1.07% per 8-hour interval
  - **NOT** bps, **NOT** scaled integer, **NOT** APR
  - Use as-is directly in DB
- **funding_period_hours**: Funding interval (usually 8 for Paradex perps)
- **APR calculation**: `APR = funding_rate * (24 / funding_period_hours) * 365`
  - BERA example: `-0.0107034 * 3 * 365 = -11.72` = -1172% APR

### BERA Current Status (Feb 7, 2026)
- **funding_rate**: ~-0.0127 (varies in real-time)
- **funding_interval_hours**: 8
- **Implied APR**: ~-1392% (extremely negative, matches Loris data)

### Database Schema
```sql
CREATE TABLE funding (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venue TEXT NOT NULL,
    symbol TEXT NOT NULL,
    funding_rate REAL NOT NULL,            -- 8h-equivalent rate (decimal, e.g., 0.0001)
    funding_interval_hours INTEGER,            -- from instruments table
    next_funding_ts INTEGER,               -- epoch ms of next funding event
    ts INTEGER NOT NULL,                  -- epoch ms UTC
    UNIQUE(venue, symbol, ts)
)
```

### Notes
- WebSocket connection runs for ~15 seconds to collect all funding updates
- Each market broadcasts its funding rate at different intervals, so we collect until we have entries for all symbols
- `next_funding_ts` is not provided by Paradex WebSocket API, set to NULL

## Docs
- docs/CONNECTORS.md
- docs/CONVENTIONS.md
- docs/RUNBOOK.md
- docs/DESIGN_v3.md

