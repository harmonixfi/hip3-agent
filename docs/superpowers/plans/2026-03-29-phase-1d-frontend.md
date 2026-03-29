# Phase 1d: Frontend Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Next.js monitoring dashboard showing portfolio overview, position details with spreads/uPnL, closed position analysis, and a manual cashflow form.

**Architecture:** Next.js 14 App Router with Server Components, Tailwind CSS. All data fetched server-side from FastAPI backend via typed API client. Deployed on Vercel.

**Tech Stack:** Next.js 14+, TypeScript, Tailwind CSS, Vercel

**References:**
- Frontend spec: `docs/PLAN.md` section 6
- API schemas: `docs/PLAN.md` section 4.2
- Task checklist: `docs/tasks/phase-1d-frontend.md`
- Decisions: `docs/DECISIONS.md` (ADR-003 Cloudflare Tunnel, ADR-006 Next.js+FastAPI)

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `frontend/package.json` | Project dependencies |
| Create | `frontend/tsconfig.json` | TypeScript config |
| Create | `frontend/tailwind.config.ts` | Tailwind configuration |
| Create | `frontend/postcss.config.mjs` | PostCSS config for Tailwind |
| Create | `frontend/next.config.ts` | Next.js configuration |
| Create | `frontend/.env.local.example` | Env var template (no secrets) |
| Create | `frontend/.gitignore` | Ignore node_modules, .next, .env.local |
| Create | `frontend/app/layout.tsx` | Root layout with nav sidebar |
| Create | `frontend/app/page.tsx` | Dashboard page |
| Create | `frontend/app/globals.css` | Tailwind imports + base styles |
| Create | `frontend/app/positions/[id]/page.tsx` | Position detail page |
| Create | `frontend/app/closed/page.tsx` | Closed positions page |
| Create | `frontend/app/settings/page.tsx` | Settings page |
| Create | `frontend/lib/types.ts` | TypeScript interfaces for API responses |
| Create | `frontend/lib/api.ts` | Server-side API client |
| Create | `frontend/lib/format.ts` | Number formatting utilities |
| Create | `frontend/components/EquityCard.tsx` | Equity summary card |
| Create | `frontend/components/WalletBreakdown.tsx` | Wallet equity table |
| Create | `frontend/components/FundingSummary.tsx` | Funding/fees/P&L summary |
| Create | `frontend/components/PositionsTable.tsx` | Open positions table |
| Create | `frontend/components/HealthStatus.tsx` | System status bar |
| Create | `frontend/components/LegDetail.tsx` | Legs table for position detail |
| Create | `frontend/components/SpreadDisplay.tsx` | Sub-pair spread display |
| Create | `frontend/components/CashflowTable.tsx` | Cashflow events table |
| Create | `frontend/components/FillsTable.tsx` | Trade fills table |
| Create | `frontend/components/ManualCashflowForm.tsx` | Deposit/withdraw form (client component) |
| Create | `frontend/components/SortableTable.tsx` | Reusable sortable table (client component) |
| Create | `frontend/components/NavSidebar.tsx` | Navigation sidebar |

---

## Task 1: Project Scaffolding

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/tailwind.config.ts`, `frontend/postcss.config.mjs`, `frontend/next.config.ts`, `frontend/.env.local.example`, `frontend/.gitignore`, `frontend/app/globals.css`

- [ ] **Step 1: Initialize the Next.js project**

Run from the repo root:

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir=false --import-alias="@/*" --use-npm --no-turbopack
```

**Expected output:** A `frontend/` directory with the standard Next.js 14 scaffold.

- [ ] **Step 2: Verify the scaffold and clean boilerplate**

Remove the default page content and styles. We will replace them in later tasks.

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend
npm run build
```

**Expected output:** Build succeeds with no errors.

- [ ] **Step 3: Create `.env.local.example`**

Create `frontend/.env.local.example`:

```env
# Server-side only — do NOT prefix with NEXT_PUBLIC_
API_BASE_URL=https://your-backend.example.com
API_KEY=your-api-key-here
```

- [ ] **Step 4: Update `.gitignore`**

Ensure `frontend/.gitignore` contains:

```gitignore
# dependencies
node_modules/
.pnp
.pnp.js

# next.js
.next/
out/

# env files
.env.local
.env.development.local
.env.test.local
.env.production.local

# misc
*.tsbuildinfo
next-env.d.ts
```

- [ ] **Step 5: Set up `globals.css`**

Replace `frontend/app/globals.css` with:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  body {
    @apply bg-gray-950 text-gray-100 antialiased;
  }
}

@layer components {
  .pnl-positive {
    @apply text-green-400;
  }
  .pnl-negative {
    @apply text-red-400;
  }
  .pnl-zero {
    @apply text-gray-400;
  }
  .card {
    @apply bg-gray-900 border border-gray-800 rounded-lg p-4;
  }
  .data-table {
    @apply w-full text-sm;
  }
  .data-table th {
    @apply text-left text-gray-400 font-medium py-2 px-3 border-b border-gray-800;
  }
  .data-table td {
    @apply py-2 px-3 border-b border-gray-800/50 tabular-nums;
  }
}
```

- [ ] **Step 6: Update `tailwind.config.ts`**

Ensure `frontend/tailwind.config.ts` is:

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 7: Update `next.config.ts`**

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // All API calls are server-side — no rewrites needed
  // Disable image optimization for simple deployment
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
```

- [ ] **Step 8: Verify build**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend
npm run build
```

**Expected output:** Build succeeds. No TypeScript errors.

---

## Task 2: TypeScript Types

**Files:**
- Create: `frontend/lib/types.ts`

- [ ] **Step 1: Create TypeScript interfaces matching all API response shapes**

Create `frontend/lib/types.ts`:

```typescript
// ============================================================
// Portfolio Overview — GET /api/portfolio/overview
// ============================================================

export interface AccountEquity {
  address: string;
  equity_usd: number;
  venue: string;
}

export interface PortfolioOverview {
  total_equity_usd: number;
  equity_by_account: Record<string, AccountEquity>;
  daily_change_usd: number;
  daily_change_pct: number;
  cashflow_adjusted_apr: number;
  funding_today_usd: number;
  funding_alltime_usd: number;
  fees_alltime_usd: number;
  net_pnl_alltime_usd: number;
  tracking_start_date: string;
  open_positions_count: number;
  total_unrealized_pnl: number;
  as_of: string;
}

// ============================================================
// Positions — GET /api/positions, GET /api/positions/{id}
// ============================================================

export interface SubPair {
  spot_leg_id: string;
  perp_leg_id: string;
  entry_spread_bps: number;
  exit_spread_bps: number;
  spread_pnl_bps: number;
}

export interface Leg {
  leg_id: string;
  venue: string;
  inst_id: string;
  side: "LONG" | "SHORT";
  size: number;
  avg_entry_price: number | null;
  current_price: number | null;
  unrealized_pnl: number | null;
  account_id: string | null;
}

export interface Position {
  position_id: string;
  base: string;
  strategy: "SPOT_PERP" | "PERP_PERP";
  status: "OPEN" | "PAUSED" | "EXITING" | "CLOSED";
  amount_usd: number;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
  funding_earned: number;
  fees_paid: number;
  net_carry: number;
  carry_apr: number | null;
  sub_pairs: SubPair[];
  legs: Leg[];
  opened_at: string;
}

// ============================================================
// Position Detail — GET /api/positions/{id}
// ============================================================

export interface FillSummary {
  leg_id: string;
  fill_count: number;
  first_fill: string | null;
  last_fill: string | null;
}

export interface Cashflow {
  cashflow_id: number;
  cf_type: string;
  amount: number;
  currency: string;
  ts: string;  // ISO 8601 string from API
  description: string | null;
  position_id: string | null;
}

export interface PositionDetail extends Position {
  fills_summary: FillSummary[];
  cashflows: Cashflow[];
  daily_funding_series: { date: string; amount: number }[];
}

// ============================================================
// Fills — GET /api/positions/{id}/fills
// ============================================================

export interface Fill {
  fill_id: number;
  leg_id: string;
  inst_id: string;
  side: "BUY" | "SELL";
  px: number;
  sz: number;
  fee: number | null;
  ts: number;
  dir: string | null;
  tid: string | null;
}

export interface FillsResponse {
  position_id: string;
  fills: Fill[];
  total: number;
  limit: number;
  offset: number;
}

// ============================================================
// Closed Positions — GET /api/positions/closed
// ============================================================

export interface ClosedPosition {
  position_id: string;
  base: string;
  status: "CLOSED";
  opened_at: string;
  closed_at: string;
  duration_days: number;
  amount_usd: number;
  realized_spread_pnl: number;
  total_funding_earned: number;
  total_fees_paid: number;
  net_pnl: number;
  net_apr: number;
  entry_spread_bps: number | null;
  exit_spread_bps: number | null;
}

// ============================================================
// Health — GET /api/health
// ============================================================

export interface HealthStatus {
  status: string;
  db_size_mb: number;
  last_fill_ingestion: string | null;
  last_price_pull: string | null;
  last_position_pull: string | null;
  felix_jwt_expires_at: string | null;
  open_positions: number;
  uptime_seconds: number;
}

// ============================================================
// Manual Cashflow — POST /api/cashflows/manual
// ============================================================

export interface ManualCashflowRequest {
  account_id: string;
  venue: string;
  cf_type: "DEPOSIT" | "WITHDRAW";
  amount: number;
  currency: string;
  ts?: number;
  description?: string;
}

export interface ManualCashflowResponse {
  cashflow_id: number;
}
```

