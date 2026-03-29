# Phase 1c: API Endpoints

**Goal**: FastAPI REST API serving all monitoring data
**Depends on**: Phase 1b (computed metrics must exist)

## Tasks

### 3.1 FastAPI Scaffold
- [ ] Create `api/` directory structure (main.py, config.py, deps.py, routers/, services/, models/)
- [ ] CORS configuration (allow Vercel domain)
- [ ] X-API-Key authentication middleware (key from vault)
- [ ] SQLite connection dependency (read-only for most endpoints)
- [ ] Uvicorn runner config

### 3.2 Portfolio Overview Endpoint
- [ ] `GET /api/portfolio/overview`
- [ ] Return: total equity, equity by account, daily change, APR, funding today/alltime, fees, net PnL, uPnL total
- [ ] Optional query param: `?tracking_start=YYYY-MM-DD`
- [ ] Pydantic response model

### 3.3 Positions Endpoints
- [ ] `GET /api/positions` — list all with computed metrics (uPnL, funding, spreads)
- [ ] `GET /api/positions/{id}` — detail with legs, sub-pair spreads, cashflows, fills summary
- [ ] `GET /api/positions/{id}/fills` — paginated fill history
- [ ] `GET /api/positions/closed` — closed position analysis with P&L breakdown
- [ ] Query params: `?status=OPEN|CLOSED|ALL`, `?limit`, `?offset`
- [ ] Pydantic response models for all

### 3.4 Manual Cashflow Endpoint
- [ ] `POST /api/cashflows/manual`
- [ ] Accept: account_id, venue, cf_type (DEPOSIT/WITHDRAW), amount, currency, ts, description
- [ ] Validation: amount positive, cf_type restricted, ts defaults to now
- [ ] Write to `pm_cashflows` with meta_json `{"source": "manual"}`
- [ ] Return 201 with cashflow_id

### 3.5 Health Endpoint
- [ ] `GET /api/health`
- [ ] Return: status, db_size, last fill/price/position pull timestamps, Felix JWT expiry, open position count, uptime

### 3.6 Testing
- [ ] curl all endpoints against live DB, verify response shapes
- [ ] Test auth: request without X-API-Key returns 401
- [ ] Test manual deposit: POST, then verify in portfolio overview
- [ ] Test pagination on fills endpoint

## Acceptance Criteria
- All endpoints return correct data matching PLAN.md response schemas
- Auth middleware blocks unauthorized requests
- Manual cashflow creates DB record and affects portfolio metrics
