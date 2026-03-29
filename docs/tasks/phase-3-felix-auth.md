# Phase 3: Felix Equities Headless Auth

**Goal**: Automated Felix JWT management without browser
**Depends on**: Phase 1 (vault must be set up)

## Tasks

### 7.1 Turnkey Auth Implementation
- [ ] Load wallet private key (secp256k1) from vault
- [ ] Implement X-Stamp header generation (sign POST body with wallet key)
- [ ] Call `stamp_login` on Turnkey API to get initial JWT
- [ ] Parse JWT response, extract token + expiry

### 7.2 Session Management
- [ ] Generate P-256 session keypair for refresh
- [ ] Store session state encrypted in vault (`vault/felix_session.enc.json`)
- [ ] Implement JWT refresh using P-256 keypair
- [ ] Handle expired session: fall back to full wallet-key login

### 7.3 Felix Fill Ingestion
- [ ] Create Felix connector for fills (`/v1/trading/orders`)
- [ ] Map Felix fills to pm_fills schema
- [ ] Synthetic tid generation: hash(venue, account_id, inst_id, side, px, sz, ts)
- [ ] Felix equity pull from `/v1/portfolio/{address}`

### 7.4 Auto-Refresh Cron
- [ ] Create `scripts/felix_jwt_refresh.py`
- [ ] Run every 14 minutes via systemd timer
- [ ] Log: JWT refreshed, new expiry time
- [ ] Health endpoint shows Felix JWT status

### 7.5 Testing
- [ ] Full auth flow: wallet key → stamp_login → JWT → API call
- [ ] Refresh flow: existing session → new JWT
- [ ] Graceful degradation: system works without Felix data (warning only)

## Acceptance Criteria
- Felix JWT auto-refreshes without manual intervention
- Felix fills ingested into pm_fills
- System continues working if Felix auth fails (degraded mode)
