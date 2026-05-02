# Felix Equities Order Placement — Implementation Notes

Headless server-side order placement for Felix equities (buy/sell tokenized stocks).
Auth prerequisite: `felix-auth.md` must be set up first (JWT + session key in vault).

## Order Flow

```
1. POST /v1/trading/limits
   body: {symbol: "TSLAon", side: "BUY"}
   → {isOpen: true, maxNotionalValue: 487500, remainingAttestations: 150}

2. POST /v1/trading/quote
   body: {symbol: "TSLAon", side: "BUY", stablecoin: "USDC", notionalValue: "20.0"}
   → {id: quoteId, price, estimatedShares, expiresAt, intent: {id, payloadHash, eip712}}

3. Sign intent.payloadHash via Turnkey API
   → {v: 27|28, r: "0x...", s: "0x..."}

4. POST /v1/trading/orders
   body: {quoteId, intentId, signature: {v, r, s}}
   → {id: orderId, status: "SUBMITTED_ONCHAIN"}

5. GET /v1/trading/orders/{orderId}  (poll until terminal)
   → {status: "FILLED", onchainTxHash: "0x..."}
```

Quote expires in ~30 seconds — sign and submit immediately after receiving.

## BUY vs SELL Parameters

| Side | Required param | Example |
|------|---------------|---------|
| BUY  | `notionalValue` (USD string) | `"20.0"` |
| SELL | `tokenAmount` (shares string) | `"0.053285362116063695"` |

## Symbol Format

Felix market symbols append `"on"` suffix: `TSLA` → `TSLAon`.
`FelixOrderClient` normalizes automatically — pass plain tickers everywhere.

## Signing Architecture

### Two Separate Keys

| Key | Address | Purpose |
|-----|---------|---------|
| EVM wallet key | `0x8EF806...` | Auth only — Turnkey `stamp_login` (X-Stamp) |
| Felix equities key | `0xaD0F4EcB...` | Signs order intents — lives in Turnkey HSM |

These are **not the same key**. The EVM wallet key authenticates TO Turnkey.
The equities key is managed BY Turnkey and signs orders on your behalf.

### What Gets Signed

Felix returns `intent.payloadHash` in the quote response. This is a raw 32-byte hash
(pre-computed by Felix's server). Sign it **directly** — no EIP-191 prefix, no additional hashing.

Confirmed via ecrecover on a browser-captured signature:
```python
Account._recover_hash(bytes.fromhex(payload_hash[2:]), vrs=(v, r, s)) == "0xaD0F4EcB..."
```

The `intent.eip712` object is present in the response but is NOT used for signing
(Felix computes `payloadHash` server-side and signs that directly).

### Turnkey Signing API

The equities key (`0xaD0F4EcB...`) is a Turnkey-managed wallet account key stored in
Turnkey's HSM. It cannot be extracted. Sign via Turnkey's API:

```
POST api.turnkey.com/public/v1/submit/sign_raw_payload
headers:
  X-Stamp: <EIP-191 stamp signed by session_private_key_hex>
body:
  {
    "type": "ACTIVITY_TYPE_SIGN_RAW_PAYLOAD_V2",
    "timestampMs": "<ms>",
    "organizationId": "<sub_org_id>",
    "parameters": {
      "signWith": "0xaD0F4EcB5bbE32D080614018253FA5A40eF5df1D",
      "payload": "<payloadHash>",
      "encoding": "PAYLOAD_ENCODING_HEXADECIMAL",
      "hashFunction": "HASH_FUNCTION_NO_OP"
    }
  }
response:
  activity.result.signRawPayloadResult → {r, s, v}
```

**Critical**: Use `ACTIVITY_TYPE_SIGN_RAW_PAYLOAD_V2` (not V1) — V2 accepts `signWith`
as a wallet account address. V1 requires `privateKeyId` (standalone private keys only).

**Critical**: URL path is `/sign_raw_payload` (not `/sign_raw_payload_v2`) — the V2
activity type submits to the same path as V1.

**Critical**: Turnkey returns `v = 0` or `v = 1` (raw secp256k1 recovery id).
Felix requires Ethereum-style `v = 27` or `v = 28`. Always add 27 if `v < 27`.

### X-Stamp Authentication for Signing

The X-Stamp on Turnkey signing requests is signed with `session_private_key_hex`
(the ephemeral secp256k1 key generated during `stamp_login`). This key is registered
with Turnkey when the JWT is issued, so Turnkey accepts it for subsequent API calls.

This is the same `build_x_stamp_header()` from `felix_auth.py`.

## Dead Ends (Do Not Retry)

| Attempt | Result | Why |
|---------|--------|-----|
| `ACTIVITY_TYPE_SIGN_WITH_ECDSA` at `/sign_with_ecdsa` | 404 | Endpoint does not exist |
| `ACTIVITY_TYPE_SIGN_RAW_PAYLOAD_V2` at `/sign_raw_payload_v2` | 404 | Path does not exist |
| `ACTIVITY_TYPE_SIGN_RAW_PAYLOAD` (V1) at `/sign_raw_payload` | 400 | V1 requires `privateKeyId`, rejects wallet account address |
| Sign locally with EVM wallet key (`0x8EF806...`) | "Signature does not match" | Wrong key — equities key is required |
| Extract P-256 CryptoKey from browser IndexedDB | Non-extractable | Web Crypto API enforces `extractable: false` |
| Extract equities private key from Turnkey | Not possible | Key lives in Turnkey HSM by design |

## Turnkey Key Inventory

| Entity | ID |
|--------|----|
| Sub-org | `d9b5db5f-2d5a-476a-a409-eccbbdc01a2a` |
| Felix Equities Wallet (HD) | `e807c81d-0eee-5b65-97fc-6a84734d3c88` |
| Wallet account address | `0xaD0F4EcB5bbE32D080614018253FA5A40eF5df1D` |
| Derivation path | `m/44'/60'/0'/0/0` |

## Usage

```python
from tracking.connectors.felix_order import FelixOrderClient
import json

with open("vault/felix_session.enc.json") as f:
    sess = json.load(f)

client = FelixOrderClient(
    jwt=sess["jwt"],
    session_private_key_hex=sess["session_private_key_hex"],
    sub_org_id=sess["sub_org_id"],
)

# BUY $20 of TSLA
buy = client.place_order("TSLA", "BUY", notional_usdc=20.0)
# buy["status"] == "FILLED"
# buy["onchainTxHash"] == "0x..."

# SELL back (use estimatedShares from quote, or exact balance)
sell = client.place_order("TSLA", "SELL", token_amount=0.053285)
```

`place_order()` is end-to-end: limits → quote → sign → submit → poll until FILLED.
Returns the final order dict. Raises `RuntimeError` on any failure, `TimeoutError` if
poll exceeds 90 seconds.

## Code

- `tracking/connectors/felix_order.py` — order client + Turnkey signing
- `tracking/connectors/felix_auth.py` — JWT auth (prerequisite)
- `tests/test_felix_order.py` — 26 unit tests (no credentials needed)

## Env / Vault Requirements

No additional env vars needed beyond what `felix_auth.py` uses.
`vault/felix_session.enc.json` must contain `session_private_key_hex` — this is written
automatically by `scripts/felix_jwt_refresh.py` after the auth overhaul.

## Validated End-to-End (2026-04-27)

```
BUY  TSLA $20.00 → 0.053285 shares @ $375.225  tx: 0xf2f5f01fb3f994...885e
SELL TSLA 0.053285 shares → $19.96 @ $374.595   tx: 0x1e104388b35f17...8245
Round-trip cost: ~$0.04 (0.2%)
```
