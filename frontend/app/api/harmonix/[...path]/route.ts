import { NextRequest, NextResponse } from "next/server";

/**
 * Proxies browser-safe requests to the Harmonix FastAPI.
 * Client components call `/api/harmonix/...` (same origin); this handler adds
 * `API_BASE_URL` and `X-API-Key` from server env — no NEXT_PUBLIC_* needed.
 */

export const dynamic = "force-dynamic";

const CF_ACCESS_CLIENT_ID = process.env.CF_ACCESS_CLIENT_ID;
const CF_ACCESS_CLIENT_SECRET = process.env.CF_ACCESS_CLIENT_SECRET;

type RouteCtx = { params: { path: string[] } };

export async function GET(request: NextRequest, ctx: RouteCtx) {
  return proxy(request, "GET", ctx);
}

export async function POST(request: NextRequest, ctx: RouteCtx) {
  return proxy(request, "POST", ctx);
}

async function proxy(request: NextRequest, method: string, ctx: RouteCtx) {
  const apiBase = process.env.API_BASE_URL?.replace(/\/$/, "");
  const apiKey = process.env.API_KEY;
  if (!apiBase) {
    return NextResponse.json(
      { detail: "API_BASE_URL not configured on Next server" },
      { status: 500 },
    );
  }

  const segments = ctx.params.path ?? [];
  const rest = segments.join("/");
  const backendUrl = `${apiBase}/api/${rest}${request.nextUrl.search}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  if (CF_ACCESS_CLIENT_ID && CF_ACCESS_CLIENT_SECRET) {
    headers["CF-Access-Client-Id"] = CF_ACCESS_CLIENT_ID;
    headers["CF-Access-Client-Secret"] = CF_ACCESS_CLIENT_SECRET;
  }

  const init: RequestInit = { method, headers };
  if (method === "POST") {
    init.body = await request.text();
  }

  const res = await fetch(backendUrl, init);
  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: {
      "Content-Type": res.headers.get("Content-Type") ?? "application/json",
    },
  });
}
