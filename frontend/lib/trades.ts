// frontend/lib/trades.ts
// API client for the /api/trades endpoints (proxied via /api/harmonix/*).
// Client-side only — uses the same-origin proxy route which injects auth headers
// server-side. Do NOT import process.env here.

export type TradeType = "OPEN" | "CLOSE";
export type TradeState = "DRAFT" | "FINALIZED";

export interface Trade {
  trade_id: string;
  position_id: string;
  trade_type: TradeType;
  state: TradeState;
  start_ts: number;
  end_ts: number;
  note: string | null;

  long_leg_id: string;
  long_size: number | null;
  long_notional: number | null;
  long_avg_px: number | null;
  long_fees: number | null;
  long_fill_count: number | null;

  short_leg_id: string;
  short_size: number | null;
  short_notional: number | null;
  short_avg_px: number | null;
  short_fees: number | null;
  short_fill_count: number | null;

  spread_bps: number | null;
  realized_pnl_bps: number | null;

  created_at_ms: number;
  finalized_at_ms: number | null;
  computed_at_ms: number;

  unassigned_fills_count: number | null;
}

export interface LinkedFill {
  fill_id: number;
  leg_side: "LONG" | "SHORT";
  inst_id: string;
  side: "BUY" | "SELL";
  px: number;
  sz: number;
  fee: number | null;
  ts: number;
}

export interface TradeDetail extends Trade {
  fills: LinkedFill[];
}

export interface TradeListFilters {
  position_id?: string;
  trade_type?: TradeType;
  state?: TradeState;
  start_ts_gte?: number;
  end_ts_lte?: number;
}

export interface TradeCreateInput {
  position_id: string;
  trade_type: TradeType;
  start_ts: number;
  end_ts: number;
  note?: string;
}

// Proxy base: the Next.js route /api/harmonix/[...path]/route.ts forwards to the
// backend. Client components call this same-origin path; the proxy adds API_BASE_URL
// and auth headers server-side (no NEXT_PUBLIC_* needed).
const PROXY_BASE = "/api/harmonix";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${PROXY_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  // DELETE returns 204 no content
  if (res.status === 204) {
    return undefined as unknown as T;
  }
  return res.json() as Promise<T>;
}

export async function listTrades(
  filters: TradeListFilters = {},
): Promise<{ items: Trade[]; total: number }> {
  const qs = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v != null) qs.set(k, String(v));
  });
  const suffix = qs.toString() ? `?${qs}` : "";
  return request(`/trades${suffix}`);
}

export async function getTrade(id: string): Promise<TradeDetail> {
  return request(`/trades/${encodeURIComponent(id)}`);
}

export async function previewTrade(input: TradeCreateInput): Promise<Trade> {
  return request("/trades/preview", { method: "POST", body: JSON.stringify(input) });
}

export async function createTrade(input: TradeCreateInput): Promise<Trade> {
  return request("/trades", { method: "POST", body: JSON.stringify(input) });
}

export async function editTrade(
  id: string,
  patch: Partial<TradeCreateInput>,
): Promise<Trade> {
  return request(`/trades/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function finalizeTrade(id: string): Promise<Trade> {
  return request(`/trades/${encodeURIComponent(id)}/finalize`, { method: "POST" });
}

export async function reopenTrade(id: string): Promise<Trade> {
  return request(`/trades/${encodeURIComponent(id)}/reopen`, { method: "POST" });
}

export async function recomputeTrade(id: string): Promise<Trade> {
  return request(`/trades/${encodeURIComponent(id)}/recompute`, { method: "POST" });
}

export async function deleteTrade(id: string): Promise<void> {
  await request(`/trades/${encodeURIComponent(id)}`, { method: "DELETE" });
}
