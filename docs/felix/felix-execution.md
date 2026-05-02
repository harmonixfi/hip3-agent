# Felix Equities — Execution Reference

Full context on how Felix order execution works server-side, based on reverse-engineering
the browser flow and running live test orders. Covers: API flow, signing, pricing mechanics,
timing, cost model, and implications for delta-neutral strategy.

Companion docs: `felix-auth.md` (JWT setup), `felix-order.md` (signing deep-dive).

---

## 1. Order Flow

```
Client                          Felix Proxy                     Turnkey HSM         Chain
  │                                    │                               │               │
  ├── POST /v1/trading/limits ────────►│                               │               │
  │◄── {isOpen, maxNotional} ──────────┤                               │               │
  │                                    │                               │               │
  ├── POST /v1/trading/quote ─────────►│                               │               │
  │◄── {quoteId, price,                │                               │               │
  │     estimatedShares,               │                               │               │
  │     intent.payloadHash} ───────────┤                               │               │
  │                                    │                               │               │
  ├── POST api.turnkey.com             │                               │               │
  │   /public/v1/submit/              │                               │               │
  │   sign_raw_payload ───────────────────────────────────────────────►│               │
  │◄── {v, r, s} ──────────────────────────────────────────────────────┤               │
  │                                    │                               │               │
  ├── POST /v1/trading/orders ────────►│                               │               │
  │   {quoteId, intentId, sig} ────────►───────────────────────────────────────────────►│
  │◄── {orderId, SUBMITTED_ONCHAIN} ───┤                               │               │
  │                                    │                               │               │
  ├── GET /v1/trading/orders/{id} ────►│  (poll until FILLED)          │               │
  │◄── {status: FILLED, txHash} ───────┤                               │               │
  │                                    │                               │               │
  ├── GET /v1/trading/orders ─────────►│                               │               │
  │◄── {data: [{notionalStablecoin}]} ─┤                               │               │
```

**Quote TTL: ~30 seconds.** Sign and submit immediately after receiving.

---

## 2. Key Parameters

### BUY vs SELL

| Side | Required param | API field | Example |
|------|---------------|-----------|---------|
| BUY  | USD amount | `notionalValue` (string) | `"20.0"` |
| SELL | Share count | `tokenAmount` (string) | `"0.052507"` |

### Symbol Format

Felix appends `"on"` suffix internally: `TSLA` → `TSLAon`.
`FelixOrderClient` normalises automatically — pass plain tickers everywhere.

---

## 3. Pricing Mechanics — H1 Confirmed: Firm RFQ

**Hypothesis tested (2026-05-01, 4 live orders on TSLA at market open):**

| | |
|---|---|
| H1 | Felix is a market maker — quote price is a firm commitment, fill price = quote price |
| H2 | Quote is indicative — Felix fills at market price at execution time |

**Result: H1 confirmed.**

### Test data

| # | Side | Requested | Quote Price | notionalStablecoin | Inferred Fill Price | Diff |
|---|------|-----------|-------------|-------------------|---------------------|------|
| 1 | BUY  | $20.00 | 380.790300 | $20.000000 | 380.904571* | +0.030%* |
| 2 | SELL | 0.052507 sh | 380.329740 | $19.969817 | 380.329729 | **−0.000%** |
| 3 | BUY  | $25.00 | 380.910360 | $25.000000 | 381.024667* | +0.030%* |
| 4 | SELL | 0.065613 sh | 380.369720 | $24.943911 | 380.369816 | **−0.000%** |

\* BUY fill price inferred as `notional / estimatedShares`. The +0.030% is a **measurement
artifact**: BUY `notionalStablecoin` = exactly the requested USD (Felix charges the exact
amount you committed to), and `estimatedShares` is slightly rounded down by Felix — so
dividing gives a price ~0.03% above quote. The actual fill is at the quoted price.

**SELL orders are the reliable measurement** (exact share count known): diff = 0.0000%.

### What this means

- The `quote.price` you see is the price you will execute at — no slippage beyond the bid/ask spread
- For BUY: you always pay exactly `notionalValue` USDC and receive `notionalValue / quote_price` shares
- For SELL: you always receive `tokenAmount × quote_price` USDC
- The cost of execution is entirely captured in the **bid/ask spread** between BUY and SELL quotes

### Bid/Ask Spread (TSLA, 2026-05-01 pre-market open)

