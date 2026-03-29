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
  long_leg_id: string;
  short_leg_id: string;
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
