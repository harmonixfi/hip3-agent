# Felix Equities Auth — Implementation Notes

Felix uses Turnkey's wallet-stamper protocol for headless JWT authentication.

## Auth Flow

```
1. POST authproxy.turnkey.com/v1/account
   headers: x-auth-proxy-config-id: cc6ef853-...
   body: {filterType: "PUBLIC_KEY", filterValue: <compressed-wallet-pubkey>}
   → {organizationId: <sub-org-id>}           # no auth required

2. Generate ephemeral secp256k1 session keypair (fresh each login)

3. POST api.turnkey.com/public/v1/submit/stamp_login
   headers: X-Stamp: <EIP-191 stamp signed by wallet key>
   body: {
     organizationId: "b052e625-..." (ROOT org, always),
     parameters: {
       publicKey: <ephemeral-session-pubkey>,
       expirationSeconds: "1209600"            # 14 days
     }
   }
   → JWT (ES256, 14-day TTL)
```

## Key Constants

| Constant | Value |
|---|---|
| `FELIX_ORG_ID` | `b052e625-0ea1-4e6a-b3a4-dd3d8e06f636` (root org) |
| `FELIX_AUTH_PROXY_CONFIG` | `cc6ef853-e2e2-45db-a0f8-7c46be0ad04f` |
| `FELIX_PROXY_BASE` | `https://spot-equities-proxy.white-star-bc1e.workers.dev` |
| `JWT_TTL_SECONDS` | `1209600` (14 days) |
| `REFRESH_BUFFER_SECONDS` | `86400` (refresh 1 day before expiry) |

## Env Vars Required

```bash
FELIX_WALLET_ADDRESS=0x...        # EVM wallet address
FELIX_WALLET_PRIVATE_KEY=...      # secp256k1 hex (32 bytes, no 0x prefix)
```

## X-Stamp Header

Turnkey requires every authenticated request to carry `X-Stamp` — a base64url-encoded JSON:

```json
{
  "publicKey": "<compressed-secp256k1-wallet-pubkey>",
  "signature": "<DER-encoded ECDSA sig>",
  "scheme": "SIGNATURE_SCHEME_TK_API_SECP256K1_EIP191"
}
```

Signing: EIP-191 `personal_sign` over the raw POST body bytes using the wallet's secp256k1 private key (`eth_account.sign_message` with `encode_defunct`).

## Important: Cloudflare WAF

Both `authproxy.turnkey.com` and `api.turnkey.com` require browser-like headers:

```python
"Origin": "https://trade.usefelix.xyz",
"Referer": "https://trade.usefelix.xyz/",
"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
```

Without these, Cloudflare returns HTTP 403 error 1010 "browser_signature_banned".

## Session Storage

JWT + sub-org ID are stored in `vault/felix_session.enc.json` (sops-encrypted). The cron script also writes `felix_jwt_expires_at` to `vault/secrets.enc.json` for the `/api/health` endpoint.

## Cron

```cron
0 */12 * * *  python scripts/felix_jwt_refresh.py
```

Runs every 12 hours. `needs_refresh()` triggers at 24h before expiry, so worst-case the JWT is still valid for ~12.5 days when refreshed.

## Code

- `tracking/connectors/felix_auth.py` — core auth logic
- `scripts/felix_jwt_refresh.py` — cron refresh script
- `tests/test_felix_auth.py` — unit tests (no credentials needed)
- `tests/test_felix_e2e.py` — E2E tests (requires `FELIX_WALLET_PRIVATE_KEY`)

## Run E2E Tests

```bash
source .arbit_env
.venv/bin/python -m pytest tests/test_felix_e2e.py -v
```

## Common Mistakes

| Mistake | Correct |
|---|---|
| Use `list_suborgs` API for sub-org lookup | Use `authproxy.turnkey.com/v1/account` with `PUBLIC_KEY` filter |
| Put sub-org ID in `stamp_login.organizationId` | Always use ROOT org `FELIX_ORG_ID` |
| Put wallet's own pubkey in `parameters.publicKey` | Generate fresh ephemeral secp256k1 keypair per session |
| Use custom `User-Agent` | Use browser-like User-Agent + Origin/Referer headers |