- [ ] **Step 2: Verify types compile**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend
npx tsc --noEmit lib/types.ts
```

**Expected output:** No errors.

---

## Task 3: API Client & Formatting Utilities

**Files:**
- Create: `frontend/lib/api.ts`
- Create: `frontend/lib/format.ts`

- [ ] **Step 1: Create the server-side API client**

Create `frontend/lib/api.ts`:

```typescript
import type {
  PortfolioOverview,
  Position,
  PositionDetail,
  FillsResponse,
  ClosedPosition,
  HealthStatus,
  ManualCashflowRequest,
  ManualCashflowResponse,
} from "./types";

const API_BASE_URL = process.env.API_BASE_URL;
const API_KEY = process.env.API_KEY;

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  if (!API_BASE_URL) {
    throw new Error("API_BASE_URL environment variable is not set");
  }

  const url = `${API_BASE_URL}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (API_KEY) {
    headers["X-API-Key"] = API_KEY;
  }

  const res = await fetch(url, {
    ...options,
    headers: {
      ...headers,
      ...options?.headers,
    },
    // Revalidate every 60 seconds (ISR-style caching for server components)
    next: { revalidate: 60 },
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, `API ${res.status}: ${body}`);
  }

  return res.json() as Promise<T>;
}

// ---- Portfolio ----

export async function getPortfolioOverview(): Promise<PortfolioOverview> {
  return apiFetch<PortfolioOverview>("/api/portfolio/overview");
}

// ---- Positions ----

export async function getOpenPositions(): Promise<Position[]> {
  return apiFetch<Position[]>("/api/positions?status=OPEN");
}

export async function getPositionDetail(
  positionId: string,
): Promise<PositionDetail> {
  return apiFetch<PositionDetail>(`/api/positions/${positionId}`);
}

export async function getPositionFills(
  positionId: string,
  limit = 100,
  offset = 0,
): Promise<FillsResponse> {
  return apiFetch<FillsResponse>(
    `/api/positions/${positionId}/fills?limit=${limit}&offset=${offset}`,
  );
}

// ---- Closed Positions ----

export async function getClosedPositions(): Promise<ClosedPosition[]> {
  return apiFetch<ClosedPosition[]>("/api/positions/closed");
}

// ---- Health ----

export async function getHealth(): Promise<HealthStatus> {
  return apiFetch<HealthStatus>("/api/health");
}

// ---- Cashflows ----

export async function postManualCashflow(
  data: ManualCashflowRequest,
): Promise<ManualCashflowResponse> {
  return apiFetch<ManualCashflowResponse>("/api/cashflows/manual", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
```

- [ ] **Step 2: Create formatting utilities**

Create `frontend/lib/format.ts`:

```typescript
/**
 * Format a number as USD: $1,234.56
 * Negative values shown as -$1,234.56
 */
export function formatUSD(value: number | null | undefined, decimals = 2): string {
  if (value == null) return "—";
  const abs = Math.abs(value);
  const formatted = abs.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return value < 0 ? `-$${formatted}` : `$${formatted}`;
}

/**
 * Format a percentage: +1.23% or -0.45%
 */
export function formatPct(value: number | null | undefined, decimals = 2): string {
  if (value == null) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
}

/**
 * Format basis points: +15 bps or -3 bps
 */
export function formatBps(value: number | null | undefined): string {
  if (value == null) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${Math.round(value)} bps`;
}

/**
 * Format a number with commas: 1,234.56
 */
export function formatNumber(
  value: number | null | undefined,
  decimals = 2,
): string {
  if (value == null) return "—";
  return value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/**
 * Format a price — auto-selects decimal places based on magnitude.
 * <1: 4 decimals, <100: 3 decimals, else: 2 decimals.
 */
export function formatPrice(value: number | null | undefined): string {
  if (value == null) return "—";
  const abs = Math.abs(value);
  let decimals = 2;
  if (abs < 1) decimals = 4;
  else if (abs < 100) decimals = 3;
  return `$${formatNumber(value, decimals)}`;
}

/**
 * Format epoch ms to a readable date string: 2026-03-29 10:00
 */
export function formatDate(epochMs: number | string | null | undefined): string {
  if (epochMs == null) return "—";
  const d = typeof epochMs === "string" ? new Date(epochMs) : new Date(epochMs);
  if (isNaN(d.getTime())) return "—";
  return d.toISOString().replace("T", " ").slice(0, 16);
}

/**
 * Format a relative time: "2h ago", "3d ago"
 */
export function formatRelative(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return "—";
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/**
 * Truncate an address: 0xabc...def
 */
export function truncateAddress(address: string, chars = 4): string {
  if (address.length <= chars * 2 + 3) return address;
  return `${address.slice(0, chars + 2)}...${address.slice(-chars)}`;
}

/**
 * Return the CSS class for a P&L value.
 */
export function pnlColor(value: number | null | undefined): string {
  if (value == null || value === 0) return "pnl-zero";
  return value > 0 ? "pnl-positive" : "pnl-negative";
}
```

- [ ] **Step 3: Verify build**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend
npm run build
```

**Expected output:** Build succeeds. No TypeScript errors.

---

## Task 4: Navigation Sidebar & Root Layout

**Files:**
- Create: `frontend/components/NavSidebar.tsx`
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Create the navigation sidebar**

Create `frontend/components/NavSidebar.tsx`:

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "Dashboard", icon: "chart" },
  { href: "/closed", label: "Closed Positions", icon: "archive" },
  { href: "/settings", label: "Settings", icon: "gear" },
];

function NavIcon({ icon }: { icon: string }) {
  switch (icon) {
    case "chart":
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      );
    case "archive":
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
        </svg>
      );
    case "gear":
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      );
    default:
      return null;
  }
}