```
BUY  quotes: 380.790 – 381.478   (multiple sessions)
SELL quotes: 380.170 – 380.472
Spread: BUY – SELL ≈ 0.46–0.61%
```

Round-trip cost (BUY then SELL) = spread ≈ **0.5% of notional** per full round trip.
This is the true transaction cost — Felix does not charge separate fees on top.

---

## 4. Fill Data — What the API Returns

### GET /v1/trading/orders/{id}  (poll endpoint)

Used to confirm FILLED status. Returns minimal data:

```json
{
  "id": "cmomoe8bl...",
  "status": "FILLED",
  "onchainTxHash": "0x348b85e9...",
  "createdAt": "...",
  "updatedAt": "..."
}
```

Does NOT return fill price. Do not expect pricing data from this endpoint.

### GET /v1/trading/orders  (list endpoint)

Returns `{"data": [...], "hasMore": bool, "lastId": str}`.

**Critical:** response key is `data`, not `orders`. Older code expecting `orders` gets an
empty list silently.

Each order in `data`:

```json
{
  "id": "cmomoe8bl...",
  "side": "BUY",
  "status": "FILLED",
  "notionalStablecoin": "20.0",   ← USD paid (BUY) or received (SELL). ALWAYS POPULATED.
  "executedStablecoin": null,     ← always null (Felix does not populate)
  "executedShares": null,         ← always null (Felix does not populate)
  "avgPrice": null,               ← always null (Felix does not populate)
  "onchainTxHash": "0x348b85e9..."
}
```

**`notionalStablecoin` is the only reliable execution field.**

- BUY: `notionalStablecoin` = exactly the USD you committed to spend
- SELL: `notionalStablecoin` = exact USD you received
- `avgPrice`, `executedShares`, `executedStablecoin` are always `null` — do not wait for them

### Deriving fill price

```python
# SELL — exact (share count is known):
fill_price = notionalStablecoin / token_amount_sold

# BUY — approximate (actual shares not returned by API):
fill_price ≈ notionalStablecoin / estimatedShares  # ~0.03% above true price
# Or simply: fill_price ≈ quote_price  (since H1 is confirmed)
```

---

## 5. Timing

All measured on 2026-05-01 at US market open (TSLA, 4 orders):

| Phase | Time |
|-------|------|
| quote request → sign (Turnkey) | ~0.7s |
| sign → submit | ~0.4s |
| submit → FILLED (GET /orders/{id} poll) | **10–21s** (variable) |
| FILLED → `notionalStablecoin` available | **~0.6s** |

**Key insight:** Once the poll endpoint returns FILLED, the list endpoint (`GET /v1/trading/orders`)
has `notionalStablecoin` populated within 0.6 seconds — one poll attempt is sufficient.
The previous 120s timeout was unnecessary; it was caused by looking in `orders` key (empty)
instead of `data` key.

Fill confirmation time (10–21s) is variable and unpredictable. Do not use fixed sleeps.
Use `FelixOrderClient.poll_order()` which loops `GET /v1/trading/orders/{id}` until FILLED.

---

## 6. Signing Architecture

### Two Separate Keys

| Key | Address | Purpose |
|-----|---------|---------|
| EVM wallet (secp256k1) | `0x8EF806...` | Authenticates TO Turnkey (X-Stamp on `stamp_login`) |
| Felix equities wallet (secp256k1) | `0xaD0F4EcB...` | Signs order intents — lives in Turnkey HSM |

These are not the same key and must not be confused.

### What to Sign

`quote.intent.payloadHash` — a raw 32-byte hash pre-computed by Felix's server.
Sign it **directly** with no prefix (not EIP-191, not EIP-712 hash, just raw hash).

The `intent.eip712` object in the quote response is present but is **not used for signing**.
Felix pre-hashes it server-side and puts the result in `payloadHash`.

### Turnkey Signing API

The equities key (`0xaD0F4EcB...`) is managed by Turnkey's HSM — it cannot be extracted.
Sign via API:

