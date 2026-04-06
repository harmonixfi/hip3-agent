import { NextRequest, NextResponse } from "next/server";
import { makeSessionToken } from "@/lib/session-token";

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Public paths — never gate these
  if (
    pathname.startsWith("/login") ||
    pathname.startsWith("/_next") ||
    pathname === "/favicon.ico"
  ) {
    return NextResponse.next();
  }

  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) {
    // Misconfigured — let through so the server action error surfaces
    return NextResponse.next();
  }

  const expectedToken = await makeSessionToken(password);
  const sessionCookie = request.cookies.get("auth_session")?.value;

  if (sessionCookie !== expectedToken) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
