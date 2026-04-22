---
name: hyperliquid
description: Use when querying Hyperliquid spot/perp data — order books, funding rates, 24h volume, OI, or USDT0/USDC swap pricing. Use for liquidity assessment before entry/exit, funding rate screening, and spot-perp delta-neutral analysis.
---

# Hyperliquid API Skill

---

## Section A: Technical Reference

### API Overview

**Endpoint**: `https://api.hyperliquid.xyz/info`  
**Method**: POST JSON — no auth, no API key  
**Stdlib only**: `urllib.request` + `json`

```python
import urllib.request, json

def hl_post(payload: dict):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.hyperliquid.xyz/info", data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())
```

### Request Types

| Type | Payload | Returns |
|------|---------|---------|
| `spotMeta` | `{"type": "spotMeta"}` | All spot pairs + token list |
| `spotMetaAndAssetCtxs` | `{"type": "spotMetaAndAssetCtxs"}` | Spot metadata + 24h volume/price |
| `metaAndAssetCtxs` | `{"type": "metaAndAssetCtxs"}` | Perp universe + funding/OI/volume |
| `l2Book` | `{"type": "l2Book", "coin": "BTC"}` | L2 order book (all levels) |
| `frontendOpenOrders` | `{"type": "frontendOpenOrders", "user": "0x..."}` | Open orders + frontend fields (orderType, tif, triggerPx, reduceOnly) |
| `openOrders` | `{"type": "openOrders", "user": "0x..."}` | Open orders (basic fields only) |

### Coin Format

| Context | Format | Example |
|---------|--------|---------|
| Perp `l2Book` | Symbol directly | `"BTC"`, `"HYPE"`, `"BNB"` |
| Spot `l2Book` | `@{index}` from spotMeta | `"@107"` (HYPE/USDC), `"@166"` (USDT0/USDC) |

**Common spot pair indices** (stable, but verify at runtime with spotMeta):
- HYPE/USDC: `@107`
- UBTC/USDC: `@142`
- UETH/USDC: `@151`
- USDT0/USDC: `@166`
- HYPE/USDT0: `@207`

### Response Structures

**`spotMeta`**:
```python
{
  "universe": [
    {"tokens": [base_idx, quote_idx], "name": "PURR/USDC", "index": 0, "isCanonical": true},
    {"tokens": [base_idx, quote_idx], "name": "@1", "index": 1, "isCanonical": false},
    ...
  ],
  "tokens": [
    {"name": "USDC", "index": 0, "szDecimals": 8, ...},
    {"name": "USDT0", "index": 268, ...},
    ...
  ]
}
# Map: tok_by_idx = {t["index"]: t for t in data["tokens"]}
# Pair token names: tok_by_idx[pair["tokens"][0]]["name"], tok_by_idx[pair["tokens"][1]]["name"]
```

**`metaAndAssetCtxs`** (perp):
```python
[
  {"universe": [{"name": "BTC"}, {"name": "ETH"}, ...]},  # index 0 = meta
  [                                                          # index 1 = ctxs (parallel to universe)
    {
      "funding": "-0.0000053",    # per-hour rate (negative = longs pay shorts)
      "openInterest": "26706.3",  # base token units
      "prevDayPx": "76331.0",
      "dayNtlVlm": "3326788717.4", # 24h notional volume USD
      "markPx": "77986.0",
      "midPx": "77986.5",
      "dayBaseVlm": "43568.4"
    },
    ...
  ]
]
# Zip: for u, ctx in zip(data[0]["universe"], data[1]): ...
```

**`spotMetaAndAssetCtxs`**:
```python
[
  {"universe": [...], "tokens": [...]},  # same as spotMeta
  [
    {
      "coin": "PURR/USDC",   # pair name (matches universe[i].name)
      "dayNtlVlm": "441987",  # 24h USD volume
      "markPx": "0.069688",
      "prevDayPx": "0.073238",
      "dayBaseVlm": "6407315.0"
    },
    ...
  ]
]
```