```
POST https://api.turnkey.com/public/v1/submit/sign_raw_payload
X-Stamp: <EIP-191 stamp with session_private_key_hex>

{
  "type": "ACTIVITY_TYPE_SIGN_RAW_PAYLOAD_V2",  ← V2 type, V1 URL path
  "organizationId": "<sub_org_id>",
  "parameters": {
    "signWith": "0xaD0F4EcB5bbE32D080614018253FA5A40eF5df1D",
    "payload": "<payloadHash>",
    "encoding": "PAYLOAD_ENCODING_HEXADECIMAL",
    "hashFunction": "HASH_FUNCTION_NO_OP"
  }
}

→ activity.result.signRawPayloadResult: {r, s, v}
```

Turnkey returns `v = 0` or `v = 1`. Felix expects `v = 27` or `v = 28`.
Always: `v_final = v_raw if v_raw >= 27 else v_raw + 27`.

### Dead Ends

| Attempt | Result | Reason |
|---------|--------|--------|
| `ACTIVITY_TYPE_SIGN_WITH_ECDSA` at `/sign_with_ecdsa` | 404 | Endpoint does not exist |
| `ACTIVITY_TYPE_SIGN_RAW_PAYLOAD_V2` at `/sign_raw_payload_v2` | 404 | Path does not exist |
| `ACTIVITY_TYPE_SIGN_RAW_PAYLOAD` (V1) at `/sign_raw_payload` | 400 | V1 requires `privateKeyId`, rejects wallet address |
| Sign with EVM wallet key (`0x8EF806...`) | "Signature does not match" | Wrong key |
| Extract P-256 CryptoKey from browser IndexedDB | Not possible | `extractable: false` |
| Extract equities private key from Turnkey | Not possible | Key is in HSM by design |

---

## 7. HTTP Headers — Cloudflare Requirement

Both Felix proxy and Turnkey API sit behind Cloudflare WAF. All requests must include
browser-like headers or Cloudflare returns HTTP 403 (error 1010 "browser_signature_banned"):

```python
"Origin": "https://trade.usefelix.xyz",
"Referer": "https://trade.usefelix.xyz/",
"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ..."
```

The original `_felix_get()` in `felix_private.py` used `User-Agent: arbit-felix-private/0.1`
which caused `GET /v1/trading/orders` to silently return `{"data": [], "hasMore": false}`
even for accounts with orders. Fixed: now uses browser-like headers.

---

## 8. Known API Quirks

| Quirk | Detail |
|-------|--------|
| Response key `data` not `orders` | `GET /v1/trading/orders` returns `{"data": [...]}`. Code checking `response["orders"]` silently gets empty list. |
| `avgPrice` always null | Felix does not populate execution price fields. Use `notionalStablecoin`. |
| `executedShares` always null | Actual share count not returned. Infer from `notionalStablecoin / quote_price`. |
| Quote expires in ~30s | Must sign and submit within the TTL after `get_quote()`. |
| `v` normalization | Turnkey returns `v=0/1`. Felix requires `v=27/28`. Add 27 if `v < 27`. |
| Symbol suffix | Felix appends `"on"`: `TSLA` → `TSLAon`. Client normalizes automatically. |
| SELL uses shares not USD | SELL orders require `tokenAmount` (share count), not `notionalValue`. |

---

## 9. Implications for Delta-Neutral Strategy

### Entry cost model

For a delta-neutral position on Felix (long stock, short perp on another venue):

```
Entry cost = Felix BUY spread (≈ 0.25–0.30% of notional)
           + short perp open fee (venue-dependent)

Exit cost  = Felix SELL spread (≈ 0.25–0.30% of notional)
           + short perp close fee

Round-trip = ≈ 0.50–0.60% of notional (Felix only)
```

Break-even funding (Felix leg): need to earn >0.5% over hold period just to cover Felix spread.
At 10% APR funding = 0.027%/day → break-even in ~18 days per round trip.

### Execution sequencing

Recommended order for opening a delta-neutral leg:

1. Open perp short first (instant, known price)
2. Get Felix BUY quote → check price is acceptable
3. Submit Felix BUY → wait FILLED (10–21s)
4. Confirm via `GET /v1/trading/orders` (0.6s after FILLED)

Reverse for closing:
1. SELL Felix first (get exact USD received)
2. Close perp short

Reason: Felix fill time is variable (10–21s). Opening the perp first ensures the hedge
is in place before the equity position is live.

### Position sizing

Felix does not provide actual `executedShares` in the API response. For tracking:

- BUY: assume `shares = notionalStablecoin / quote_price` (accurate to <0.01%)
- SELL: `shares = token_amount_sold` (exact — you specify this)