export default function NavSidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-full w-56 bg-gray-900 border-r border-gray-800 flex flex-col z-50">
      {/* Logo / Brand */}
      <div className="p-4 border-b border-gray-800">
        <h1 className="text-lg font-bold text-white tracking-tight">
          OpenClaw
        </h1>
        <p className="text-xs text-gray-500">Delta-Neutral Monitor</p>
      </div>

      {/* Nav links */}
      <nav className="flex-1 p-3 space-y-1">
        {navItems.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                isActive
                  ? "bg-gray-800 text-white"
                  : "text-gray-400 hover:text-white hover:bg-gray-800/50"
              }`}
            >
              <NavIcon icon={item.icon} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-gray-800">
        <p className="text-xs text-gray-600">v1.0 — Phase 1d</p>
      </div>
    </aside>
  );
}
```

- [ ] **Step 2: Create the root layout**

Replace `frontend/app/layout.tsx` with:

```tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import NavSidebar from "@/components/NavSidebar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "OpenClaw Dashboard",
  description: "Delta-neutral funding arbitrage monitoring",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <NavSidebar />
        <main className="ml-56 min-h-screen p-6">{children}</main>
      </body>
    </html>
  );
}
```

- [ ] **Step 3: Verify build**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend
npm run build
```

**Expected output:** Build succeeds. Layout renders with sidebar.

---

## Task 5: Dashboard Components

**Files:**
- Create: `frontend/components/EquityCard.tsx`
- Create: `frontend/components/WalletBreakdown.tsx`
- Create: `frontend/components/FundingSummary.tsx`
- Create: `frontend/components/PositionsTable.tsx`
- Create: `frontend/components/HealthStatus.tsx`

- [ ] **Step 1: Create EquityCard**

Create `frontend/components/EquityCard.tsx`:

```tsx
import { formatUSD, formatPct, pnlColor } from "@/lib/format";
import type { PortfolioOverview } from "@/lib/types";

interface Props {
  data: PortfolioOverview;
}

