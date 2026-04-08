# Felix headless auth (Turnkey) — handoff notes

Use this doc to restore context in a new session. It summarizes how `scripts/felix_jwt_refresh.py` + `tracking/connectors/felix_auth.py` relate to Turnkey/Felix, what was fixed in code, and what remains blocked on Felix/Turnkey side.

## Goal

Automated JWT for Felix equities API: cron runs `scripts/felix_jwt_refresh.py`, which uses Turnkey (`stamp_login` flow) to obtain a session JWT and stores encrypted session state under `vault/felix_session.enc.json` (when `sops` is available).

## Required configuration

- **`FELIX_WALLET_ADDRESS`** — EVM address (same wallet used in Felix UI).
- **`FELIX_WALLET_PRIVATE_KEY`** — secp256k1 hex for that address (or vault keys `felix_wallet_address` / `felix_wallet_private_key` via `get_secret_with_env_fallback` in the script).

Constants in `tracking/connectors/felix_auth.py` (Felix Turnkey org / proxy) are **not** env-driven: `FELIX_ORG_ID`, Turnkey base URL, etc.

## Health / Settings UI gap (optional)

- `/api/health` reads **`felix_jwt_expires_at`** from `vault/secrets.enc.json` only (`get_secret("felix_jwt_expires_at")`).
- The JWT refresh script **does not** write that key; it only updates `felix_session.enc.json`.
- So Settings can show empty Felix JWT expiry even when refresh works, unless `felix_jwt_expires_at` is set manually or the script is extended to update secrets.

## Error timeline and code fixes (resolved)

1. **`expected a 33-bytes-long public key (compressed). Got 65 bytes`**  
   - **Cause:** X-Stamp used uncompressed secp256k1 pubkey.  
   - **Fix:** Use compressed pubkey (33-byte SEC1) in the stamp.

2. **`invalid signature`** (after fixing pubkey format)  
   - **Cause:** Wrong signing scheme. Turnkey’s **EVM wallet** stamping matches `@turnkey/wallet-stamper`: **EIP-191** over the raw POST body, not raw SHA256+ECDSA with `SIGNATURE_SCHEME_TK_API_P256`.  
   - **Fix:** `build_x_stamp_header` uses `eth_account` (`encode_defunct` + `sign_message`), **DER**-encode `(r,s)` via `encode_dss_signature`, scheme **`SIGNATURE_SCHEME_TK_API_SECP256K1_EIP191`**. Dependency: **`eth-account`** in `requirements.txt`.

3. **Debug logging**  
   - `_turnkey_post` logs HTTP status and response body on failure; `lookup_sub_org` / `stamp_login` log step markers. Do not log JWTs or private keys.

## Current blocker (not fixed by this repo)

**Symptom**

```text
HTTP 403 — could not find public key in organization
organizationId=b052e625-0ea1-4e6a-b3a4-dd3d8e06f636
publicKey=031e1846519e8fe8c1dbfe026b4d66fe65dce434a90cb96d436237d95d0c7c0d99
```

**Meaning**

- Turnkey **accepts the stamp** (signature verification passes) and identifies the compressed pubkey above.
- That pubkey is **not registered** as an allowed API identity under Felix’s Turnkey org `b052e625-0ea1-4e6a-b3a4-dd3d8e06f636` for this API path (`list_suborgs`).

Trading in the Felix UI (e.g. SPY) confirms the wallet works in the product; it does **not** automatically register the same key for **server-side stamped Turnkey API** access.

**Sanity check (local)**

Derive compressed pubkey from `FELIX_WALLET_PRIVATE_KEY`; it must match the `publicKey=` value in Turnkey’s error (proves env + crypto align with what Turnkey sees).

**Next step**

- **Felix / Turnkey (ops):** Ask how this wallet’s pubkey gets **registered** for programmatic Turnkey requests under their org, or whether headless flow must use a different path (e.g. auth proxy only). Provide: wallet address, compressed pubkey, org id, exact error string.

## Files touched in this workstream

- `tracking/connectors/felix_auth.py` — EIP-191 stamping, compressed pubkey, logging, `RuntimeError` on HTTP errors with body snippet.
- `requirements.txt` — `eth-account>=0.13`.
- `tests/test_felix_auth.py` — expectations for EIP-191 stamp scheme and pubkey format.

## Quick verification commands

```bash
source .arbit_env
.venv/bin/python -m pytest tests/test_felix_auth.py -q
.venv/bin/python scripts/felix_jwt_refresh.py
```

---

*Last updated from debugging session: Turnkey “public key not in org” remains until Felix registers the identity or documents the correct headless onboarding path.*