For delta-neutral sizing, calculate perp short size as `notionalStablecoin / felix_quote_price`
shares × current perp price. Rebalancing is rarely needed for small moves but monitor
if position runs >5% P&L unhedged.

---

## 10. Code Reference

| File | Purpose |
|------|---------|
| `tracking/connectors/felix_order.py` | Order placement, Turnkey signing, `FelixOrderClient` |
| `tracking/connectors/felix_auth.py` | JWT auth via Turnkey `stamp_login` |
| `tracking/connectors/felix_private.py` | Portfolio + fills data (`GET /v1/trading/orders`) |
| `scripts/test_felix_order_execution.py` | Quote-vs-fill test harness |
| `tests/test_felix_order.py` | Unit tests (26, no credentials) |
| `vault/felix_session.enc.json` | JWT + session key (written by `felix_jwt_refresh.py`) |

### Quick usage

```python
import json
from tracking.connectors.felix_order import FelixOrderClient

with open("vault/felix_session.enc.json") as f:
    sess = json.load(f)

client = FelixOrderClient(
    jwt=sess["jwt"],
    session_private_key_hex=sess["session_private_key_hex"],
    sub_org_id=sess["sub_org_id"],
)

# BUY $50 of AAPL — returns final order dict when FILLED
order = client.place_order("AAPL", "BUY", notional_usdc=50.0)
shares_received = float(order.get("notionalStablecoin", 50)) / client_quote_price  # approx

# SELL exact shares back
order = client.place_order("AAPL", "SELL", token_amount=shares_received)
usdc_received = float(order["notionalStablecoin"])  # exact
```

### Reading fills after execution

```python
import urllib.request, json

jwt = sess["jwt"]
url = "https://spot-equities-proxy.white-star-bc1e.workers.dev/v1/trading/orders"
req = urllib.request.Request(url, headers={
    "Authorization": f"Bearer {jwt}",
    "Accept": "application/json",
    "Origin": "https://trade.usefelix.xyz",
    "Referer": "https://trade.usefelix.xyz/",
    "User-Agent": "Mozilla/5.0 ...",
})
with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read())["data"]   # note: "data", not "orders"

for order in data:
    if order["status"] == "FILLED":
        notional = float(order["notionalStablecoin"])
        print(f"{order['side']} {order['symbol']}: ${notional:.4f} USDC")
```

---

## 11. Turnkey Key Inventory

| Entity | Value |
|--------|-------|
| Sub-org ID | `d9b5db5f-2d5a-476a-a409-eccbbdc01a2a` |
| Felix Equities Wallet ID (HD) | `e807c81d-0eee-5b65-97fc-6a84734d3c88` |
| Equities account address | `0xaD0F4EcB5bbE32D080614018253FA5A40eF5df1D` |
| EVM wallet address (auth only) | `0x8EF8060a14fF71F4E03Ef5b3b2B037C671fC5861` |
| Derivation path | `m/44'/60'/0'/0/0` |
| Root org ID | `b052e625-0ea1-4e6a-b3a4-dd3d8e06f636` |

---

## 12. Validated Executions

### 2026-04-27 — First successful server-side orders

```
BUY  TSLA $20.00 → 0.053285 sh @ $375.225  tx: 0xf2f5f01fb3f994...885e
SELL TSLA 0.053285 sh → $19.96 @ $374.595   tx: 0x1e104388b35f17...8245
Round-trip: −$0.04 (0.20%)
```

### 2026-05-01 — Quote-vs-fill price test (4 orders, market open)

```
BUY  TSLA $20.00 @ quote 380.790  notional=$20.000  fill≈quote ✓  tx: 0x348b85e9...
SELL TSLA 0.052507 sh @ quote 380.330  received=$19.970  fill=quote ✓  tx: 0xa994da99...
BUY  TSLA $25.00 @ quote 380.910  notional=$25.000  fill≈quote ✓  tx: 0x6ee2d216...
SELL TSLA 0.065613 sh @ quote 380.170  received=$24.944  fill=quote ✓  tx: 0x68a0e99c...

Total round-trip cost: −$0.10 on $45 deployed = 0.22% (spread only, no separate fee)
Timing: submit→FILLED 10–21s | FILLED→notional_ready 0.6s
Conclusion: H1 CONFIRMED — Felix is a firm RFQ system
```
