# Phase 1e: Deployment & Cron — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy FastAPI backend behind Cloudflare Tunnel, set up systemd services for auto-start, configure hourly cron pipeline, and verify end-to-end Vercel→Tunnel→VPS connectivity.

**Architecture:** cloudflared tunnel on VPS proxies HTTPS to localhost:8000 (uvicorn). systemd manages both services. Cron runs hourly data pipeline.

**Tech Stack:** cloudflared, systemd, crontab, uvicorn

---

## Prerequisites

Before starting, confirm on the VPS:
- [ ] Project root at `/Users/harmonix/.openclaw/workspace-hip3-agent` (or update `$WORKSPACE` accordingly)
- [ ] `.arbit_env` present and populated in project root
- [ ] `.venv/bin/python` functional, all dependencies installed (`pip install -r requirements.txt`)
- [ ] `api/main.py` (FastAPI app) exists and starts cleanly with `uvicorn api.main:app`
- [ ] Cloudflare account exists with the target domain's DNS managed by Cloudflare
- [ ] `cloudflared` binary not yet installed (this plan installs it)
- [ ] VPS running Ubuntu 20.04+ (systemd present)

---

## Task 1: Install and Authenticate cloudflared

### 1.1 Install cloudflared binary

```bash
# Download and install cloudflared (Debian/Ubuntu)
curl -L --output cloudflared.deb \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# Verify
cloudflared --version
```

Expected output: `cloudflared version 2024.x.x`

### 1.2 Authenticate cloudflared with your Cloudflare account

```bash
cloudflared tunnel login
```

This opens a browser URL. Visit it, select the domain (e.g. `harmonix.yourdomain.com`), and authorize. A credentials file is written to `~/.cloudflared/cert.pem`.

- [ ] `~/.cloudflared/cert.pem` exists after auth

---

## Task 2: Create the Cloudflare Tunnel

### 2.1 Create the tunnel

```bash
cloudflared tunnel create harmonix-api
```

