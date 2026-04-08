import type {
  PortfolioOverview,
  Position,
  PositionDetail,
  FillsResponse,
  ClosedPosition,
  HealthStatus,
  ManualCashflowRequest,
  ManualCashflowResponse,
  ManualCashflowListResponse,
  VaultOverview,
  VaultSnapshot,
  VaultCashflow,
  StrategyDetail,
  StrategySnapshot,
  CandidatesResponse,
} from "./types";

/** Server-side only. Browser code uses `/api/harmonix/*` proxy (see `app/api/harmonix/[...path]/route.ts`). */
const API_BASE_URL = process.env.API_BASE_URL;
const API_KEY = process.env.API_KEY;
const CF_ACCESS_CLIENT_ID = process.env.CF_ACCESS_CLIENT_ID;
const CF_ACCESS_CLIENT_SECRET = process.env.CF_ACCESS_CLIENT_SECRET;

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Same-origin proxy path for client; FastAPI path always starts with `/api/`. */
function harmonixProxyUrl(path: string): string {
  const qIdx = path.indexOf("?");
  const pathPart = qIdx >= 0 ? path.slice(0, qIdx) : path;
  const query = qIdx >= 0 ? path.slice(qIdx) : "";
  const rest = pathPart.replace(/^\/api\/?/, "");
  return `/api/harmonix/${rest}${query}`;
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const isServer = typeof window === "undefined";

  if (isServer && !API_BASE_URL) {
    throw new Error("Set API_BASE_URL in frontend/.env.local");
  }

  const url = isServer ? `${API_BASE_URL}${path}` : harmonixProxyUrl(path);

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (isServer && API_KEY) {
    headers["X-API-Key"] = API_KEY;
  }

  if (CF_ACCESS_CLIENT_ID && CF_ACCESS_CLIENT_SECRET) {
    headers["CF-Access-Client-Id"] = CF_ACCESS_CLIENT_ID;
    headers["CF-Access-Client-Secret"] = CF_ACCESS_CLIENT_SECRET;
  }

  const res = await fetch(url, {
    ...options,
    headers: {
      ...headers,
      ...options?.headers,
    },
    ...(isServer ? { next: { revalidate: 60 } } : {}),
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

export async function getManualCashflows(
  limit = 50,
): Promise<ManualCashflowListResponse> {
  const q = new URLSearchParams({ limit: String(limit) });
  return apiFetch<ManualCashflowListResponse>(
    `/api/cashflows/manual?${q.toString()}`,
  );
}

// ---- Vault ----

export async function fetchVaultOverview(): Promise<VaultOverview> {
  return apiFetch<VaultOverview>("/api/vault/overview");
}

export async function fetchVaultSnapshots(limit = 30): Promise<VaultSnapshot[]> {
  return apiFetch<VaultSnapshot[]>(`/api/vault/snapshots?limit=${limit}`);
}

export async function fetchVaultCashflows(limit = 50): Promise<VaultCashflow[]> {
  return apiFetch<VaultCashflow[]>(`/api/vault/cashflows?limit=${limit}`);
}

export async function fetchVaultStrategyDetail(
  strategyId: string,
): Promise<StrategyDetail> {
  return apiFetch<StrategyDetail>(
    `/api/vault/strategies/${encodeURIComponent(strategyId)}`,
  );
}

export async function fetchVaultStrategySnapshots(
  strategyId: string,
  limit = 90,
): Promise<StrategySnapshot[]> {
  const q = new URLSearchParams({ limit: String(limit) });
  return apiFetch<StrategySnapshot[]>(
    `/api/vault/strategies/${encodeURIComponent(strategyId)}/snapshots?${q.toString()}`,
  );
}

// ---- Candidates ----

export async function getCandidates(): Promise<CandidatesResponse> {
  return apiFetch<CandidatesResponse>("/api/candidates");
}

export async function refreshCandidates(): Promise<{ ok: boolean; elapsed_s: number }> {
  return apiFetch<{ ok: boolean; elapsed_s: number }>("/api/candidates/refresh", {
    method: "POST",
  });
}
