# Architecture Decision Records

This document captures architectural decisions made during the design and development of the OpenClaw delta-neutral funding arbitrage monitoring system.

---

## ADR-001: Bid/Ask Pricing for Unrealized PnL Instead of Mark Price

**Status:** Accepted
**Date:** 2026-03-29

### Context

The system needs to calculate unrealized PnL (uPnL) for delta-neutral positions consisting of a spot long leg and a perpetual short leg. A naive implementation would use mark price for both legs, which is the standard display convention on most exchanges.

### Decision

Use the current **bid** price when estimating exit value for the long (spot) leg, and the current **ask** price for the short (perp) leg.

- Spot long uPnL = `(current_bid - avg_entry_price) × size`
- Short perp uPnL = `-(current_ask - avg_entry_price) × size`

### Rationale

Mark price reflects a theoretical mid-market value, not the price actually executable at exit. In practice:

- Exiting a spot long means selling — the best available price is the bid.
- Covering a short perp means buying to close — the best available price is the ask.

Using bid/ask gives a conservative, realistic estimate of what the position would net if closed immediately. Mark price overstates realizable PnL by ignoring the bid/ask spread.

### Consequences / Trade-offs

- **Positive:** uPnL figures are consistently conservative and reflect executable economics. No surprise degradation at actual exit.
- **Positive:** Naturally accounts for spread widening in stress conditions, which is when accurate PnL estimates matter most.
- **Negative:** Displayed uPnL will always be slightly worse than mark-price-based dashboards. Users must understand this convention to avoid confusion when comparing against exchange UIs.
- **Negative:** Requires live order book data (L1 bid/ask) rather than just mark price, adding a small data dependency.

---

## ADR-002: Per-Leg Fill Tracking for Split-Leg Positions

**Status:** Accepted
**Date:** 2026-03-29

### Context

Some positions are split across multiple venues per asset. For example, a HYPE position might consist of: spot on Hyperliquid + perp on Hyena + perp on Hyperliquid native. Execution is performed sequentially per sub-pair (spot + perp on venue A, then spot + perp on venue B).

### Decision

Track fills and compute average entry price per individual leg, not aggregated across all perp legs. Each sub-pair (spot leg + its matched perp leg) is treated as an independent unit for fill accounting.

### Rationale

Sequential execution by sub-pair produces clean fill matching — each perp fill corresponds to the spot fill executed at approximately the same time and price level. Aggregating across all perp legs for a given asset would:

- Blend entries executed at different times and price levels.
- Lose exit timing information needed for accurate PnL attribution.
- Make it impossible to evaluate the carry quality of each sub-pair independently.

Per-leg tracking preserves the granularity that reflects actual trading behavior.

### Consequences / Trade-offs

- **Positive:** Accurate PnL attribution per sub-pair. Enables independent evaluation of each venue's execution quality.
- **Positive:** Clean mapping between fills and position legs. No heuristic matching required.
- **Negative:** More records in the fills table (N legs rather than 1 aggregated entry per side).
- **Negative:** UI must be designed to display sub-pair breakdowns clearly, or collapse them meaningfully, to avoid overwhelming the user.

---

## ADR-003: Cloudflare Tunnel for VPS Backend Exposure

**Status:** Accepted
**Date:** 2026-03-29

### Context

The frontend is deployed on Vercel (HTTPS). The Python backend runs on a VPS with no public TLS certificate. Browsers block mixed-content requests (HTTPS page calling HTTP endpoint). Options considered:

1. Caddy or nginx reverse proxy with Let's Encrypt on the VPS.
2. Vercel API routes as a proxy layer.
3. Cloudflare Tunnel (free tier).

### Decision

Use Cloudflare Tunnel to expose the VPS backend over HTTPS without opening inbound ports or managing TLS certificates.

### Rationale

- **Zero cost** on the free tier for the expected traffic volume.
- **No inbound port exposure** on the VPS — the tunnel is an outbound connection from VPS to Cloudflare edge.
- **Automatic HTTPS** via Cloudflare's edge certificates. No Let's Encrypt renewal management.
- **Setup time approximately 10 minutes** versus 30-60 minutes for a full nginx/Caddy configuration.
- Eliminates mixed-content browser blocking without additional code in the frontend or backend.

### Consequences / Trade-offs

