# Phase 1d: Frontend

**Goal**: Next.js web dashboard on Vercel
**Depends on**: Phase 1c (API must be running)

## Tasks

### 4.1 Project Setup
- [ ] Initialize Next.js 14+ project with App Router
- [ ] Tailwind CSS configuration
- [ ] TypeScript interfaces matching API response shapes (`lib/types.ts`)
- [ ] API client wrapper (`lib/api.ts`) with server-side API key
- [ ] Environment variable: `API_BASE_URL` (server-side only, NOT NEXT_PUBLIC)

### 4.2 Dashboard Page (`/`)
- [ ] Equity card: total equity, 24h change (USD + %), cashflow-adjusted APR
- [ ] Wallet breakdown table: label, address (truncated), equity per wallet
- [ ] Funding summary: today, all-time, fees, net P&L
- [ ] Open positions table: base, amount, uPnL, funding earned, carry APR, exit spread, advisory
- [ ] System status: last pull times, Felix JWT status, DB size
- [ ] Color coding: green for positive P&L, red for negative

### 4.3 Position Detail Page (`/positions/[id]`)
- [ ] Header: position ID, base, strategy, status, opened date, amount
- [ ] Legs table: venue, inst_id, side, size, avg entry, current price, uPnL
- [ ] Sub-pair spreads: entry spread, exit spread, spread P&L (bps)
- [ ] Cashflow table: all funding + fee events
- [ ] Fills table: all trade fills with price, size, side, fee, timestamp

### 4.4 Closed Positions Page (`/closed`)
- [ ] Table: base, duration, amount, spread P&L, funding, fees, net P&L, net APR
- [ ] Sort by net APR or net P&L
- [ ] Color coding for profitable/unprofitable

### 4.5 Settings Page (`/settings`)
- [ ] Tracking start date config
- [ ] Manual deposit/withdraw form → POST /api/cashflows/manual
- [ ] System info display

### 4.6 Deploy
- [ ] Deploy to Vercel
- [ ] Set server-side env vars (API_BASE_URL, API_KEY)
- [ ] Verify: all pages load with real data

## Acceptance Criteria
- Dashboard shows correct equity, positions, funding data
- Position detail shows legs, spreads, fills
- Closed positions show P&L breakdown
- Manual deposit via settings form works end-to-end
- Mobile responsive (readable on phone)