**`l2Book`**:
```python
{
  "coin": "BNB",
  "time": 1776851965759,
  "levels": [
    [  # bids — descending price (best first)
      {"px": "642.03", "sz": "2.298", "n": 2},  # n = num orders
      ...
    ],
    [  # asks — ascending price (best first)
      {"px": "642.08", "sz": "1.500", "n": 1},
      ...
    ]
  ]
}
```

**`frontendOpenOrders`** (returns list):
```python
[
  {
    "coin": "ATOM",         # perp symbol, or "@N" for spot
    "side": "A",             # "A" = ask/sell, "B" = bid/buy
    "limitPx": "1.9066",
    "sz": "378.0",           # remaining size
    "origSz": "378.0",       # original size
    "oid": 392529364881,     # order ID (use for cancels)
    "timestamp": 1776855492273,
    "orderType": "Limit",    # "Limit", "Trigger Market", "Trigger Limit"
    "tif": "Alo",            # "Alo" = post-only, "Gtc", "Ioc"
    "reduceOnly": false,
    "isTrigger": false,
    "triggerPx": "0.0",
    "triggerCondition": "N/A",
    "isPositionTpsl": false, # position-level TP/SL
    "children": [],          # child orders (bracket orders)
    "cloid": null            # client order ID
  },
  ...
]
```

### Rate & Metric Formulas

```python
# Perp funding
funding_hr  = float(ctx["funding"])          # per hour (e.g., 0.000125 = 0.0125%/hr)
funding_apr = funding_hr * 8760 * 100        # annualized %

# OI in USD
oi_usd = float(ctx["openInterest"]) * float(ctx["markPx"])

# Order book spread
mid = (best_bid + best_ask) / 2
spread_bps = (best_ask - best_bid) / mid * 10_000

# Slippage for size N
# Walk levels: for each level, level_usd = px * sz
# avg_px = total_cost / total_base
# slippage_bps = abs(avg_px - best_px) / best_px * 10_000

# USDT0 swap cost vs $1 parity
sell_vs_parity_bps = (avg_sell_px - 1.0) * 10_000  # positive = above $1 (good for seller)
buy_vs_parity_bps  = (avg_buy_px  - 1.0) * 10_000  # positive = above $1 (cost for buyer)
```

### Yield Farming Use Cases

**Screen funding rates** — `metaAndAssetCtxs` sorted by `|funding × 8760|`:
```python
rows = [(u["name"], float(ctx["funding"]) * 8760 * 100) for u, ctx in zip(universe, ctxs)]
rows.sort(key=lambda x: abs(x[1]), reverse=True)
```

**Liquidity gate check** — Before sizing a position:
1. `l2Book` → check bid/ask depth at target size
2. `metaAndAssetCtxs` → check OI rank (higher = more institutional flow)
3. Compute slippage for entry + exit

**USDT0/USDC swap** — when moving capital between HypurrFi/Felix (uses USDT0) and USDC:
- Use `@166` for USDT0/USDC book
- For large swaps ($100k+), prefer maker orders (post on ask/bid) to avoid taker premium
- Round-trip cost (sell then buy back) increases with size: ~2.5 bps at $20k → ~5 bps at $200k

---

## Section B: Agent CLI Tool

### `hyperliquid_api.py` — Hyperliquid Data Fetcher

**Location**: `.claude/skills/hyperliquid/hyperliquid_api.py`  
**Requirements**: Python 3.9+ stdlib only

#### Usage

