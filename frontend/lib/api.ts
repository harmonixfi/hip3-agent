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
const CF_ACCESS_CLIENT_ID = process.env.CF_ACCESS_CLIENT_ID;
const CF_ACCESS_CLIENT_SECRET = process.env.CF_ACCESS_CLIENT_SECRET;

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