Note the tunnel UUID printed in output (format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`). It is also stored in:
`~/.cloudflared/<TUNNEL_UUID>.json`

- [ ] Tunnel UUID recorded: `__________________________`

### 2.2 Write the tunnel config file

Create `/etc/cloudflared/config.yml` (system-wide, used by systemd service):

```bash
sudo mkdir -p /etc/cloudflared
sudo tee /etc/cloudflared/config.yml > /dev/null << 'EOF'
tunnel: <TUNNEL_UUID>
credentials-file: /root/.cloudflared/<TUNNEL_UUID>.json

ingress:
  - hostname: api.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
EOF
```

Replace `<TUNNEL_UUID>` with the UUID from step 2.1. Replace `api.yourdomain.com` with the actual subdomain.

> **Note:** If running cloudflared as a non-root user, adjust `credentials-file` path to match the user's home directory (e.g., `/home/harmonix/.cloudflared/<TUNNEL_UUID>.json`).

- [ ] `/etc/cloudflared/config.yml` written with correct UUID and hostname

### 2.3 Create DNS CNAME record

```bash
cloudflared tunnel route dns harmonix-api api.yourdomain.com
```

This creates a CNAME in Cloudflare DNS: `api.yourdomain.com` → `<TUNNEL_UUID>.cfargotunnel.com`

Verify in Cloudflare dashboard: DNS tab → should see the CNAME record.

- [ ] CNAME visible in Cloudflare DNS dashboard

---

## Task 3: cloudflared systemd Service

### 3.1 Install cloudflared as a systemd service

cloudflared ships with a built-in install command that writes the unit file automatically:

```bash
sudo cloudflared service install
```

This writes `/etc/systemd/system/cloudflared.service` and enables it.

If the auto-install doesn't pick up `/etc/cloudflared/config.yml`, write the unit file manually:

```ini
# /etc/systemd/system/cloudflared.service
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/cloudflared tunnel --config /etc/cloudflared/config.yml run
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

### 3.2 Verify tunnel is up

```bash
sudo systemctl status cloudflared
```

Expected: `active (running)`

```bash
# Quick smoke test from VPS (tunnel itself, not yet testing FastAPI)
curl -I https://api.yourdomain.com/
```

Expected: HTTP response (even 502 is fine here — it means tunnel is up but FastAPI not running yet).

- [ ] `systemctl status cloudflared` shows `active (running)`
- [ ] curl to tunnel URL returns any HTTP response (not a connection error)

---

## Task 4: FastAPI systemd Service

### 4.1 Write the harmonix-api.service unit file

The service must:
- Source `.arbit_env` for environment variables (systemd does not source shell files natively — use `EnvironmentFile` or an `ExecStartPre` wrapper)
- Set `SOPS_AGE_KEY_FILE` for vault decryption
- Bind uvicorn to `127.0.0.1:8000` (localhost only — tunnel handles external access)
- Restart automatically on failure

```bash
sudo tee /etc/systemd/system/harmonix-api.service > /dev/null << 'EOF'
[Unit]
Description=Harmonix FastAPI Backend
After=network.target
Wants=network.target

[Service]
Type=simple
User=harmonix
WorkingDirectory=/Users/harmonix/.openclaw/workspace-hip3-agent
EnvironmentFile=/Users/harmonix/.openclaw/workspace-hip3-agent/.arbit_env
Environment=SOPS_AGE_KEY_FILE=/Users/harmonix/.openclaw/workspace-hip3-agent/.sops_age_key
ExecStart=/Users/harmonix/.openclaw/workspace-hip3-agent/.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=on-failure
RestartSec=10s
StandardOutput=append:/Users/harmonix/.openclaw/workspace-hip3-agent/logs/harmonix-api.log
StandardError=append:/Users/harmonix/.openclaw/workspace-hip3-agent/logs/harmonix-api.log

[Install]
WantedBy=multi-user.target
EOF
```

> **Important:** `EnvironmentFile` does not support `export KEY=VALUE` syntax — it requires bare `KEY=VALUE` lines. If `.arbit_env` uses `export`, strip that prefix with a wrapper script (see Task 4.2).

> **User:** Replace `harmonix` with the actual VPS user running the project. If running as root, replace `User=harmonix` with `User=root` and adjust paths accordingly.

- [ ] Unit file written at `/etc/systemd/system/harmonix-api.service`

### 4.2 (Conditional) Wrapper script if .arbit_env uses `export` syntax

If `.arbit_env` contains lines like `export DB_PATH=...`, systemd's `EnvironmentFile` will fail. Use a wrapper:

```bash
tee /Users/harmonix/.openclaw/workspace-hip3-agent/scripts/start_api.sh > /dev/null << 'EOF'
#!/bin/bash
set -a
source /Users/harmonix/.openclaw/workspace-hip3-agent/.arbit_env
set +a
exec /Users/harmonix/.openclaw/workspace-hip3-agent/.venv/bin/uvicorn api.main:app \
  --host 127.0.0.1 --port 8000 --workers 1
EOF
chmod +x /Users/harmonix/.openclaw/workspace-hip3-agent/scripts/start_api.sh
```

Then update `ExecStart` in the unit file:

```ini
ExecStart=/Users/harmonix/.openclaw/workspace-hip3-agent/scripts/start_api.sh
```

Remove the `EnvironmentFile=` line when using the wrapper.

- [ ] (if needed) `scripts/start_api.sh` written and `+x`

### 4.3 Enable and start the service

```bash
sudo systemctl daemon-reload
sudo systemctl enable harmonix-api
sudo systemctl start harmonix-api
```

### 4.4 Verify FastAPI is running

```bash
sudo systemctl status harmonix-api
# Expected: active (running)

curl http://127.0.0.1:8000/api/health
# Expected: {"status": "ok", ...}
```

- [ ] `systemctl status harmonix-api` shows `active (running)`
- [ ] `curl http://127.0.0.1:8000/api/health` returns 200 with JSON body

---

## Task 5: End-to-End Tunnel Verification

With both services running, test the full Cloudflare path:

```bash
# From any external machine (or VPS with curl):
curl https://api.yourdomain.com/api/health
```

Expected:
```json
{"status": "ok", "db": "connected", "last_pull": "..."}
```

- [ ] `curl https://api.yourdomain.com/api/health` returns 200 from external network

If this fails:
1. Check cloudflared logs: `sudo journalctl -u cloudflared -f`
2. Check FastAPI logs: `tail -f /Users/harmonix/.openclaw/workspace-hip3-agent/logs/harmonix-api.log`
3. Confirm tunnel UUID in config matches the `.json` credentials file

---

## Task 6: Cron Jobs

The existing `harmonix.cron` (project root) is the reference. **Append new jobs — do not overwrite existing ones.**

### 6.1 View current crontab

```bash
crontab -l
```

### 6.2 New cron entries to append

```cron
# --- Harmonix Phase 1e: New pipeline jobs ---
# Hourly fill ingestion + metric computation (:05, after position pull settles)
5 * * * *  cd /Users/harmonix/.openclaw/workspace-hip3-agent && source .arbit_env && .venv/bin/python scripts/pipeline_hourly.py >> logs/pipeline_hourly.log 2>&1

# Felix JWT refresh (every 14 minutes) — Phase 3 placeholder, uncomment when Felix is live
# */14 * * * * cd /Users/harmonix/.openclaw/workspace-hip3-agent && source .arbit_env && .venv/bin/python scripts/felix_jwt_refresh.py >> logs/felix_jwt.log 2>&1
```

> **Note:** The Felix JWT refresh line is commented out — it is a Phase 3 dependency. Uncomment it when `scripts/felix_jwt_refresh.py` is implemented and Felix headless auth is active.

### 6.3 Add the new entries

```bash
# Export current crontab, append new entries, re-import
crontab -l > /tmp/current_crontab.txt
cat >> /tmp/current_crontab.txt << 'EOF'

# --- Harmonix Phase 1e: New pipeline jobs ---
# Hourly fill ingestion + metric computation (:05, after position pull settles)
5 * * * *  cd /Users/harmonix/.openclaw/workspace-hip3-agent && source .arbit_env && .venv/bin/python scripts/pipeline_hourly.py >> logs/pipeline_hourly.log 2>&1

# Felix JWT refresh (every 14 minutes) — Phase 3 placeholder
# */14 * * * * cd /Users/harmonix/.openclaw/workspace-hip3-agent && source .arbit_env && .venv/bin/python scripts/felix_jwt_refresh.py >> logs/felix_jwt.log 2>&1
EOF
crontab /tmp/current_crontab.txt
rm /tmp/current_crontab.txt
```

### 6.4 Also update harmonix.cron in the repo

Append the same entries to `harmonix.cron` so the file stays in sync with the live crontab (it is the canonical reference):

```bash
cat >> /Users/harmonix/.openclaw/workspace-hip3-agent/harmonix.cron << 'EOF'

# --- Phase 1e additions ---
# Hourly fill ingestion + metric computation (:05, after position pull settles)
5 * * * *  cd /Users/harmonix/.openclaw/workspace-hip3-agent && source .arbit_env && .venv/bin/python scripts/pipeline_hourly.py >> logs/pipeline_hourly.log 2>&1

# Felix JWT refresh (every 14 minutes) — Phase 3 placeholder
# */14 * * * * cd /Users/harmonix/.openclaw/workspace-hip3-agent && source .arbit_env && .venv/bin/python scripts/felix_jwt_refresh.py >> logs/felix_jwt.log 2>&1
EOF
```

- [ ] `crontab -l` shows the new `pipeline_hourly.py` entry
- [ ] `harmonix.cron` in repo updated to match

### 6.5 Verify logs directory exists

```bash
mkdir -p /Users/harmonix/.openclaw/workspace-hip3-agent/logs
```

The cron job appends to `logs/pipeline_hourly.log` — the directory must exist.

- [ ] `logs/` directory exists in project root

---

## Task 7: Log Rotation

### 7.1 Create logrotate config for new logs

```bash
sudo tee /etc/logrotate.d/harmonix-pipeline > /dev/null << 'EOF'
/Users/harmonix/.openclaw/workspace-hip3-agent/logs/pipeline_hourly.log
/Users/harmonix/.openclaw/workspace-hip3-agent/logs/felix_jwt.log
/Users/harmonix/.openclaw/workspace-hip3-agent/logs/harmonix-api.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0644 harmonix harmonix
}
EOF
```

Replace `harmonix harmonix` with the actual `user group` on the VPS.

### 7.2 Test logrotate config

```bash
sudo logrotate --debug /etc/logrotate.d/harmonix-pipeline
```

Expected: no errors, shows which files would be rotated.

- [ ] logrotate config written
- [ ] `logrotate --debug` passes without errors

---

## Task 8: Vercel Environment Variable

Set `API_BASE_URL` and `API_KEY` as server-side environment variables in the Vercel project settings. These are used in Server Components only and must NOT have the `NEXT_PUBLIC_` prefix (they are never exposed to the browser).

### 8.1 Set via Vercel dashboard

1. Go to `https://vercel.com` → project settings → Environment Variables
2. Add: `API_BASE_URL` = `https://api.yourdomain.com`
3. Add: `API_KEY` = `<your API key>`
4. Scope: Production + Preview
5. Trigger a redeploy (Vercel applies env vars on next build)

### 8.2 Alternative: set via Vercel CLI

```bash
npx vercel env add API_BASE_URL production
# Enter value: https://api.yourdomain.com
npx vercel env add API_KEY production
# Enter value: <your API key>
npx vercel --prod
```

- [ ] `API_BASE_URL` set in Vercel for Production environment
- [ ] `API_KEY` set in Vercel for Production environment
- [ ] Vercel redeploy triggered

---

## Task 9: Full End-to-End Verification

Run all checks in sequence. Every item must pass before marking Phase 1e complete.

### 9.1 Service health checks

```bash
# Both systemd services running
sudo systemctl status harmonix-api cloudflared

# FastAPI health via localhost
curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool

# FastAPI health via Cloudflare Tunnel (external HTTPS path)
curl -s https://api.yourdomain.com/api/health | python3 -m json.tool
```

Expected: both return `{"status": "ok", ...}` with 200.

- [ ] `systemctl status` shows both services `active (running)`
- [ ] Localhost health check returns 200
- [ ] Tunnel health check returns 200

### 9.2 Reboot survival test

```bash
sudo reboot
# Wait ~60 seconds, then SSH back in
sudo systemctl status harmonix-api cloudflared
```

Both services must come back up automatically without manual intervention.

- [ ] Both services auto-start after reboot

### 9.3 Cron fire verification

Wait for the next `:05` minute of any hour, then:

```bash
# Check that the cron fired
tail -30 /Users/harmonix/.openclaw/workspace-hip3-agent/logs/pipeline_hourly.log
```

Expected: log entries from the current hour's run, no Python traceback as the final lines.

- [ ] `pipeline_hourly.log` has a fresh entry from the current hour
- [ ] No unhandled exception at the end of the log

### 9.4 Frontend connectivity check

Open the Vercel deployment URL in a browser. Navigate to the dashboard.

Check:
- Portfolio overview card loads (equity, APR)
- Positions table populates (even if 0 rows, the table renders without error)
- System status panel shows last data pull time (not "unknown")
- No console errors about CORS or mixed content (open browser DevTools → Console)

- [ ] Dashboard loads without errors
- [ ] Data populated from VPS (not stale/empty due to API error)
- [ ] No CORS errors in browser console

### 9.5 Manual cashflow persists to VPS

From the Vercel settings page (or via curl), POST a test cashflow entry:

```bash
TUNNEL_URL="https://api.yourdomain.com"
curl -s -X POST "$TUNNEL_URL/api/cashflows/manual" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"account_id": "0xYOUR_ADDRESS", "venue": "hyperliquid", "cf_type": "DEPOSIT", "amount": 1.00, "currency": "USDC", "description": "e2e smoke test"}'
```

Expected: 201 response.

Then verify it landed in the DB on VPS:

```bash
source .arbit_env && .venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('tracking/db/arbit_v3.db')
rows = conn.execute(\"SELECT * FROM pm_cashflows WHERE description='e2e smoke test'\").fetchall()
print(rows)
"
```

Expected: 1 row returned.

Delete the test row:

```bash
source .arbit_env && .venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('tracking/db/arbit_v3.db')
conn.execute(\"DELETE FROM pm_cashflows WHERE description='e2e smoke test'\")
conn.commit()
print('cleaned up')
"
```

- [ ] POST cashflow returns 201
- [ ] Row confirmed in DB on VPS
- [ ] Test row deleted

---

## Acceptance Criteria

All of the following must be true before Phase 1e is marked complete:

- [ ] `cloudflared` is installed and the `harmonix-api` tunnel exists in Cloudflare dashboard
- [ ] `systemctl status cloudflared` → `active (running)`, survives reboot
- [ ] `systemctl status harmonix-api` → `active (running)`, survives reboot
- [ ] `GET https://api.yourdomain.com/api/health` → 200 from public internet
- [ ] Cron entry for `pipeline_hourly.py` active in `crontab -l`
- [ ] `harmonix.cron` in repo reflects all live cron jobs
- [ ] `logs/pipeline_hourly.log` has a run from the current or previous hour
- [ ] Vercel frontend loads portfolio data from VPS without errors
- [ ] Manual cashflow POST persists to VPS DB
- [ ] logrotate config in place for new log files

---

## Rollback / Recovery Notes

**If cloudflared breaks:**
- Services behind the tunnel continue running; VPS is still directly accessible via SSH
- CLI scripts (`pm.py`, data pulls) are unaffected — they run locally on VPS
- Restart: `sudo systemctl restart cloudflared`
- Logs: `sudo journalctl -u cloudflared -n 50`

**If harmonix-api.service fails to start:**
- Check for import errors: `cd $WORKSPACE && source .arbit_env && .venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000` manually
- Common cause: missing env var or vault key not set in `EnvironmentFile`
- Logs: `tail -50 logs/harmonix-api.log`

**If cron job fails silently:**
- Check log: `tail -50 logs/pipeline_hourly.log`
- Test manually: `cd $WORKSPACE && source .arbit_env && .venv/bin/python scripts/pipeline_hourly.py`
- Common cause: PATH or env var issue in cron environment — ensure `cd $WORKSPACE && source .arbit_env` is at the start of each entry

**If Vercel shows stale data after deployment:**
- Confirm `API_BASE_URL` is set correctly and redeploy was triggered after env var change
- Test the tunnel URL directly with curl from a browser/terminal
