# Server Operations Runbook

## Infrastructure

| Alias | Host | User | Key | Role |
|-------|------|------|-----|------|
| `trading-sandbox` | ec2-54-251-223-39.ap-southeast-1.compute.amazonaws.com | ubuntu | `~/.ssh/har_sandbox_trading` | Production VPS (API + DB) |

**Workspace path:** `/home/ubuntu/hip3-agent/`

**Key paths inside workspace:**
- DB: `tracking/db/arbit_v3.db`
- Env: `.arbit_env`
- Config: `config/positions.json`
- Logs: `logs/`

---

## Containers

```bash
ssh trading-sandbox "docker ps"
```

| Container | Port (host→container) | Role |
|-----------|----------------------|------|
| `harmonix-api` | `127.0.0.1:8001→8000` | FastAPI backend |
| `trading-dashboard` | `0.0.0.0:3000→3000` | (other project) |

**Volume mounts on `harmonix-api`:**
- `/home/ubuntu/hip3-agent/tracking/db` → `/app/tracking/db`
- `/home/ubuntu/hip3-agent/.arbit_env` → `/app/.arbit_env`
- `/home/ubuntu/hip3-agent/config` → `/app/config`
- `/home/ubuntu/hip3-agent/logs` → `/app/logs`

> Source code (`api/`, `scripts/`, `tracking/`) is **baked into the image** — not volume-mounted.
> Changes to host files under `api/` are NOT picked up automatically; see [Deploy code changes](#deploy-code-changes).

---

## API

**Base URL (local):** `http://127.0.0.1:8001`
**API Key:** `abcde` (set via `HARMONIX_API_KEY` in `.arbit_env`)

```bash
# Health check
ssh trading-sandbox "curl -s -H 'X-API-Key: abcde' http://127.0.0.1:8001/api/health"

# List open positions
ssh trading-sandbox "curl -s -H 'X-API-Key: abcde' http://127.0.0.1:8001/api/positions | python3 -m json.tool"
```

---

## Cashflow Ingest

The `pm_cashflows` table must be kept fresh for realized metrics (windowed funding/APR) to appear in the dashboard.

### Check freshness

```bash
ssh trading-sandbox 'docker exec harmonix-api python3 -c "
import sqlite3, time
con = sqlite3.connect(\"tracking/db/arbit_v3.db\")
now = int(time.time() * 1000)
row = con.execute(\"SELECT MAX(ts) FROM pm_cashflows WHERE cf_type=\\\"FUNDING\\\"\").fetchone()
last_ts = row[0] if row[0] else 0
print(f\"Last FUNDING: {(now-last_ts)/3600000:.1f}h ago\")
"'
```

If > 24h, the `1d` windowed column will show `—` in the dashboard.

### Run ingest (all Hyperliquid positions)

```bash
ssh trading-sandbox "docker exec harmonix-api python scripts/pm_cashflows.py ingest --venues hyperliquid --since-hours 504"
```

`--since-hours 504` = 21 days. Safe to re-run; events are deduped.

### Verify windowed data

```bash
ssh trading-sandbox 'docker exec harmonix-api python3 -c "
import sqlite3, time
con = sqlite3.connect(\"tracking/db/arbit_v3.db\")
now = int(time.time() * 1000)
for w, ms in [(\"1d\", 86400000), (\"7d\", 7*86400000), (\"14d\", 14*86400000)]:
    rows = con.execute(\"SELECT position_id, ROUND(SUM(amount),2) FROM pm_cashflows WHERE cf_type=\\\"FUNDING\\\" AND ts >= ? AND UPPER(currency) IN (\\\"USD\\\",\\\"USDC\\\",\\\"USDT\\\") GROUP BY position_id\", (now-ms,)).fetchall()
    print(f\"{w}:\", rows)
"'
```

### View full cashflow report

```bash
ssh trading-sandbox "docker exec harmonix-api python scripts/pm_cashflows.py report --json"
```

---

## Deploy Code Changes

Since `api/` is baked into the container image, patches must be copied in manually and the container restarted.

### Workflow

```bash
# 1. Edit the file on the host
ssh trading-sandbox "nano /home/ubuntu/hip3-agent/api/routers/positions.py"

# 2. Copy into the running container
ssh trading-sandbox "docker cp /home/ubuntu/hip3-agent/api/routers/positions.py harmonix-api:/app/api/routers/positions.py"
ssh trading-sandbox "docker cp /home/ubuntu/hip3-agent/api/models/schemas.py harmonix-api:/app/api/models/schemas.py"

# 3. Test imports before restart
ssh trading-sandbox "docker exec harmonix-api python3 -c 'from api.routers.positions import _build_position_summary; print(\"OK\")'"

# 4. Restart
ssh trading-sandbox "docker restart harmonix-api"

# 5. Verify (wait ~10s for health check)
sleep 10 && ssh trading-sandbox "docker ps --filter name=harmonix-api --format '{{.Status}}'"
```

> For permanent changes: rebuild the image (`docker compose build harmonix-api && docker compose up -d harmonix-api`) or update the source and redeploy.

---

## Realized APR / Funding $ (Dashboard Columns)

These two columns (`APR (realized)` and `Funding $ (realized)`) are populated from the `windowed` field in the API response.

**How it works:**
- API computes `windowed.funding_Nd` = SUM of FUNDING cashflows in last N days from `pm_cashflows`
- `windowed.apr_Nd` = `(funding_Nd / amount_usd) / N * 365 * 100`
- If `pm_cashflows` has no rows in the 1d window → columns show `—`

**Fix when columns are empty:**
1. Run cashflow ingest (see above)
2. Verify windowed data query returns rows for 1d window
3. Reload the Vercel dashboard (Next.js SSR — no client cache to clear)

**Debug windowed output from API:**
```bash
ssh trading-sandbox "curl -s -H 'X-API-Key: abcde' http://127.0.0.1:8001/api/positions | python3 -c \"
import sys, json
data = json.load(sys.stdin)
for p in data:
    w = p.get('windowed') or {}
    print(f\\\"{p['base']:10s}: f1d={w.get('funding_1d')} apr1d={w.get('apr_1d')}% f7d={w.get('funding_7d')} apr7d={w.get('apr_7d')}%\\\")
\""
```

---

## Common Checks

### DB size + last pull timestamps
```bash
ssh trading-sandbox "curl -s -H 'X-API-Key: abcde' http://127.0.0.1:8001/api/health | python3 -m json.tool"
```

### Container logs
```bash
ssh trading-sandbox "docker logs harmonix-api --tail 50"
```

### Run arbitrary Python in container
```bash
ssh trading-sandbox "docker exec harmonix-api python3 -c 'import sqlite3; con = sqlite3.connect(\"tracking/db/arbit_v3.db\"); print(con.execute(\"SELECT COUNT(*) FROM pm_cashflows\").fetchone())'"
```

### pm.py commands (position registry)
```bash
# Run inside container (has env loaded)
ssh trading-sandbox "docker exec harmonix-api python scripts/pm.py list"
ssh trading-sandbox "docker exec harmonix-api python scripts/pm.py sync-registry"
```
