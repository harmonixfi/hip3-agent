# Deployment Guide: Harmonix Monitoring System

## Architecture

```
[Vercel CDN]                    [Cloudflare Tunnel]
Next.js Frontend                HTTPS termination
frontend-sable-pi-*.vercel.app  api-trade-sandbox.harmonix.fi
        |                              |
        +-------- HTTPS --------> [EC2: trading-sandbox]
                                  Docker: harmonix-api
                                  - FastAPI (port 8001)
                                  - Cron jobs (5min + hourly)
                                  - SQLite DB
```

## Backend (EC2 + Docker + Cloudflare Tunnel)

### Server Access
```bash
ssh trading-sandbox
# Project path: /home/ubuntu/hip3-agent
# Branch: feat/monitoring-system
```

### What's Running
- **Docker container** `harmonix-api`: FastAPI + cron jobs
- **cloudflared** systemd service: tunnels `api-trade-sandbox.harmonix.fi` → `localhost:8001`

### Docker Setup (already done)

Files in repo:
- `Dockerfile` — Python 3.11-slim, installs deps, copies code, runs entrypoint
- `docker-compose.yml` — Maps port 127.0.0.1:8001:8000, mounts DB/env/config/logs as volumes
- `docker/entrypoint.sh` — Sources `.arbit_env`, exports env for cron, starts cron + uvicorn
- `docker/crontab` — 4 cron jobs (positions, prices, market data, computation pipeline)

Volume mounts (NOT baked into image):
- `./tracking/db:/app/tracking/db` — SQLite database
- `./.arbit_env:/app/.arbit_env:ro` — Environment variables
- `./config:/app/config:ro` — Position + equity config
- `./logs:/app/logs` — Cron logs

### Deploy/Redeploy Backend

```bash
# SSH to server
ssh trading-sandbox
cd /home/ubuntu/hip3-agent

# Pull latest code
git pull origin feat/monitoring-system

# Rebuild and restart
docker compose build && docker compose up -d

# Check status
docker compose ps
docker compose logs --tail 50

# Check API
curl http://localhost:8001/
```

### Cloudflare Tunnel Setup (already done)

- **Tunnel ID**: `6d6086c9-b2f5-4112-9389-e2ed09072b1a`
- **Hostname**: `api-trade-sandbox.harmonix.fi`
- **Config**: `/etc/cloudflared/config.yml`
- **Credentials**: `/etc/cloudflared/6d6086c9-b2f5-4112-9389-e2ed09072b1a.json`
- **Service**: `cloudflared.service` (systemd, auto-starts on boot)

Config file (`/etc/cloudflared/config.yml`):
```yaml
tunnel: 6d6086c9-b2f5-4112-9389-e2ed09072b1a
credentials-file: /etc/cloudflared/6d6086c9-b2f5-4112-9389-e2ed09072b1a.json

ingress:
  - hostname: api-trade-sandbox.harmonix.fi
    service: http://localhost:8001
  - service: http_status:404
```

Manage tunnel:
```bash
sudo systemctl status cloudflared
sudo systemctl restart cloudflared
sudo journalctl -u cloudflared -f
```

### How Cloudflare Tunnel Was Set Up (for reference)

```bash
# 1. Install cloudflared
sudo curl -L --output /usr/local/bin/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
sudo chmod +x /usr/local/bin/cloudflared

# 2. Login (opens browser — select harmonix.fi domain)
cloudflared tunnel login

# 3. Create tunnel
cloudflared tunnel create harmonix-api

# 4. Write config (replace UUID)
sudo mkdir -p /etc/cloudflared
sudo cp ~/.cloudflared/config.yml /etc/cloudflared/
sudo cp ~/.cloudflared/<TUNNEL_UUID>.json /etc/cloudflared/

# 5. Create DNS route
cloudflared tunnel route dns harmonix-api api-trade-sandbox.harmonix.fi

# 6. Install as systemd service
sudo cloudflared service install
sudo systemctl start cloudflared
```

### Cron Jobs in Docker

| Schedule | Script | Purpose |
|----------|--------|---------|
| `*/5 * * * *` | `pull_positions_v3.py` | Position + account snapshots |
| `2-57/5 * * * *` | `pull_position_prices.py` | Bid/ask prices for position legs |
| `20 * * * *` | `pull_hyperliquid_v3.py` | Market data (all perps) |
| `30 * * * *` | `pipeline_hourly.py` | Entry prices, uPnL, spreads, portfolio |

Logs at `/home/ubuntu/hip3-agent/logs/`.

---

## Frontend (Vercel)

### Project Info
- **Vercel project**: `frontend` under `baonlq94-gmailcoms-projects`
- **Production URL**: `https://frontend-sable-pi-w4rp2wptry.vercel.app`
- **Source**: `frontend/` directory in repo

### Environment Variables (set on Vercel)
- `API_BASE_URL` = `https://api-trade-sandbox.harmonix.fi`
- `API_KEY` = `<HARMONIX_API_KEY value>` (server-side only, not NEXT_PUBLIC_)

### Deploy/Redeploy Frontend

```bash
cd frontend
vercel deploy --prod --yes
```

Or push to repo — if GitHub integration is connected, it auto-deploys.

### First-Time Setup (for reference)

```bash
# 1. Install Vercel CLI
npm i -g vercel

# 2. Login
vercel login

# 3. Deploy (links project on first run)
cd frontend
vercel deploy --yes

# 4. Set env vars
vercel env add API_BASE_URL production <<< "https://api-trade-sandbox.harmonix.fi"
vercel env add API_KEY production <<< "<your-api-key>"

# 5. Production deploy with env vars
vercel deploy --prod --yes
```

---

## Remaining Setup (not yet done)

### Cloudflare Access (IP restriction)
Restrict `api-trade-sandbox.harmonix.fi` to only accept requests from Vercel IPs:

1. Go to [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/)
2. Access → Applications → Add Application → Self-hosted
3. Application domain: `api-trade-sandbox.harmonix.fi`
4. Add policy: Allow → IP Ranges → add Vercel's IP ranges
5. Vercel IPs: https://vercel.com/docs/security/deployment-protection/ip-allowlist

### Custom Domain for Frontend
Optionally assign a custom domain (e.g., `dashboard.harmonix.fi`) via Vercel dashboard → Project → Domains.

---

## Troubleshooting

### Backend not responding
```bash
ssh trading-sandbox
docker compose ps                    # Container running?
docker compose logs --tail 100       # Check errors
curl http://localhost:8001/          # API responding locally?
sudo systemctl status cloudflared    # Tunnel running?
```

### Stale data on dashboard
```bash
ssh trading-sandbox
docker exec harmonix-api cat /app/logs/pipeline_hourly.log | tail -20
docker exec harmonix-api cat /app/logs/pull_positions.log | tail -20
```

### Rebuild from scratch
```bash
ssh trading-sandbox
cd /home/ubuntu/hip3-agent
docker compose down
docker compose build --no-cache
docker compose up -d
```
