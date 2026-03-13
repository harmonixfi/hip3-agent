# T-010 — Cron jobs for public data collection

## Goal
Schedule hourly pulls of public market data to build continuous time-series.

## Status
✅ **COMPLETED** — 5 cron jobs created and enabled (2026-02-07)

## Created Cron Jobs

### 1. OKX Market Pull (hourly)
- **Job ID:** `92dc0e40-2394-41bb-a477-7da8e239c8b5`
- **Schedule:** `0 * * * *` (Asia/Ho_Chi_Minh timezone)
- **Command:** `Run scripts/pull_okx_market.py`
- **Agent:** arbit (isolated session)
- **Delivery:** Discord #funding-arbit (1469013456274460725) on any output
- **Next Run:** See `clawdbot cron list`

### 2. Hyperliquid Market Pull (hourly)
- **Job ID:** `b1789355-d96c-40be-a137-9f558254f8a7`
- **Schedule:** `5 * * * *` (Asia/Ho_Chi_Minh timezone)
- **Command:** `Run scripts/pull_hyperliquid_market.py`
- **Agent:** arbit (isolated session)
- **Delivery:** Discord #funding-arbit (1469013456274460725) on any output
- **Next Run:** See `clawdbot cron list`

### 3. Paradex Market Pull (hourly)
- **Job ID:** `578265fb-f85e-42f8-b82f-fd05da1f139d`
- **Schedule:** `10 * * * *` (Asia/Ho_Chi_Minh timezone)
- **Command:** `Run scripts/pull_paradex_market.py`
- **Agent:** arbit (isolated session)
- **Delivery:** Discord #funding-arbit (1469013456274460725) on any output
- **Next Run:** See `clawdbot cron list`

### 4. Lighter Market Pull (hourly)
- **Job ID:** `ce701fcf-4964-4f32-a146-0a7429eb58f3`
- **Schedule:** `15 * * * *` (Asia/Ho_Chi_Minh timezone)
- **Command:** `Run scripts/pull_lighter_market.py`
- **Agent:** arbit (isolated session)
- **Delivery:** Discord #funding-arbit (1469013456274460725) on any output
- **Next Run:** See `clawdbot cron list`

### 5. Ethereal Market Pull (hourly)
- **Job ID:** `6cbd208b-5533-4baa-b994-3e765a80bd3d`
- **Schedule:** `20 * * * *` (Asia/Ho_Chi_Minh timezone)
- **Command:** `Run scripts/pull_ethereal_market.py`
- **Agent:** arbit (isolated session)
- **Delivery:** Discord #funding-arbit (1469013456274460725) on any output
- **Next Run:** See `clawdbot cron list`

## Verification

### Check job status
```bash
clawdbot cron list
```

### Check run history
```bash
# For a specific job
clawdbot cron runs --id <job-id> --limit 10

# For all arbit jobs
clawdbot cron runs | grep arbit
```

### Verify scripts exist
```bash
ls -la scripts/pull_*.py
```

## Schedule Notes

- All jobs run hourly with **5-minute staggering** to avoid API burst
- Timezone: Asia/Ho_Chi_Minh (GMT+7)
- OKX runs at XX:00, Hyperliquid at XX:05, Paradex at XX:10, Lighter at XX:15, Ethereal at XX:20

## Alerting Configuration

- **Current Behavior:** All jobs deliver output to Discord #funding-arbit (channel ID: 1469013456274460725)
- **Desired Behavior (Future):** Send alerts on failure only, stay silent on success
- **Implementation Note:** Currently using `--deliver` flag which sends all output. To implement failure-only alerts, scripts should be modified to return exit codes and cron jobs configured accordingly

## Optional Scripts (Not Scheduled)

The following optional analytics scripts do **not exist** and were not scheduled:
- `scripts/compute_basis.py` — NOT FOUND
- `scripts/opportunity_report_public.py` — NOT FOUND

If these scripts are created in the future, they should be scheduled after the last market pull (Ethereal at XX:20), e.g.:
- Compute basis: `25 * * * *` (Asia/Ho_Chi_Minh)
- Opportunity report: `30 * * * *` (Asia/Ho_Chi_Minh)

## Conflicts / Caveats

1. **Existing Loris Funding Pull:** There is an existing cron job (`c61aea88-9563-48ab-bab4-78c5f7622eea`) that runs at `0 * * * *` (same time as OKX). This is intentional and not a conflict.

2. **Delivery Behavior:** Jobs currently deliver all output, not just failures. This may generate noise in Discord. Consider modifying scripts to only output on error, or adjusting cron job configuration.

3. **Script Execution Mode:** Jobs use `--session isolated` which runs in an isolated arbit session. This is correct for background tasks.

## Deliverables
- ✅ 5 Gateway cron jobs created and enabled
- ✅ Job IDs and schedules documented
- ✅ Verification commands provided
- ✅ Caveats documented

## Acceptance
- ✅ All public data scripts run hourly automatically (5 venues)
- ⏸️ Basis + opp reports: Scripts do not exist, scheduled when available

## Docs
- docs/CONNECTORS.md
- docs/CONVENTIONS.md
- docs/RUNBOOK.md
- docs/DESIGN_v3.md

