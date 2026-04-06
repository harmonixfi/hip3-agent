# Dashboard Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shared-password gate to the OpenClaw dashboard using Next.js middleware and a Server Action — no auth libraries, no database.

**Architecture:** Middleware runs on every request and checks for a valid `auth_session` httpOnly cookie. If missing, the user is redirected to `/login`. The login page submits to a Server Action that validates the password against the `DASHBOARD_PASSWORD` env var using `crypto.timingSafeEqual`, then sets the cookie and redirects home.

**Tech Stack:** Next.js 14 (App Router), Server Actions, Node.js `crypto` (built-in), `cookies()` from `next/headers`

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `frontend/middleware.ts` | Block unauthenticated requests, exempt public paths |
| Create | `frontend/app/login/page.tsx` | Login UI — dark-themed password form |
| Create | `frontend/app/login/actions.ts` | Server Action — validate password, set cookie |
| Modify | `frontend/.env.local` | Add `DASHBOARD_PASSWORD` env var |

---

### Task 1: Add `DASHBOARD_PASSWORD` to env

**Files:**
- Modify: `frontend/.env.local`

- [ ] **Step 1: Add env var**

Open `frontend/.env.local` and append:

```
DASHBOARD_PASSWORD=changeme
```

> Note: Change `changeme` to your real password. Also add this to Vercel project environment variables (Settings → Environment Variables).

- [ ] **Step 2: Commit**

```bash
cd frontend
git add .env.local
git commit -m "chore: add DASHBOARD_PASSWORD env var"
```

> If `.env.local` is gitignored (it should be), skip staging it. Just note that it must be set in Vercel.

---

### Task 2: Server Action — validate password and set cookie

**Files:**
- Create: `frontend/app/login/actions.ts`

- [ ] **Step 1: Create the file**

```ts
"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { createHmac, timingSafeEqual } from "crypto";

function makeSessionToken(password: string): string {
  return createHmac("sha256", password).update(password).digest("hex");
}

export async function login(formData: FormData): Promise<{ error: string }> {
  const submitted = formData.get("password") as string;
  const expected = process.env.DASHBOARD_PASSWORD;

  if (!expected) {
    return { error: "Server misconfiguration: DASHBOARD_PASSWORD not set." };
  }

  const submittedBuf = Buffer.from(submitted ?? "");
  const expectedBuf = Buffer.from(expected);

  // Pad to same length before timingSafeEqual (it requires equal lengths)
  const maxLen = Math.max(submittedBuf.length, expectedBuf.length);
  const a = Buffer.concat([submittedBuf, Buffer.alloc(maxLen - submittedBuf.length)]);
  const b = Buffer.concat([expectedBuf, Buffer.alloc(maxLen - expectedBuf.length)]);

  const match = timingSafeEqual(a, b) && submittedBuf.length === expectedBuf.length;

  if (!match) {
    return { error: "Incorrect password." };
  }

  const token = makeSessionToken(expected);
  const cookieStore = await cookies();
  cookieStore.set("auth_session", token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 30, // 30 days
    path: "/",
  });

  redirect("/");
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/login/actions.ts
git commit -m "feat: add login server action"
```

---

### Task 3: Login page UI

**Files:**
- Create: `frontend/app/login/page.tsx`

- [ ] **Step 1: Create the file**

```tsx
"use client";

import { useActionState } from "react";
import { login } from "./actions";

const initialState = { error: "" };

export default function LoginPage() {
  const [state, formAction, pending] = useActionState(login, initialState);

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="card space-y-6">
          <div>
            <h1 className="text-xl font-bold text-white">OpenClaw Dashboard</h1>
            <p className="text-sm text-gray-400 mt-1">Enter password to continue</p>
          </div>

          <form action={formAction} className="space-y-4">
            <div>
              <input
                type="password"
                name="password"
                placeholder="Password"
                required
                autoFocus
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-gray-500"
              />
            </div>

            {state?.error && (
              <p className="text-red-400 text-sm">{state.error}</p>
            )}

            <button
              type="submit"
              disabled={pending}
              className="w-full bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-white text-sm font-medium py-2 px-4 rounded transition-colors"
            >
              {pending ? "Checking..." : "Enter"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/login/page.tsx
git commit -m "feat: add login page UI"
```

---

### Task 4: Middleware — protect all routes

**Files:**
- Create: `frontend/middleware.ts`

- [ ] **Step 1: Create the file**

```ts
import { NextRequest, NextResponse } from "next/server";
import { createHmac } from "crypto";

function makeSessionToken(password: string): string {
  return createHmac("sha256", password).update(password).digest("hex");
}

export function middleware(request: NextRequest) {
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

  const expectedToken = makeSessionToken(password);
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/middleware.ts
git commit -m "feat: add auth middleware to protect dashboard routes"
```

---

### Task 5: Manual verification

- [ ] **Step 1: Start the dev server**

```bash
cd frontend
source ../.arbit_env
npm run dev
```

- [ ] **Step 2: Verify redirect**

Open `http://localhost:3000` in a browser. You should be redirected to `http://localhost:3000/login`.

- [ ] **Step 3: Test wrong password**

Enter any wrong password. You should see "Incorrect password." and stay on `/login`.

- [ ] **Step 4: Test correct password**

Enter the value you set for `DASHBOARD_PASSWORD`. You should be redirected to `/` and see the dashboard.

- [ ] **Step 5: Test persistence**

Refresh the page. You should remain on the dashboard (cookie persists).

- [ ] **Step 6: Test cookie invalidation (optional)**

In DevTools → Application → Cookies, delete the `auth_session` cookie. Refresh — you should be redirected back to `/login`.

- [ ] **Step 7: Final commit**

```bash
git add .
git commit -m "feat: dashboard password protection complete"
```

---

## Deployment Checklist

- [ ] Add `DASHBOARD_PASSWORD` to Vercel project → Settings → Environment Variables
- [ ] Redeploy on Vercel (or it redeploys automatically on push)
- [ ] Verify production URL redirects to `/login` before cookie is set
