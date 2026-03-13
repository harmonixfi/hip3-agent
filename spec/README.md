# Harmonix Spec Index

This folder is the working specification for the Harmonix delta-neutral workspace.
It describes the intended behavior of the current runtime, not the legacy Arbit docs.

Use these files as the baseline before changing code:

- `report-scripts.md`
  Report outputs, CLI contracts, section order, advisory semantics, and rotation analysis.
- `pull-data-pipeline.md`
  Raw data pull, historical backfill, private ledger ingest, position sync, and daily run order.
- `data-structures.md`
  Registry JSON, CSV contracts, DB schema contracts, and key normalization rules.
- `test-contracts.md`
  The minimum regression checks that should pass after a fix.

Current project scope:

- Strategy: `SPOT_PERP`
- Venue family: Hyperliquid base dex plus HIP3 deployers
- Agent mode: advisory only
- Candidate report scope: base `hyperliquid` ranking unless explicitly widened later
- Portfolio carry/advisory scope: must understand namespaced Hyperliquid perps such as `xyz:GOLD`, `flx:*`, `km:*`, `hyna:*`

Key invariants:

- Registry `qty` is in base units, not USD.
- Position-level `amount_usd` is manual gross capital/notional used for report economics.
- `pm_cashflows.amount` uses PnL sign:
  positive = credit received
  negative = debit paid
- Loris exchange resolution for Hyperliquid namespaced perps is:
  - `"" -> hyperliquid`
  - `xyz -> tradexyz`
  - `flx -> felix`
  - `km -> kinetiq`
  - `hyna -> hyena`