- **Positive:** Significantly reduced operational overhead. No cert expiry incidents.
- **Positive:** Latency from Cloudflare edge to VPS is negligible for a monitoring dashboard (non-execution path).
- **Negative:** Introduces a dependency on Cloudflare availability. A Cloudflare outage makes the backend unreachable from the frontend.
- **Negative:** All traffic passes through Cloudflare infrastructure. Acceptable for monitoring data; would require re-evaluation if sensitive trade execution were routed through this path.
- **Mitigation:** The backend also remains directly reachable on the VPS for CLI tools and scripts, so monitoring continues even if the Cloudflare path is unavailable.

---

## ADR-004: Encrypted Secret Vault for Private Keys and Tokens

**Status:** Accepted
**Date:** 2026-03-29

### Context

Felix headless authentication requires a wallet private key at runtime. Currently, secrets are stored as plaintext values in `.env` files or environment variables. As the system grows to include multiple wallet keys and Felix Turnkey session keypairs, plaintext storage becomes an unacceptable security posture.

### Decision

Implement an encrypted vault for all sensitive material. No plaintext private keys or session keys in `.env` files or environment variables.

**Approach:** Use `age` encryption (modern, audited, simple CLI) or Python `cryptography` Fernet symmetric encryption. The master key is entered interactively at service startup or sourced from a hardware-backed key store.

**Scope of secrets managed by vault:**
- Wallet private keys (main and alt wallets)
- Felix Turnkey session keypairs
- Any future API secrets or signing keys

### Rationale

Private keys are irreversible if compromised. Plaintext env vars are trivially exposed via process listings, log scraping, or accidental commits. An encrypted vault:

- Ensures secrets are never stored or transmitted in cleartext.
- Provides a single, auditable location for all sensitive material.
- Requires explicit unlock at service startup, making accidental exposure much harder.

`age` is preferred over GPG for its simplicity and lack of legacy complexity. Fernet is acceptable if a pure-Python solution is required.

### Consequences / Trade-offs

- **Positive:** Significantly improved security posture. Private keys are protected at rest.
- **Positive:** Eliminates the class of "committed .env file" or "leaked process env" incidents.
- **Negative:** Adds a manual step at service startup (master key entry). Not fully automated for unattended restarts unless a hardware key source is configured.
- **Negative:** If the master key is lost, all vaulted secrets must be re-entered from cold backups. Key backup procedure must be documented and tested.
- **Mitigation:** Document key backup and recovery procedure. Consider storing master key in a password manager with hardware 2FA.

---

## ADR-005: Hourly Cron Interval for All Data Pipelines

**Status:** Accepted
**Date:** 2026-03-29

### Context

Multiple data pipelines need scheduled refresh: equity snapshots, fill history, funding cashflows, and price feeds. The refresh frequency must balance data freshness against API rate limit risk and operational complexity.

### Decision

All data pipelines run on a **1-hour interval**.

**Exception:** Felix JWT refresh runs on a **14-minute cycle** due to the 15-minute token TTL.

### Rationale

The system is a **monitoring** tool, not an execution engine. Sub-hourly data freshness provides no actionable value for a delta-neutral funding strategy with multi-day holding periods. Hourly intervals:

- Simplify scheduling (single cron cadence for most pipelines).
- Stay well within API rate limits across all data sources.
- Reduce operational noise — fewer pipeline runs means fewer potential failure points to monitor.

The Felix JWT exception is a hard technical constraint (not a design preference) and is handled separately.

### Consequences / Trade-offs

- **Positive:** Simple, predictable scheduling. Easy to reason about data staleness.
- **Positive:** Low API call volume minimizes rate limit risk.
- **Negative:** Data can be up to 59 minutes stale. Insufficient for latency-sensitive use cases (not applicable here).
- **Negative:** Funding rate anomalies or large price moves may not be visible in the dashboard immediately. Mitigated by the daily morning report and ad-hoc review triggers defined in the trading workflow.

---

## ADR-006: Next.js (Vercel) + FastAPI (VPS) Architecture

**Status:** Accepted
**Date:** 2026-03-29

### Context

A web dashboard is required for portfolio monitoring, accessible from any device. Options considered:

1. Full-stack Next.js with a database accessed directly (serverless functions on Vercel).
2. Separate frontend (Vercel) and backend (VPS) services.
3. Static site with client-side API calls.

### Decision

Deploy a **Next.js frontend on Vercel** paired with a **Python FastAPI backend on the existing VPS**.