```bash
# Perp funding rates (sorted by |APR|, top 30)
python3 .claude/skills/hyperliquid/hyperliquid_api.py --perp-meta

# Filter to specific symbol group
python3 .claude/skills/hyperliquid/hyperliquid_api.py --perp-meta --filter HYPE

# Only perps with >$1M daily volume
python3 .claude/skills/hyperliquid/hyperliquid_api.py --perp-meta --min-vol 1000000

# Funding rate for one symbol
python3 .claude/skills/hyperliquid/hyperliquid_api.py --funding HYPE

# Spot pairs list (all, or filtered)
python3 .claude/skills/hyperliquid/hyperliquid_api.py --spot-meta
python3 .claude/skills/hyperliquid/hyperliquid_api.py --spot-meta --filter HYPE

# Top spot pairs by 24h volume
python3 .claude/skills/hyperliquid/hyperliquid_api.py --spot-volume
python3 .claude/skills/hyperliquid/hyperliquid_api.py --spot-volume --min-vol 100000 --top 20

# L2 order book — perp symbol or @index for spot
python3 .claude/skills/hyperliquid/hyperliquid_api.py --book HYPE
python3 .claude/skills/hyperliquid/hyperliquid_api.py --book @107       # HYPE/USDC spot
python3 .claude/skills/hyperliquid/hyperliquid_api.py --book BNB --levels 20

# USDT0/USDC swap analysis
python3 .claude/skills/hyperliquid/hyperliquid_api.py --usdt0

# Open orders for a wallet (frontendOpenOrders — includes orderType, tif, trigger info)
python3 .claude/skills/hyperliquid/hyperliquid_api.py --open-orders 0xYourWallet
python3 .claude/skills/hyperliquid/hyperliquid_api.py --open-orders 0x... --filter BTC

# JSON output for agent parsing
python3 .claude/skills/hyperliquid/hyperliquid_api.py --perp-meta --json
python3 .claude/skills/hyperliquid/hyperliquid_api.py --book HYPE --json
python3 .claude/skills/hyperliquid/hyperliquid_api.py --usdt0 --json
python3 .claude/skills/hyperliquid/hyperliquid_api.py --open-orders 0x... --json
```

#### Output Fields

**`--perp-meta`**:

| Field | Description |
|-------|-------------|
| Mark Px | Current mark price |
| 24h Vol | Notional USD traded in last 24h |
| OI USD | Open Interest in USD (base × markPx) |
| Fund/hr | Funding rate per hour (%) |
| APR | Annualized funding rate (%) = fund_hr × 8760 |
| 24h% | Price change from previous day |

**`--book COIN`**:

| Field | Description |
|-------|-------------|
| Spread | `(ask - bid) / mid × 10000` bps |
| Bid/Ask Depth | Sum of `px × sz` for shown levels |
| Buy/Sell Slip | Market impact bps at given size (vs best price) |

**`--usdt0`**:

| Field | Description |
|-------|-------------|
| Sell→USDC (vs $1) | Bps above/below $1.0 when selling USDT0; positive = above parity (good) |
| Buy←USDC (vs $1) | Bps above $1.0 paid when buying USDT0; positive = cost |
| Round-trip | `buy_vs_par - sell_vs_par` — full cost of in-and-out swap |

**`--open-orders ADDRESS`**:

| Field | Description |
|-------|-------------|
| Side | Buy (`B`) or Sell (`A`) |
| Type | `Limit`, `Trigger Market`, `Trigger Limit` |
| TIF | `Alo` = post-only/maker-only, `Gtc`, `Ioc` |
| Limit Px | Limit price |
| Size | Remaining (unfilled) size |
| Notional | `limit_px × size` in loan-token units |
| Filled% | `(origSz - sz) / origSz × 100` |
| Age | Time since placement (m/h/d) |
| Flags | `RO` = reduce-only, `TRIG@px` = trigger order, `TPSL` = position-level TP/SL |
| OID | Order ID (use for cancel requests) |

Orders are sorted by coin then by notional descending. Use `--filter SYMBOL` to narrow.

#### Known Limitations

1. **Spot pair indices change**: New pairs are added frequently. Use `--spot-meta --filter X` to find the current index for a token. The `--usdt0` command discovers the index at runtime.
2. **Perp count**: 230+ perps — without `--filter` or `--min-vol`, output can be long. Default `--top 30`.
3. **Funding direction**: Negative funding = shorts pay longs (unusual; spot-perp position earns on short side but OI can be thin).
4. **L2 depth**: Slippage estimate based on visible levels. Very large orders may need full book (`--levels 100`).
5. **Non-canonical spot pairs**: Many spot pairs use `@N` format (non-canonical). `isCanonical=true` pairs have human-readable names.
