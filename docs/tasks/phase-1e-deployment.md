# Phase 1e: Deployment & Cron

**Goal**: Cloudflare Tunnel, systemd services, cron jobs
**Depends on**: Phase 1c + 1d (API + frontend ready)

## Tasks

### 5.1 Cloudflare Tunnel
- [ ] Install `cloudflared` on VPS
- [ ] Create tunnel: `cloudflared tunnel create harmonix-api`
- [ ] Configure: route to `localhost:8000` (uvicorn)
- [ ] DNS: create CNAME for `api.yourdomain.com` → tunnel
- [ ] Test: `curl https://api.yourdomain.com/api/health`

### 5.2 FastAPI Systemd Service
- [ ] Create `harmonix-api.service` systemd unit
- [ ] Auto-start on boot, restart on failure
- [ ] Environment: load vault at startup
- [ ] Bind to localhost:8000 (only accessible via tunnel)

### 5.3 Cron Jobs
- [ ] Hourly pipeline: `pipeline_hourly.py` at :05 every hour
- [ ] Felix JWT refresh: `felix_jwt_refresh.py` every 14 minutes
- [ ] Update existing crontab with new jobs
- [ ] Log rotation for new log files

### 5.4 End-to-End Verification
- [ ] Vercel frontend loads data via Cloudflare Tunnel
- [ ] Hourly cron fires, new fills appear in DB
- [ ] Metrics auto-update after cron run
- [ ] Health endpoint shows all systems green
- [ ] Manual cashflow from Vercel settings page persists to VPS DB

## Acceptance Criteria
- Frontend on Vercel connects to VPS backend via HTTPS tunnel
- All cron jobs fire on schedule and update data
- System survives VPS reboot (auto-start)