### Rationale

- **Vercel** provides free HTTPS hosting, global CDN, and zero-config deployment for Next.js. No server to manage for the frontend.
- **FastAPI** is lightweight, async, and integrates naturally with the existing Python codebase (scripts, DB access, data pipelines). It avoids a polyglot backend.
- Keeping the backend on the VPS co-locates it with the SQLite database and existing scripts, minimizing latency for DB reads and avoiding data transfer costs.
- Vercel serverless functions cannot maintain a persistent SQLite connection or run long-lived background jobs — both requirements for this system.

### Consequences / Trade-offs

- **Positive:** Frontend and backend can be developed, deployed, and scaled independently.
- **Positive:** FastAPI's async support handles concurrent dashboard requests efficiently.
- **Positive:** Next.js React Server Components and incremental static regeneration options available for future optimization.
- **Negative:** Two separate deployment targets to manage (Vercel + VPS).
- **Negative:** Requires Cloudflare Tunnel (see ADR-003) to bridge Vercel HTTPS and VPS HTTP.
- **Negative:** SQLite on a single VPS is a single point of failure. Acceptable for current scale; revisit if multi-user or high-availability requirements emerge.

---

## ADR-007: Spot Fill Symbol Mapping via spotMeta Cache

**Status:** Accepted
**Date:** 2026-03-29

### Context

Hyperliquid spot fill API responses return the coin field as a numeric index reference (e.g., `@107`) rather than a human-readable symbol (e.g., `HYPE`). The system needs readable symbols for display, storage, and matching against position records.

### Decision

Call the `spotMeta` API endpoint at service startup and once daily to build an index-to-symbol mapping. Cache this mapping locally (in-memory and/or persisted to DB).

### Rationale

- The `spotMeta` index-to-symbol mapping is **static** for any given coin — indices are assigned once and do not change.
- A single `spotMeta` call returns the full universe of spot tokens, providing complete coverage in one API call.
- Per-fill reverse lookups would multiply API calls proportionally with fill volume and introduce unnecessary latency.
- Daily refresh catches any newly listed tokens without requiring a service restart.

### Consequences / Trade-offs

- **Positive:** Single API call provides complete mapping. No per-fill API overhead.
- **Positive:** Locally cached mapping means symbol resolution is instant and offline-capable.
- **Negative:** If a new token is listed mid-day, fills for that token will show as unresolved until the next daily refresh. Mitigated by the startup refresh and by the low frequency of new listings.
- **Negative:** Cache must be invalidated and rebuilt on service restart. Startup time increases marginally.

---

## ADR-008: Entry/Exit Spread Definition for Basis Trade Monitoring

**Status:** Accepted
**Date:** 2026-03-29

### Context

Delta-neutral funding positions involve a basis component: the spread between spot and perp prices. Tracking this spread over the position lifetime allows the system to identify optimal exit timing (when spread has converged or inverted relative to entry).

A consistent, precise definition of "spread" is required to avoid ambiguity across display, alerts, and trade logic.

### Decision

Define spreads as follows:

- **Entry spread** = `(spot_avg_entry / perp_avg_entry) - 1` expressed as a percentage.
- **Exit spread** = `(spot_best_bid / perp_best_ask) - 1` expressed as a percentage.
- **Favorable exit condition:** `exit_spread > entry_spread` (spread has widened in favor of the long spot / short perp position).

### Rationale

This definition:

- Directly measures the cost/gain of the basis at entry versus the cost/gain at the potential exit.
- Uses bid/ask prices for the exit spread (consistent with ADR-001) to produce a conservative, executable estimate rather than a theoretical mid-price figure.
- Is directionally intuitive: a positive spread means spot is trading at a premium to perp, which benefits the long-spot/short-perp holder at exit.

### Consequences / Trade-offs

- **Positive:** Unambiguous, formula-based definition prevents inconsistency between display and decision logic.
- **Positive:** Conservative (bid/ask) exit spread prevents premature "favorable exit" signals.
- **Negative:** Spread figures will differ from exchange-displayed basis (which typically uses mark or last price). Users must understand the convention.
- **Negative:** Requires live L1 order book data for exit spread computation (same dependency as ADR-001).

---

## ADR-009: PERP_PERP Position Type — Schema Now, Implement Phase 2

**Status:** Accepted
**Date:** 2026-03-29

### Context

