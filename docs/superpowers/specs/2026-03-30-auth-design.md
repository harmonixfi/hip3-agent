# Auth Design: Dashboard Password Protection

**Date:** 2026-03-30
**Status:** Approved

## Summary

Add a shared-password gate to the OpenClaw dashboard frontend. All routes require a valid session cookie. Users enter a single shared password on a `/login` page. No user management, no database, no auth library.

## Architecture

Three new files inside `frontend/`:

| File | Purpose |
|------|---------|
| `middleware.ts` | Edge middleware — checks session cookie on every request, redirects to `/login` if missing/invalid |
| `app/login/page.tsx` | Login page — dark-themed form with password field |
| `app/login/actions.ts` | Server Action — validates password, sets cookie, redirects |

## Data Flow

```
Browser → middleware.ts
  → has valid cookie? → pass through to app
  → no cookie?        → redirect to /login

/login form submit → Server Action (actions.ts)
  → compare password via crypto.timingSafeEqual
  → wrong? → return error message to form
  → correct? → set httpOnly cookie (30-day expiry) → redirect to /
```

## Session Cookie

- Name: `auth_session`
- Value: `HMAC-SHA256(DASHBOARD_PASSWORD, DASHBOARD_PASSWORD)` — a fixed token derived from the password
- httpOnly: true (not accessible to JS)
- Expiry: 30 days
- Rotating `DASHBOARD_PASSWORD` invalidates all existing sessions instantly

## Public Routes (exempt from middleware)

- `/login`
- `/_next/*` (static assets)
- `/favicon.ico`

## Environment Variable

Add to `.env.local` (and Vercel project settings):

```
DASHBOARD_PASSWORD=your-shared-password-here
```

No other dependencies. Uses Node.js built-in `crypto` and Next.js built-in cookies API.

## UI

The `/login` page uses the existing dark theme (same background, same card style). Contains:
- Title: "OpenClaw Dashboard"
- Single password input field
- Submit button
- Inline error message on wrong password

No username field, no "remember me" toggle, no "forgot password" flow.

## Out of Scope

- Per-user accounts or audit trails
- JWT or session storage
- Auth libraries (NextAuth, Clerk, etc.)
- Logout route (can be added later if needed)
