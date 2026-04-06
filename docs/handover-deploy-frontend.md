# Handover: Complete Frontend Vercel Deployment

## Context
We're deploying the Harmonix monitoring dashboard (Next.js 14 frontend) to Vercel. The backend is already live at `https://api-trade-sandbox.harmonix.fi` (EC2 + Docker + Cloudflare Tunnel).

## What's Already Done
- Vercel CLI installed and logged in (`vercel whoami` → `baonlq94-8124`)
- First deploy succeeded — project `frontend` linked under `baonlq94-gmailcoms-projects`
- Env vars `API_BASE_URL` and `API_KEY` set for production on Vercel
- Production deployed at: `https://frontend-sable-pi-w4rp2wptry.vercel.app`

## What You Need To Do

### 1. Verify the production deployment works
```bash
curl -s https://frontend-sable-pi-w4rp2wptry.vercel.app | head -20
```
Open in browser and check if the dashboard loads with real data from the backend.

### 2. If the dashboard shows errors or empty data
The frontend fetches from `API_BASE_URL` server-side. Check:
```bash
# Verify env vars are set
cd frontend && vercel env ls

# Test backend directly
curl -s -H "X-API-Key: abcde" https://api-trade-sandbox.harmonix.fi/api/portfolio/overview | python3 -m json.tool
```

If env vars were added after the last deploy, redeploy:
```bash
cd frontend && vercel deploy --prod --yes
```

### 3. (Optional) Set up custom domain
If you want `dashboard.harmonix.fi` instead of the auto-generated Vercel URL:
```bash
cd frontend && vercel domains add dashboard.harmonix.fi
```
Then add the CNAME in Cloudflare DNS: `dashboard` → `cname.vercel-dns.com`

### 4. Set up Cloudflare Access (IP restriction for backend)
This restricts the backend API to only accept traffic from Vercel's edge servers:
1. Go to https://one.dash.cloudflare.com/
2. Access → Applications → Add Application → Self-hosted
3. Application domain: `api-trade-sandbox.harmonix.fi`
4. Add policy to allow Vercel IP ranges (see https://vercel.com/docs/security/deployment-protection/ip-allowlist)

### 5. Verify end-to-end
Open the Vercel URL in browser. You should see:
- Total Equity ~$34K (not $3K)
- All 4 positions with uPnL values
- Funding, Carry APR, Exit Spread columns populated
- Health bar showing recent data pulls

## Key Files
- Frontend source: `frontend/` directory
- Deployment guide: `docs/deployment-guide.md`
- Backend: EC2 `trading-sandbox` at `/home/ubuntu/hip3-agent`
- Docker: `docker-compose.yml`, `Dockerfile`, `docker/`