export default function EquityCard({ data }: Props) {
  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">
        Total Equity
      </div>
      <div className="text-3xl font-bold text-white tabular-nums">
        {formatUSD(data.total_equity_usd)}
      </div>
      <div className="flex items-center gap-3 mt-2">
        <span className={`text-sm font-medium ${pnlColor(data.daily_change_usd)}`}>
          {formatUSD(data.daily_change_usd)} ({formatPct(data.daily_change_pct)})
        </span>
        <span className="text-xs text-gray-500">24h</span>
      </div>
      <div className="flex items-center gap-3 mt-1">
        <span className={`text-sm ${pnlColor(data.cashflow_adjusted_apr)}`}>
          {formatPct(data.cashflow_adjusted_apr, 1)} APR
        </span>
        <span className="text-xs text-gray-500">cashflow-adjusted</span>
      </div>
      <div className="mt-3 flex items-center gap-2">
        <span className="text-xs text-gray-500">
          {data.open_positions_count} open positions
        </span>
        <span className="text-xs text-gray-600">|</span>
        <span className={`text-xs ${pnlColor(data.total_unrealized_pnl)}`}>
          uPnL {formatUSD(data.total_unrealized_pnl)}
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create WalletBreakdown**

Create `frontend/components/WalletBreakdown.tsx`:

```tsx
import { formatUSD, truncateAddress } from "@/lib/format";
import type { PortfolioOverview } from "@/lib/types";

interface Props {
  data: PortfolioOverview;
}

export default function WalletBreakdown({ data }: Props) {
  const accounts = Object.entries(data.equity_by_account);

  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
        Wallet Breakdown
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Label</th>
            <th>Address</th>
            <th>Venue</th>
            <th className="text-right">Equity</th>
          </tr>
        </thead>
        <tbody>
          {accounts.map(([label, acct]) => (
            <tr key={label}>
              <td className="font-medium text-white">{label}</td>
              <td className="font-mono text-gray-400 text-xs">
                {truncateAddress(acct.address)}
              </td>
              <td className="text-gray-400">{acct.venue}</td>
              <td className="text-right text-white tabular-nums">
                {formatUSD(acct.equity_usd)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 3: Create FundingSummary**

Create `frontend/components/FundingSummary.tsx`:

```tsx
import { formatUSD, pnlColor } from "@/lib/format";
import type { PortfolioOverview } from "@/lib/types";

interface Props {
  data: PortfolioOverview;
}

export default function FundingSummary({ data }: Props) {
  const items = [
    { label: "Funding Today", value: data.funding_today_usd },
    { label: "Funding All-Time", value: data.funding_alltime_usd },
    { label: "Fees All-Time", value: data.fees_alltime_usd },
    { label: "Net P&L", value: data.net_pnl_alltime_usd },
  ];

  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
        Funding Summary
      </div>
      <div className="grid grid-cols-2 gap-4">
        {items.map((item) => (
          <div key={item.label}>
            <div className="text-xs text-gray-500">{item.label}</div>
            <div className={`text-lg font-semibold tabular-nums ${pnlColor(item.value)}`}>
              {formatUSD(item.value)}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 text-xs text-gray-600">
        Since {data.tracking_start_date}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create PositionsTable**

Create `frontend/components/PositionsTable.tsx`:

```tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { formatUSD, formatPct, formatBps, pnlColor } from "@/lib/format";
import type { Position } from "@/lib/types";

interface Props {
  positions: Position[];
}

type SortKey =
  | "base"
  | "amount_usd"
  | "unrealized_pnl"
  | "funding_earned"
  | "carry_apr"
  | "exit_spread";

export default function PositionsTable({ positions }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("base");
  const [sortAsc, setSortAsc] = useState(true);

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(key === "base"); // alpha ascending, numeric descending
    }
  }

  function getSortValue(p: Position, key: SortKey): number | string {
    switch (key) {
      case "base":
        return p.base;
      case "amount_usd":
        return p.amount_usd;
      case "unrealized_pnl":
        return p.unrealized_pnl ?? 0;
      case "funding_earned":
        return p.funding_earned;
      case "carry_apr":
        return p.carry_apr ?? 0;
      case "exit_spread":
        // Weighted average exit spread across sub-pairs
        return p.sub_pairs.length > 0
          ? p.sub_pairs.reduce((s, sp) => s + sp.exit_spread_bps, 0) /
              p.sub_pairs.length
          : 0;
    }
  }

  const sorted = [...positions].sort((a, b) => {
    const va = getSortValue(a, sortKey);
    const vb = getSortValue(b, sortKey);
    const cmp = typeof va === "string" ? va.localeCompare(vb as string) : (va as number) - (vb as number);
    return sortAsc ? cmp : -cmp;
  });

  function SortHeader({ label, sortId }: { label: string; sortId: SortKey }) {
    const isActive = sortKey === sortId;
    return (
      <th
        onClick={() => handleSort(sortId)}
        className="cursor-pointer select-none hover:text-gray-200 transition-colors"
      >
        {label}
        {isActive && (
          <span className="ml-1 text-gray-500">
            {sortAsc ? "\u25B2" : "\u25BC"}
          </span>
        )}
      </th>
    );
  }

  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
        Open Positions
      </div>
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <SortHeader label="Base" sortId="base" />
              <th>Status</th>
              <SortHeader label="Amount" sortId="amount_usd" />
              <SortHeader label="uPnL" sortId="unrealized_pnl" />
              <SortHeader label="Funding" sortId="funding_earned" />
              <SortHeader label="Carry APR" sortId="carry_apr" />
              <SortHeader label="Exit Spread" sortId="exit_spread" />
              <th>Spread P&L</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((p) => {
              const avgExitSpread =
                p.sub_pairs.length > 0
                  ? p.sub_pairs.reduce((s, sp) => s + sp.exit_spread_bps, 0) /
                    p.sub_pairs.length
                  : null;
              const avgSpreadPnl =
                p.sub_pairs.length > 0
                  ? p.sub_pairs.reduce((s, sp) => s + sp.spread_pnl_bps, 0) /
                    p.sub_pairs.length
                  : null;

              return (
                <tr key={p.position_id} className="hover:bg-gray-800/50 transition-colors">
                  <td>
                    <Link
                      href={`/positions/${p.position_id}`}
                      className="text-blue-400 hover:text-blue-300 font-medium"
                    >
                      {p.base}
                    </Link>
                  </td>
                  <td>
                    <span
                      className={`text-xs px-1.5 py-0.5 rounded ${
                        p.status === "OPEN"
                          ? "bg-green-900/30 text-green-400"
                          : p.status === "PAUSED"
                            ? "bg-yellow-900/30 text-yellow-400"
                            : p.status === "EXITING"
                              ? "bg-orange-900/30 text-orange-400"
                              : "bg-gray-800 text-gray-400"
                      }`}
                    >
                      {p.status}
                    </span>
                  </td>
                  <td className="text-right tabular-nums">
                    {formatUSD(p.amount_usd)}
                  </td>
                  <td className={`text-right tabular-nums ${pnlColor(p.unrealized_pnl)}`}>
                    {formatUSD(p.unrealized_pnl)}
                  </td>
                  <td className={`text-right tabular-nums ${pnlColor(p.funding_earned)}`}>
                    {formatUSD(p.funding_earned)}
                  </td>
                  <td className={`text-right tabular-nums ${pnlColor(p.carry_apr)}`}>
                    {p.carry_apr != null ? formatPct(p.carry_apr, 1) : "—"}
                  </td>
                  <td className="text-right tabular-nums">
                    {formatBps(avgExitSpread)}
                  </td>
                  <td className={`text-right tabular-nums ${pnlColor(avgSpreadPnl)}`}>
                    {formatBps(avgSpreadPnl)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Create HealthStatus**

Create `frontend/components/HealthStatus.tsx`:

```tsx
import { formatRelative } from "@/lib/format";
import type { HealthStatus as HealthStatusType } from "@/lib/types";

interface Props {
  data: HealthStatusType;
}

export default function HealthStatus({ data }: Props) {
  const isHealthy = data.status === "ok";

  const items = [
    { label: "Fills", value: formatRelative(data.last_fill_ingestion) },
    { label: "Prices", value: formatRelative(data.last_price_pull) },
    { label: "Positions", value: formatRelative(data.last_position_pull) },
    { label: "Felix JWT", value: formatRelative(data.felix_jwt_expires_at) },
    { label: "DB", value: `${data.db_size_mb.toFixed(1)} MB` },
  ];

  return (
    <div className="flex items-center gap-4 px-4 py-2 bg-gray-900 border border-gray-800 rounded-lg text-xs">
      <div className="flex items-center gap-1.5">
        <div
          className={`w-2 h-2 rounded-full ${
            isHealthy ? "bg-green-400" : "bg-red-400"
          }`}
        />
        <span className="text-gray-400 font-medium uppercase">System</span>
      </div>
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1">
          <span className="text-gray-500">{item.label}:</span>
          <span className="text-gray-300">{item.value}</span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 6: Verify build**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend
npm run build
```

**Expected output:** Build succeeds. No TypeScript errors.

---

## Task 6: Dashboard Page

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Create the dashboard page**

Replace `frontend/app/page.tsx` with:

```tsx
import { getPortfolioOverview, getOpenPositions, getHealth } from "@/lib/api";
import EquityCard from "@/components/EquityCard";
import WalletBreakdown from "@/components/WalletBreakdown";
import FundingSummary from "@/components/FundingSummary";
import PositionsTable from "@/components/PositionsTable";
import HealthStatus from "@/components/HealthStatus";

export const revalidate = 60; // ISR: revalidate every 60 seconds

export default async function DashboardPage() {
  let portfolioData;
  let positions;
  let health;
  let error: string | null = null;

  try {
    [portfolioData, positions, health] = await Promise.all([
      getPortfolioOverview(),
      getOpenPositions(),
      getHealth(),
    ]);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to fetch data";
  }

  if (error || !portfolioData || !positions || !health) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <div className="card border-red-900">
          <p className="text-red-400">Failed to load dashboard data</p>
          <p className="text-sm text-gray-500 mt-1">{error}</p>
          <p className="text-xs text-gray-600 mt-2">
            Check that the backend is running and API_BASE_URL is configured.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <span className="text-xs text-gray-500">
          Last updated: {new Date(portfolioData.as_of).toLocaleString()}
        </span>
      </div>

      {/* System status bar */}
      <HealthStatus data={health} />

      {/* Top row: Equity + Wallets + Funding */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <EquityCard data={portfolioData} />
        <WalletBreakdown data={portfolioData} />
        <FundingSummary data={portfolioData} />
      </div>

      {/* Open Positions */}
      <PositionsTable positions={positions} />
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend
npm run build
```

**Expected output:** Build succeeds. Dashboard page renders.

---

## Task 7: Position Detail Components

**Files:**
- Create: `frontend/components/LegDetail.tsx`
- Create: `frontend/components/SpreadDisplay.tsx`
- Create: `frontend/components/CashflowTable.tsx`
- Create: `frontend/components/FillsTable.tsx`

- [ ] **Step 1: Create LegDetail component**

Create `frontend/components/LegDetail.tsx`:

```tsx
import { formatUSD, formatPrice, formatNumber, pnlColor } from "@/lib/format";
import type { Leg } from "@/lib/types";

interface Props {
  legs: Leg[];
}

export default function LegDetail({ legs }: Props) {
  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
        Legs
      </div>
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Venue</th>
              <th>Instrument</th>
              <th>Side</th>
              <th className="text-right">Size</th>
              <th className="text-right">Avg Entry</th>
              <th className="text-right">Current</th>
              <th className="text-right">uPnL</th>
            </tr>
          </thead>
          <tbody>
            {legs.map((leg) => (
              <tr key={leg.leg_id}>
                <td className="text-gray-400">{leg.venue}</td>
                <td className="font-mono text-white">{leg.inst_id}</td>
                <td>
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded ${
                      leg.side === "LONG"
                        ? "bg-green-900/30 text-green-400"
                        : "bg-red-900/30 text-red-400"
                    }`}
                  >
                    {leg.side}
                  </span>
                </td>
                <td className="text-right tabular-nums">
                  {formatNumber(leg.size, 4)}
                </td>
                <td className="text-right tabular-nums">
                  {formatPrice(leg.avg_entry_price)}
                </td>
                <td className="text-right tabular-nums">
                  {formatPrice(leg.current_price)}
                </td>
                <td className={`text-right tabular-nums ${pnlColor(leg.unrealized_pnl)}`}>
                  {formatUSD(leg.unrealized_pnl)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create SpreadDisplay component**

Create `frontend/components/SpreadDisplay.tsx`:

```tsx
import { formatBps, pnlColor } from "@/lib/format";
import type { SubPair, Leg } from "@/lib/types";

interface Props {
  subPairs: SubPair[];
  legs: Leg[];
}

export default function SpreadDisplay({ subPairs, legs }: Props) {
  if (subPairs.length === 0) {
    return null;
  }

  function getLegLabel(legId: string): string {
    const leg = legs.find((l) => l.leg_id === legId);
    return leg ? `${leg.venue} ${leg.inst_id}` : legId;
  }

  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
        Sub-Pair Spreads
      </div>
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Spot Leg</th>
              <th>Perp Leg</th>
              <th className="text-right">Entry Spread</th>
              <th className="text-right">Exit Spread</th>
              <th className="text-right">Spread P&L</th>
              <th className="text-right">Direction</th>
            </tr>
          </thead>
          <tbody>
            {subPairs.map((sp, i) => {
              const favorable = sp.spread_pnl_bps > 0;
              return (
                <tr key={i}>
                  <td className="text-gray-400 text-xs">
                    {getLegLabel(sp.spot_leg_id)}
                  </td>
                  <td className="text-gray-400 text-xs">
                    {getLegLabel(sp.perp_leg_id)}
                  </td>
                  <td className="text-right tabular-nums">
                    {formatBps(sp.entry_spread_bps)}
                  </td>
                  <td className="text-right tabular-nums">
                    {formatBps(sp.exit_spread_bps)}
                  </td>
                  <td className={`text-right tabular-nums font-medium ${pnlColor(sp.spread_pnl_bps)}`}>
                    {formatBps(sp.spread_pnl_bps)}
                  </td>
                  <td className="text-right">
                    <span
                      className={`text-xs ${
                        favorable ? "text-green-400" : "text-red-400"
                      }`}
                    >
                      {favorable ? "Favorable" : "Unfavorable"}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create CashflowTable component**

Create `frontend/components/CashflowTable.tsx`:

```tsx
import { formatUSD, formatDate, pnlColor } from "@/lib/format";
import type { Cashflow } from "@/lib/types";

interface Props {
  cashflows: Cashflow[];
}

export default function CashflowTable({ cashflows }: Props) {
  if (cashflows.length === 0) {
    return (
      <div className="card">
        <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
          Cashflows
        </div>
        <p className="text-sm text-gray-500">No cashflow events recorded.</p>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
        Cashflows ({cashflows.length})
      </div>
      <div className="overflow-x-auto max-h-96 overflow-y-auto">
        <table className="data-table">
          <thead className="sticky top-0 bg-gray-900">
            <tr>
              <th>Time</th>
              <th>Type</th>
              <th className="text-right">Amount</th>
              <th>Currency</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {cashflows.map((cf) => (
              <tr key={cf.cashflow_id}>
                <td className="text-gray-400 text-xs tabular-nums">
                  {formatDate(cf.ts)}
                </td>
                <td>
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded ${
                      cf.cf_type.includes("FUND")
                        ? "bg-blue-900/30 text-blue-400"
                        : cf.cf_type.includes("FEE")
                          ? "bg-yellow-900/30 text-yellow-400"
                          : cf.cf_type.includes("DEPOSIT")
                            ? "bg-green-900/30 text-green-400"
                            : cf.cf_type.includes("WITHDRAW")
                              ? "bg-red-900/30 text-red-400"
                              : "bg-gray-800 text-gray-400"
                    }`}
                  >
                    {cf.cf_type}
                  </span>
                </td>
                <td className={`text-right tabular-nums ${pnlColor(cf.amount)}`}>
                  {formatUSD(cf.amount)}
                </td>
                <td className="text-gray-400">{cf.currency}</td>
                <td className="text-gray-500 text-xs max-w-[200px] truncate">
                  {cf.description ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create FillsTable component**

Create `frontend/components/FillsTable.tsx`:

```tsx
import { formatUSD, formatPrice, formatNumber, formatDate } from "@/lib/format";
import type { Fill } from "@/lib/types";

interface Props {
  fills: Fill[];
  total: number;
}

export default function FillsTable({ fills, total }: Props) {
  if (fills.length === 0) {
    return (
      <div className="card">
        <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
          Fills
        </div>
        <p className="text-sm text-gray-500">No fills recorded.</p>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs text-gray-500 uppercase tracking-wide">
          Fills ({total})
        </div>
      </div>
      <div className="overflow-x-auto max-h-96 overflow-y-auto">
        <table className="data-table">
          <thead className="sticky top-0 bg-gray-900">
            <tr>
              <th>Time</th>
              <th>Instrument</th>
              <th>Side</th>
              <th>Direction</th>
              <th className="text-right">Price</th>
              <th className="text-right">Size</th>
              <th className="text-right">Notional</th>
              <th className="text-right">Fee</th>
            </tr>
          </thead>
          <tbody>
            {fills.map((fill) => (
              <tr key={fill.fill_id}>
                <td className="text-gray-400 text-xs tabular-nums">
                  {formatDate(fill.ts)}
                </td>
                <td className="font-mono text-white text-xs">{fill.inst_id}</td>
                <td>
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded ${
                      fill.side === "BUY"
                        ? "bg-green-900/30 text-green-400"
                        : "bg-red-900/30 text-red-400"
                    }`}
                  >
                    {fill.side}
                  </span>
                </td>
                <td className="text-gray-400 text-xs">{fill.dir ?? "—"}</td>
                <td className="text-right tabular-nums">
                  {formatPrice(fill.px)}
                </td>
                <td className="text-right tabular-nums">
                  {formatNumber(fill.sz, 4)}
                </td>
                <td className="text-right tabular-nums">
                  {formatUSD(fill.px * fill.sz)}
                </td>
                <td className="text-right tabular-nums text-yellow-400">
                  {fill.fee != null ? formatUSD(fill.fee) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Verify build**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend
npm run build
```

**Expected output:** Build succeeds. No TypeScript errors.

---

## Task 8: Position Detail Page

**Files:**
- Create: `frontend/app/positions/[id]/page.tsx`

- [ ] **Step 1: Create the position detail page**

Create `frontend/app/positions/[id]/page.tsx`:

```tsx
import Link from "next/link";
import { getPositionDetail, getPositionFills } from "@/lib/api";
import { formatUSD, formatPct, formatDate, pnlColor } from "@/lib/format";
import LegDetail from "@/components/LegDetail";
import SpreadDisplay from "@/components/SpreadDisplay";
import CashflowTable from "@/components/CashflowTable";
import FillsTable from "@/components/FillsTable";

export const revalidate = 60;

interface Props {
  params: Promise<{ id: string }>;
}

export default async function PositionDetailPage({ params }: Props) {
  const { id } = await params;

  let position;
  let fills;
  let error: string | null = null;

  try {
    [position, fills] = await Promise.all([
      getPositionDetail(id),
      getPositionFills(id),
    ]);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to fetch position data";
  }

  if (error || !position || !fills) {
    return (
      <div className="space-y-6">
        <Link href="/" className="text-sm text-gray-400 hover:text-white">
          &larr; Back to Dashboard
        </Link>
        <div className="card border-red-900">
          <p className="text-red-400">Failed to load position</p>
          <p className="text-sm text-gray-500 mt-1">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <Link href="/" className="text-sm text-gray-400 hover:text-white">
        &larr; Back to Dashboard
      </Link>

      {/* Header card */}
      <div className="card">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">{position.base}</h1>
            <p className="text-sm text-gray-400 mt-1">
              {position.position_id} | {position.strategy}
            </p>
          </div>
          <div className="text-right">
            <span
              className={`text-sm px-2 py-1 rounded ${
                position.status === "OPEN"
                  ? "bg-green-900/30 text-green-400"
                  : position.status === "PAUSED"
                    ? "bg-yellow-900/30 text-yellow-400"
                    : position.status === "EXITING"
                      ? "bg-orange-900/30 text-orange-400"
                      : "bg-gray-800 text-gray-400"
              }`}
            >
              {position.status}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-4">
          <div>
            <div className="text-xs text-gray-500">Amount</div>
            <div className="text-lg font-semibold text-white tabular-nums">
              {formatUSD(position.amount_usd)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">uPnL</div>
            <div className={`text-lg font-semibold tabular-nums ${pnlColor(position.unrealized_pnl)}`}>
              {formatUSD(position.unrealized_pnl)}
              {position.unrealized_pnl_pct != null && (
                <span className="text-sm ml-1">
                  ({formatPct(position.unrealized_pnl_pct)})
                </span>
              )}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Funding</div>
            <div className={`text-lg font-semibold tabular-nums ${pnlColor(position.funding_earned)}`}>
              {formatUSD(position.funding_earned)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Carry APR</div>
            <div className={`text-lg font-semibold tabular-nums ${pnlColor(position.carry_apr)}`}>
              {position.carry_apr != null ? formatPct(position.carry_apr, 1) : "—"}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Opened</div>
            <div className="text-sm text-gray-300">
              {formatDate(position.opened_at)}
            </div>
          </div>
        </div>

        {/* Daily funding mini bar chart */}
        {position.daily_funding_series && position.daily_funding_series.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-800">
            <div className="text-xs text-gray-500 mb-2">
              Daily Funding (last {position.daily_funding_series.length} days)
            </div>
            <FundingBarChart series={position.daily_funding_series} />
          </div>
        )}
      </div>

      {/* Legs */}
      <LegDetail legs={position.legs} />

      {/* Spreads */}
      <SpreadDisplay subPairs={position.sub_pairs} legs={position.legs} />

      {/* Cashflows */}
      <CashflowTable cashflows={position.cashflows} />

      {/* Fills */}
      <FillsTable fills={fills.fills} total={fills.total} />
    </div>
  );
}

// Simple bar chart using divs — no charting library needed
function FundingBarChart({
  series,
}: {
  series: { date: string; amount: number }[];
}) {
  const maxAbs = Math.max(...series.map((s) => Math.abs(s.amount)), 0.01);

  return (
    <div className="flex items-end gap-1 h-16">
      {series.map((s) => {
        const heightPct = Math.abs(s.amount / maxAbs) * 100;
        const isPositive = s.amount >= 0;

        return (
          <div
            key={s.date}
            className="flex-1 flex flex-col items-center justify-end h-full"
            title={`${s.date}: $${s.amount.toFixed(2)}`}
          >
            <div
              className={`w-full rounded-sm ${
                isPositive ? "bg-green-500/60" : "bg-red-500/60"
              }`}
              style={{ height: `${Math.max(heightPct, 2)}%` }}
            />
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend
npm run build
```

**Expected output:** Build succeeds. Dynamic route compiles.

---

## Task 9: Closed Positions Page

**Files:**
- Create: `frontend/app/closed/page.tsx`

- [ ] **Step 1: Create the closed positions page**

Create `frontend/app/closed/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { formatUSD, formatPct, formatBps, formatNumber, pnlColor } from "@/lib/format";
import type { ClosedPosition } from "@/lib/types";

// NOTE: This page uses a client component for sortable columns.
// Data is fetched via a server action wrapper. See step 2 below.

type SortKey = "base" | "duration_days" | "amount_usd" | "net_pnl" | "net_apr";

interface Props {
  closedPositions: ClosedPosition[];
}

function ClosedPositionsClient({ closedPositions }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("net_apr");
  const [sortAsc, setSortAsc] = useState(false);

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(key === "base");
    }
  }

  const sorted = [...closedPositions].sort((a, b) => {
    const va = a[sortKey];
    const vb = b[sortKey];
    const cmp =
      typeof va === "string"
        ? (va as string).localeCompare(vb as string)
        : (va as number) - (vb as number);
    return sortAsc ? cmp : -cmp;
  });

  const totals = closedPositions.reduce(
    (acc, p) => ({
      spread: acc.spread + p.realized_spread_pnl,
      funding: acc.funding + p.total_funding_earned,
      fees: acc.fees + p.total_fees_paid,
      net: acc.net + p.net_pnl,
    }),
    { spread: 0, funding: 0, fees: 0, net: 0 },
  );

  function SortHeader({ label, sortId }: { label: string; sortId: SortKey }) {
    const isActive = sortKey === sortId;
    return (
      <th
        onClick={() => handleSort(sortId)}
        className="cursor-pointer select-none hover:text-gray-200 transition-colors"
      >
        {label}
        {isActive && (
          <span className="ml-1 text-gray-500">
            {sortAsc ? "\u25B2" : "\u25BC"}
          </span>
        )}
      </th>
    );
  }

  return (
    <div className="card">
      {/* Summary row */}
      <div className="grid grid-cols-4 gap-4 mb-4 pb-4 border-b border-gray-800">
        <div>
          <div className="text-xs text-gray-500">Total Spread P&L</div>
          <div className={`text-lg font-semibold tabular-nums ${pnlColor(totals.spread)}`}>
            {formatUSD(totals.spread)}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500">Total Funding</div>
          <div className={`text-lg font-semibold tabular-nums ${pnlColor(totals.funding)}`}>
            {formatUSD(totals.funding)}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500">Total Fees</div>
          <div className={`text-lg font-semibold tabular-nums ${pnlColor(totals.fees)}`}>
            {formatUSD(totals.fees)}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500">Total Net P&L</div>
          <div className={`text-lg font-semibold tabular-nums ${pnlColor(totals.net)}`}>
            {formatUSD(totals.net)}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <SortHeader label="Base" sortId="base" />
              <SortHeader label="Duration" sortId="duration_days" />
              <SortHeader label="Amount" sortId="amount_usd" />
              <th className="text-right">Entry Spread</th>
              <th className="text-right">Exit Spread</th>
              <th className="text-right">Spread P&L</th>
              <th className="text-right">Funding</th>
              <th className="text-right">Fees</th>
              <SortHeader label="Net P&L" sortId="net_pnl" />
              <SortHeader label="Net APR" sortId="net_apr" />
            </tr>
          </thead>
          <tbody>
            {sorted.map((p) => (
              <tr
                key={p.position_id}
                className={`hover:bg-gray-800/50 transition-colors ${
                  p.net_pnl >= 0
                    ? "border-l-2 border-l-green-500/30"
                    : "border-l-2 border-l-red-500/30"
                }`}
              >
                <td className="font-medium text-white">{p.base}</td>
                <td className="tabular-nums">{p.duration_days}d</td>
                <td className="text-right tabular-nums">{formatUSD(p.amount_usd)}</td>
                <td className="text-right tabular-nums">
                  {formatBps(p.entry_spread_bps)}
                </td>
                <td className="text-right tabular-nums">
                  {formatBps(p.exit_spread_bps)}
                </td>
                <td className={`text-right tabular-nums ${pnlColor(p.realized_spread_pnl)}`}>
                  {formatUSD(p.realized_spread_pnl)}
                </td>
                <td className={`text-right tabular-nums ${pnlColor(p.total_funding_earned)}`}>
                  {formatUSD(p.total_funding_earned)}
                </td>
                <td className={`text-right tabular-nums ${pnlColor(p.total_fees_paid)}`}>
                  {formatUSD(p.total_fees_paid)}
                </td>
                <td className={`text-right tabular-nums font-medium ${pnlColor(p.net_pnl)}`}>
                  {formatUSD(p.net_pnl)}
                </td>
                <td className={`text-right tabular-nums font-medium ${pnlColor(p.net_apr)}`}>
                  {formatPct(p.net_apr, 1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default ClosedPositionsClient;
```

- [ ] **Step 2: Create the server page wrapper**

Since we need server-side data fetching but client-side sorting, create the actual page file that wraps the client component.

Replace the content of `frontend/app/closed/page.tsx` with a server component that imports the client component. We need two files.

First, rename the client component: create `frontend/components/ClosedPositionsClient.tsx` with the content from Step 1 above (move the entire code).

Then create `frontend/app/closed/page.tsx`:

```tsx
import { getClosedPositions } from "@/lib/api";
import ClosedPositionsClient from "@/components/ClosedPositionsClient";

export const revalidate = 60;

export default async function ClosedPositionsPage() {
  let closedPositions;
  let error: string | null = null;

  try {
    closedPositions = await getClosedPositions();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to fetch closed positions";
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Closed Positions</h1>

      {error || !closedPositions ? (
        <div className="card border-red-900">
          <p className="text-red-400">Failed to load closed positions</p>
          <p className="text-sm text-gray-500 mt-1">{error}</p>
        </div>
      ) : closedPositions.length === 0 ? (
        <div className="card">
          <p className="text-gray-500">No closed positions yet.</p>
        </div>
      ) : (
        <ClosedPositionsClient closedPositions={closedPositions} />
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create the ClosedPositionsClient component file**

Create `frontend/components/ClosedPositionsClient.tsx` with the client component code from Step 1 (the full `"use client"` component). Remove the unused imports (`useEffect`, `useState` — keep `useState`).

The final file should be:

```tsx
"use client";

import { useState } from "react";
import { formatUSD, formatPct, formatBps, pnlColor } from "@/lib/format";
import type { ClosedPosition } from "@/lib/types";

type SortKey = "base" | "duration_days" | "amount_usd" | "net_pnl" | "net_apr";

interface Props {
  closedPositions: ClosedPosition[];
}

export default function ClosedPositionsClient({ closedPositions }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("net_apr");
  const [sortAsc, setSortAsc] = useState(false);

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(key === "base");
    }
  }

  const sorted = [...closedPositions].sort((a, b) => {
    const va = a[sortKey];
    const vb = b[sortKey];
    const cmp =
      typeof va === "string"
        ? (va as string).localeCompare(vb as string)
        : (va as number) - (vb as number);
    return sortAsc ? cmp : -cmp;
  });

  const totals = closedPositions.reduce(
    (acc, p) => ({
      spread: acc.spread + p.realized_spread_pnl,
      funding: acc.funding + p.total_funding_earned,
      fees: acc.fees + p.total_fees_paid,
      net: acc.net + p.net_pnl,
    }),
    { spread: 0, funding: 0, fees: 0, net: 0 },
  );

  function SortHeader({ label, sortId }: { label: string; sortId: SortKey }) {
    const isActive = sortKey === sortId;
    return (
      <th
        onClick={() => handleSort(sortId)}
        className="cursor-pointer select-none hover:text-gray-200 transition-colors"
      >
        {label}
        {isActive && (
          <span className="ml-1 text-gray-500">
            {sortAsc ? "\u25B2" : "\u25BC"}
          </span>
        )}
      </th>
    );
  }

  return (
    <div className="card">
      {/* Summary row */}
      <div className="grid grid-cols-4 gap-4 mb-4 pb-4 border-b border-gray-800">
        <div>
          <div className="text-xs text-gray-500">Total Spread P&L</div>
          <div className={`text-lg font-semibold tabular-nums ${pnlColor(totals.spread)}`}>
            {formatUSD(totals.spread)}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500">Total Funding</div>
          <div className={`text-lg font-semibold tabular-nums ${pnlColor(totals.funding)}`}>
            {formatUSD(totals.funding)}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500">Total Fees</div>
          <div className={`text-lg font-semibold tabular-nums ${pnlColor(totals.fees)}`}>
            {formatUSD(totals.fees)}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500">Total Net P&L</div>
          <div className={`text-lg font-semibold tabular-nums ${pnlColor(totals.net)}`}>
            {formatUSD(totals.net)}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <SortHeader label="Base" sortId="base" />
              <SortHeader label="Duration" sortId="duration_days" />
              <SortHeader label="Amount" sortId="amount_usd" />
              <th className="text-right">Entry Spread</th>
              <th className="text-right">Exit Spread</th>
              <th className="text-right">Spread P&L</th>
              <th className="text-right">Funding</th>
              <th className="text-right">Fees</th>
              <SortHeader label="Net P&L" sortId="net_pnl" />
              <SortHeader label="Net APR" sortId="net_apr" />
            </tr>
          </thead>
          <tbody>
            {sorted.map((p) => (
              <tr
                key={p.position_id}
                className={`hover:bg-gray-800/50 transition-colors ${
                  p.net_pnl >= 0
                    ? "border-l-2 border-l-green-500/30"
                    : "border-l-2 border-l-red-500/30"
                }`}
              >
                <td className="font-medium text-white">{p.base}</td>
                <td className="tabular-nums">{p.duration_days}d</td>
                <td className="text-right tabular-nums">{formatUSD(p.amount_usd)}</td>
                <td className="text-right tabular-nums">
                  {formatBps(p.entry_spread_bps)}
                </td>
                <td className="text-right tabular-nums">
                  {formatBps(p.exit_spread_bps)}
                </td>
                <td className={`text-right tabular-nums ${pnlColor(p.realized_spread_pnl)}`}>
                  {formatUSD(p.realized_spread_pnl)}
                </td>
                <td className={`text-right tabular-nums ${pnlColor(p.total_funding_earned)}`}>
                  {formatUSD(p.total_funding_earned)}
                </td>
                <td className={`text-right tabular-nums ${pnlColor(p.total_fees_paid)}`}>
                  {formatUSD(p.total_fees_paid)}
                </td>
                <td className={`text-right tabular-nums font-medium ${pnlColor(p.net_pnl)}`}>
                  {formatUSD(p.net_pnl)}
                </td>
                <td className={`text-right tabular-nums font-medium ${pnlColor(p.net_apr)}`}>
                  {formatPct(p.net_apr, 1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify build**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend
npm run build
```

**Expected output:** Build succeeds.

---

## Task 10: Settings Page with Manual Cashflow Form

**Files:**
- Create: `frontend/components/ManualCashflowForm.tsx`
- Create: `frontend/app/settings/page.tsx`
- Create: `frontend/app/settings/actions.ts`

- [ ] **Step 1: Create the server action for manual cashflow**

Create `frontend/app/settings/actions.ts`:

```typescript
"use server";

import { postManualCashflow } from "@/lib/api";
import type { ManualCashflowRequest } from "@/lib/types";

export interface ActionResult {
  success: boolean;
  message: string;
  cashflow_id?: number;
}

export async function submitManualCashflow(
  formData: FormData,
): Promise<ActionResult> {
  const account_id = formData.get("account_id") as string;
  const venue = formData.get("venue") as string;
  const cf_type = formData.get("cf_type") as "DEPOSIT" | "WITHDRAW";
  const amount = parseFloat(formData.get("amount") as string);
  const currency = formData.get("currency") as string;
  const description = formData.get("description") as string;

  // Validation
  if (!account_id || !venue || !cf_type || isNaN(amount) || amount <= 0) {
    return {
      success: false,
      message: "All fields are required and amount must be positive.",
    };
  }

  if (cf_type !== "DEPOSIT" && cf_type !== "WITHDRAW") {
    return {
      success: false,
      message: "Type must be DEPOSIT or WITHDRAW.",
    };
  }

  const payload: ManualCashflowRequest = {
    account_id,
    venue,
    cf_type,
    amount,
    currency: currency || "USDC",
    description: description || undefined,
  };

  try {
    const result = await postManualCashflow(payload);
    return {
      success: true,
      message: `${cf_type} of $${amount.toFixed(2)} recorded successfully.`,
      cashflow_id: result.cashflow_id,
    };
  } catch (e) {
    return {
      success: false,
      message: e instanceof Error ? e.message : "Failed to submit cashflow.",
    };
  }
}
```

- [ ] **Step 2: Create ManualCashflowForm**

Create `frontend/components/ManualCashflowForm.tsx`:

```tsx
"use client";

import { useState, useTransition } from "react";
import { submitManualCashflow, type ActionResult } from "@/app/settings/actions";

export default function ManualCashflowForm() {
  const [isPending, startTransition] = useTransition();
  const [result, setResult] = useState<ActionResult | null>(null);

  function handleSubmit(formData: FormData) {
    startTransition(async () => {
      const res = await submitManualCashflow(formData);
      setResult(res);
    });
  }

  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-4">
        Manual Deposit / Withdraw
      </div>

      {result && (
        <div
          className={`mb-4 p-3 rounded text-sm ${
            result.success
              ? "bg-green-900/20 text-green-400 border border-green-800"
              : "bg-red-900/20 text-red-400 border border-red-800"
          }`}
        >
          {result.message}
          {result.cashflow_id && (
            <span className="ml-2 text-xs text-gray-500">
              ID: {result.cashflow_id}
            </span>
          )}
        </div>
      )}

      <form action={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Account ID */}
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Account Address
            </label>
            <input
              name="account_id"
              type="text"
              required
              placeholder="0x..."
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
            />
          </div>

          {/* Venue */}
          <div>
            <label className="block text-xs text-gray-400 mb-1">Venue</label>
            <select
              name="venue"
              required
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
            >
              <option value="hyperliquid">Hyperliquid</option>
              <option value="felix">Felix</option>
            </select>
          </div>

          {/* Type */}
          <div>
            <label className="block text-xs text-gray-400 mb-1">Type</label>
            <select
              name="cf_type"
              required
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
            >
              <option value="DEPOSIT">Deposit</option>
              <option value="WITHDRAW">Withdraw</option>
            </select>
          </div>

          {/* Amount */}
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Amount (positive)
            </label>
            <input
              name="amount"
              type="number"
              step="0.01"
              min="0.01"
              required
              placeholder="1000.00"
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
            />
          </div>

          {/* Currency */}
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Currency
            </label>
            <input
              name="currency"
              type="text"
              defaultValue="USDC"
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Description (optional)
            </label>
            <input
              name="description"
              type="text"
              placeholder="Deposit from Arbitrum bridge"
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={isPending}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded transition-colors"
        >
          {isPending ? "Submitting..." : "Submit"}
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 3: Create the settings page**

Create `frontend/app/settings/page.tsx`:

```tsx
import { getHealth } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import ManualCashflowForm from "@/components/ManualCashflowForm";

export const revalidate = 60;

export default async function SettingsPage() {
  let health;
  let error: string | null = null;

  try {
    health = await getHealth();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to fetch health data";
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      {/* Manual cashflow form */}
      <ManualCashflowForm />

      {/* System info */}
      <div className="card">
        <div className="text-xs text-gray-500 uppercase tracking-wide mb-4">
          System Information
        </div>

        {error || !health ? (
          <p className="text-red-400 text-sm">
            Failed to load system info. {error}
          </p>
        ) : (
          <div className="space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <div className="text-xs text-gray-500">Status</div>
                <div className="flex items-center gap-2">
                  <div
                    className={`w-2 h-2 rounded-full ${
                      health.status === "ok" ? "bg-green-400" : "bg-red-400"
                    }`}
                  />
                  <span className="text-sm text-white">{health.status}</span>
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Open Positions</div>
                <div className="text-sm text-white">{health.open_positions}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">DB Size</div>
                <div className="text-sm text-white">
                  {health.db_size_mb.toFixed(1)} MB
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Uptime</div>
                <div className="text-sm text-white">
                  {Math.floor(health.uptime_seconds / 3600)}h{" "}
                  {Math.floor((health.uptime_seconds % 3600) / 60)}m
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Last Fill Ingestion</div>
                <div className="text-sm text-white">
                  {formatRelative(health.last_fill_ingestion)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Last Price Pull</div>
                <div className="text-sm text-white">
                  {formatRelative(health.last_price_pull)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Last Position Pull</div>
                <div className="text-sm text-white">
                  {formatRelative(health.last_position_pull)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Felix JWT Expiry</div>
                <div className="text-sm text-white">
                  {formatRelative(health.felix_jwt_expires_at)}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Tracking config (display only for now) */}
      <div className="card">
        <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
          Configuration
        </div>
        <div className="text-sm text-gray-400">
          <p>
            Tracking start date and other configuration will be managed via the
            API in a future update.
          </p>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify build**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend
npm run build
```

**Expected output:** Build succeeds. Settings page compiles with server action.

---

## Task 11: Mobile Responsive Adjustments

**Files:**
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/components/NavSidebar.tsx`

- [ ] **Step 1: Add mobile hamburger menu to NavSidebar**

Update `frontend/components/NavSidebar.tsx` to include a mobile toggle. Add a hamburger button that shows on small screens and hides the sidebar behind a slide-out:

Add at the top of the component, inside the function:

```tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

// ... navItems and NavIcon remain the same ...

export default function NavSidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      {/* Mobile hamburger button */}
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        className="md:hidden fixed top-4 left-4 z-[60] p-2 bg-gray-800 rounded-lg border border-gray-700"
        aria-label="Toggle navigation"
      >
        <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          {mobileOpen ? (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          )}
        </svg>
      </button>

      {/* Overlay */}
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/50 z-40"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed left-0 top-0 h-full w-56 bg-gray-900 border-r border-gray-800 flex flex-col z-50 transition-transform duration-200 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        {/* ... rest of sidebar content unchanged ... */}
      </aside>
    </>
  );
}
```

- [ ] **Step 2: Update layout for mobile**

Update `frontend/app/layout.tsx` — change the main content margin to be responsive:

```tsx
<main className="md:ml-56 min-h-screen p-4 md:p-6 pt-14 md:pt-6">
  {children}
</main>
```

The `pt-14` on mobile gives space for the hamburger button.

- [ ] **Step 3: Verify build**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend
npm run build
```

**Expected output:** Build succeeds. Layout is responsive.

---

## Task 12: Vercel Deployment

- [ ] **Step 1: Verify the project builds cleanly**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend
npm run build
```

**Expected output:** Build succeeds with all pages compiled:

```
Route (app)                              Size     First Load JS
/                                        ...      ...
/closed                                  ...      ...
/positions/[id]                          ...      ...
/settings                                ...      ...
```

- [ ] **Step 2: Install Vercel CLI (if not installed)**

```bash
npm i -g vercel
```

- [ ] **Step 3: Deploy to Vercel**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend
vercel
```

Follow the interactive prompts:
- Set up and deploy? **Y**
- Which scope? Select your account
- Link to existing project? **N** (create new)
- Project name: `openclaw-dashboard` (or preferred name)
- Framework preset: **Next.js** (auto-detected)
- Root directory: `.` (since we are inside `frontend/`)

**Expected output:** Deployment URL provided.

- [ ] **Step 4: Set environment variables on Vercel**

```bash
vercel env add API_BASE_URL production
# Enter: https://your-cloudflare-tunnel-domain.com

vercel env add API_KEY production
# Enter: your-api-key-from-vault
```

These are **server-side only** env vars (no NEXT_PUBLIC prefix), so they are never exposed to the browser.

- [ ] **Step 5: Redeploy with env vars**

```bash
vercel --prod
```

**Expected output:** Production deployment at the assigned domain.

- [ ] **Step 6: Verify all pages load with real data**

Open the Vercel deployment URL and verify:

1. **Dashboard `/`**: Shows equity card, wallet breakdown, funding summary, positions table, health status bar.
2. **Position Detail `/positions/{id}`**: Click any position from dashboard. Shows legs, spreads, cashflows, fills.
3. **Closed Positions `/closed`**: Shows table with P&L breakdown. Sortable columns work.
4. **Settings `/settings`**: Shows manual cashflow form and system info. Submit a test entry to verify form works end-to-end.
5. **Mobile**: Open on phone or resize browser. Navigation hamburger works. Tables scroll horizontally.

**Expected output:** All 4 pages render with real data from the backend. No console errors. Colors correct (green for positive, red for negative).

---

## Verification Checklist

After all tasks are complete, verify these acceptance criteria:

- [ ] `npm run build` succeeds with zero errors and zero warnings
- [ ] Dashboard shows correct equity, positions, and funding data from the API
- [ ] Position detail shows legs, sub-pair spreads, cashflows, and fills
- [ ] Closed positions page shows P&L breakdown with correct color coding
- [ ] Tables are sortable by clicking column headers
- [ ] Manual deposit/withdraw form submits successfully via server action
- [ ] Settings page shows system health info
- [ ] Mobile responsive: sidebar collapses, tables scroll, cards stack
- [ ] No `NEXT_PUBLIC_` env vars exist (all API access is server-side)
- [ ] Vercel deployment loads all pages with real backend data
- [ ] Green (#22c55e / green-400) for positive P&L, Red (#ef4444 / red-400) for negative
- [ ] Numbers formatted: USD 2 decimals, percentages 1-2 decimals, bps as integers