The initial system focuses on SPOT_PERP positions (spot long + perp short). The user plans to open PERP_PERP positions (perp long on one venue + perp short on another) in the near term. PERP_PERP adds complexity: both legs carry funding, uPnL calculation differs from SPOT_PERP, and spread definitions change.

Deferring schema design until implementation would require a migration later.

### Decision

Include `PERP_PERP` as a valid position type in the data schema and data models from day one. Implementation of fill tracking, uPnL calculation, and UI rendering for PERP_PERP follows after SPOT_PERP is complete and validated.

### Rationale

- Schema changes require data migrations, which are disruptive and error-prone on a live system.
- Adding a `position_type` enum field with `SPOT_PERP | PERP_PERP` costs near-zero design effort now.
- The computational complexity of PERP_PERP (dual funding, cross-venue basis) lives in the application layer, not the data model. The data model is identical in structure.
- Pre-including the type avoids a hard cutover where historical SPOT_PERP records must be relabeled.

### Consequences / Trade-offs

- **Positive:** No schema migration required when PERP_PERP implementation begins.
- **Positive:** Forces early clarity on what distinguishes PERP_PERP from SPOT_PERP at the data level.
- **Negative:** `PERP_PERP` code paths will exist in the schema but be unimplemented in Phase 1. Requires discipline to ensure Phase 1 code does not accidentally process PERP_PERP records.
- **Mitigation:** All PERP_PERP computation paths return `NotImplementedError` or are gated behind a feature flag until Phase 2 is complete.

---

## ADR-010: Manual Deposit/Withdraw Entry via REST API

**Status:** Accepted
**Date:** 2026-03-29

### Context

Cashflow-adjusted APR calculation requires accurate knowledge of capital deposits and withdrawals per wallet. Options considered:

1. Auto-detection from on-chain transaction history.
2. Manual entry via REST API endpoint.

### Decision

Expose a `POST /cashflow` (or equivalent) REST endpoint for manual entry of deposit and withdrawal events. The Claude agent or user calls this endpoint directly when a transfer occurs.

### Rationale

Auto-detection of deposits and withdrawals from on-chain data is:

- **Complex:** Multiple wallets, multiple bridges, internal transfers, and rebasing tokens all create edge cases.
- **Fragile:** On-chain indexers can lag, miss events, or misclassify transactions.
- **Over-engineered** for the current use case: deposits and withdrawals are low-frequency, deliberate events that the user is always aware of.

Manual entry is simple, accurate, and places no trust in third-party indexers. The overhead of one API call per transfer event is negligible.

### Consequences / Trade-offs

- **Positive:** Zero implementation complexity for data collection. Deterministically accurate.
- **Positive:** No dependency on on-chain indexers or third-party APIs for cashflow data.
- **Negative:** Relies on the user or agent to record every transfer. A missed entry silently corrupts APR calculations.
- **Mitigation:** The morning report (see ADR-005 cadence) should include a prompt or check to confirm no unrecorded transfers occurred. Consider a simple reconciliation alert if wallet balance changes by more than a threshold between snapshots.

---

## ADR-011: Backfill Closed Positions at Initial Setup

**Status:** Accepted
**Date:** 2026-03-29

### Context

Seven positions were closed within days before the monitoring system was set up. Fill history for these positions is still available via the Hyperliquid API, but API history is time-limited. If backfill is deferred, this data will be permanently lost.

### Decision

Backfill all closed position fills during initial system setup, before the fill history window expires.

### Rationale

- Complete trade history enables full performance analysis from system inception: realized PnL, holding periods, funding earned, and basis at entry/exit for all historical positions.
- The data exists now and is retrievable with known effort. Deferring risks permanent loss.
- Backfill logic is also required for the production system (handling restarts, gaps, new position onboarding), so the implementation effort is not wasted.
- Historical data is the foundation for evaluating strategy performance over time. Gaps in early history permanently degrade this analysis.

### Consequences / Trade-offs

- **Positive:** Complete audit trail from the start of live trading. No gaps in performance reporting.
- **Positive:** Validates the fill ingestion pipeline against known historical data before applying it to live positions.
- **Negative:** Requires additional upfront engineering effort for the backfill script.
- **Negative:** Closed position fills may have edge cases (partial fills, venue-specific quirks) that require additional handling.
- **Mitigation:** Prioritize backfill as an early milestone task. Run immediately after fill ingestion pipeline is functional, before the API history window closes.
