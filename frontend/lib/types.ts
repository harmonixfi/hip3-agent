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
  daily_change_usd: number | null;
  daily_change_pct: number | null;
  cashflow_adjusted_apr: number | null;
  funding_today_usd: number;
  funding_alltime_usd: number;
  fees_alltime_usd: number;
  net_pnl_alltime_usd: number;
  tracking_start_date: string;
  open_positions_count: number;
  total_unrealized_pnl: number;
  as_of: string;
  fund_utilization: FundUtilization | null;
}

// ============================================================
// Fund Utilization — nested in /api/portfolio/overview
// ============================================================

export interface AccountUtilization {
  label: string;
  venue: string;
  equity_usd: number;
  margin_used_usd: number;
  available_usd: number;
  position_value_usd: number;
  leverage: number;
}

export interface FundUtilization {
  total_equity_usd: number;
  total_notional_usd: number;
  total_deployed_usd: number;
  total_available_usd: number;
  leverage: number;
  deployed_pct: number;
  accounts: AccountUtilization[];
}

// ============================================================
// Positions — GET /api/positions, GET /api/positions/{id}
// ============================================================

export interface SubPair {
  long_leg_id: string;
  short_leg_id: string;
  entry_spread_bps: number | null;
  exit_spread_bps: number | null;
  spread_pnl_bps: number | null;
}

export interface WindowedMetrics {
  funding_1d:          number | null;
  funding_3d:          number | null;
  funding_7d:          number | null;
  funding_14d:         number | null;
  apr_1d:              number | null;  // percent form e.g. 38.5 means 38.5%
  apr_3d:              number | null;
  apr_7d:              number | null;
  apr_14d:             number | null;
  incomplete_notional: boolean;
  missing_leg_ids:     string[];
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
  windowed: WindowedMetrics | null;
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
  opened_at: string | null;
  closed_at: string | null;
  duration_days: number | null;
  amount_usd: number | null;
  realized_spread_pnl: number | null;
  total_funding_earned: number | null;
  total_fees_paid: number | null;
  net_pnl: number | null;
  net_apr: number | null;
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

/** POST /api/cashflows/manual — deposit/withdraw (single strategy) or internal transfer */
export type ManualCashflowRequest =
  | {
      strategy_id: string;
      account_id?: string;
      cf_type: "DEPOSIT" | "WITHDRAW";
      amount: number;
      currency: string;
      ts?: number;
      description?: string;
    }
  | {
      from_strategy_id: string;
      to_strategy_id: string;
      account_id?: string;
      cf_type: "TRANSFER";
      amount: number;
      currency: string;
      ts?: number;
      description?: string;
    };

export interface ManualCashflowResponse {
  cashflow_id: number;
  vault_cashflow_id: number;
  message: string;
  pm_cashflow_ids: number[];
  /** True when vault/strategy snapshots were recomputed for overview APR */
  snapshot_refreshed?: boolean;
  snapshot_error?: string | null;
}

/** GET /api/cashflows/manual — manual source rows only */
export interface ManualCashflowListItem {
  cashflow_id: number;
  ts: number;
  cf_type: string;
  amount: number;
  currency: string;
  strategy_id: string | null;
  venue: string | null;
  account_id: string | null;
  description: string | null;
  internal_transfer_id?: string | null;
}

export interface ManualCashflowListResponse {
  items: ManualCashflowListItem[];
  limit: number;
}

// ============================================================
// Vault — /api/vault/*
// ============================================================

export interface StrategySummary {
  strategy_id: string;
  name: string;
  type: string;
  status: string;
  equity_usd: number | null;
  weight_pct: number | null;
  target_weight_pct: number | null;
  apr_since_inception: number | null;
  apr_30d: number | null;
  apr_7d: number | null;
}

export interface VaultOverview {
  vault_name: string;
  total_equity_usd: number;
  total_apr: number | null;
  apr_30d: number | null;
  apr_7d: number | null;
  net_deposits_alltime: number | null;
  strategies: StrategySummary[];
  as_of: string | null;
}

export interface VaultCashflow {
  cashflow_id: number;
  ts: number;
  cf_type: string;
  amount: number;
  currency: string;
  strategy_id: string | null;
  from_strategy_id: string | null;
  to_strategy_id: string | null;
  description: string | null;
}

export interface VaultSnapshot {
  ts: number;
  total_equity_usd: number;
  total_apr: number | null;
  apr_30d: number | null;
  apr_7d: number | null;
  strategy_weights: Record<string, number> | null;
}

export interface StrategyDetail {
  strategy_id: string;
  name: string;
  type: string;
  status: string;
  target_weight_pct: number | null;
  equity_usd: number | null;
  apr_since_inception: number | null;
  apr_30d: number | null;
  apr_7d: number | null;
  equity_breakdown: Record<string, unknown> | null;
  wallets: { wallet_label: string; venue: string }[] | null;
}

/** GET /api/vault/strategies/{id}/snapshots — daily strategy equity history */
export interface StrategySnapshot {
  ts: number;
  equity_usd: number;
  apr_since_inception: number | null;
  apr_30d: number | null;
  apr_7d: number | null;
}

// ============================================================
// Candidates — GET /api/candidates
// ============================================================

export interface Candidate {
  rank: number;
  symbol: string;
  venue: string;
  apr_14d: number | null;
  apr_7d: number | null;
  apr_1d: number | null;
  apr_3d: number | null;
  stability_score: number | null;
  flags: string;
  tradeability_status: string;
}

export interface CandidatesResponse {
  general: Candidate[];
  equities: Candidate[];
  as_of: string;
  total: number;
}

// ============================================================
// Vault — /api/vault/*
// ============================================================

export interface StrategySummary {
  strategy_id: string;
  name: string;
  type: string;
  status: string;
  equity_usd: number | null;
  weight_pct: number | null;
  target_weight_pct: number | null;
  apr_since_inception: number | null;
  apr_30d: number | null;
  apr_7d: number | null;
}

export interface VaultOverview {
  vault_name: string;
  total_equity_usd: number;
  total_apr: number | null;
  apr_30d: number | null;
  apr_7d: number | null;
  net_deposits_alltime: number | null;
  strategies: StrategySummary[];
  as_of: string | null;
}

export interface VaultCashflow {
  cashflow_id: number;
  ts: number;
  cf_type: string;
  amount: number;
  currency: string;
  strategy_id: string | null;
  from_strategy_id: string | null;
  to_strategy_id: string | null;
  description: string | null;
}

export interface VaultSnapshot {
  ts: number;
  total_equity_usd: number;
  total_apr: number | null;
  apr_30d: number | null;
  apr_7d: number | null;
  strategy_weights: Record<string, number> | null;
}

export interface StrategyDetail {
  strategy_id: string;
  name: string;
  type: string;
  status: string;
  target_weight_pct: number | null;
  equity_usd: number | null;
  apr_since_inception: number | null;
  apr_30d: number | null;
  apr_7d: number | null;
  equity_breakdown: Record<string, unknown> | null;
  wallets: { wallet_label: string; venue: string }[] | null;
}

// ============================================================
// Candidates — GET /api/candidates
// ============================================================

export interface Candidate {
  rank: number;
  symbol: string;
  venue: string;
  apr_14d: number | null;
  apr_7d: number | null;
  apr_1d: number | null;
  apr_3d: number | null;
  stability_score: number | null;
  flags: string;
  tradeability_status: string;
}

export interface CandidatesResponse {
  general: Candidate[];
  equities: Candidate[];
  as_of: string;
  total: number;
}
