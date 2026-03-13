# Tracking System (Arbit)

Goal: track Bean’s portfolio across venues + build a funding-arb screener with *history-based stability checks* (e.g., 14D avg APR).

## Data sources
- Live funding + OI ranks: https://api.loris.tools/funding
  - Funding values are scaled by 10,000.
  - Loris normalizes 1h exchanges to 8h-equivalent by multiplying by 8.

## Files
- `data/portfolio_snapshots.csv` — manual portfolio equity snapshots
- `data/loris_funding_history.csv` — time-series funding samples (we build our own history by sampling)
- `config/strategy.json` — strategy thresholds (OI rank, APR threshold, window)
- `config/fees.json` — maker/taker fee assumptions (fill in as we confirm each venue)

## Scripts
- `scripts/pull_loris_funding.py`
  - pulls https://api.loris.tools/funding
  - filters to OI rank <= threshold and target venues
  - appends to `data/loris_funding_history.csv`

- `scripts/report_funding_opps.py`
  - reads last N days from history
  - computes 14D avg APR per exchange+symbol
  - computes best cross-exchange perp-perp funding spread per symbol
  - prints a ranked list + suggested hedge direction

## How to run (manual)
```bash
python3 scripts/pull_loris_funding.py
python3 scripts/report_funding_opps.py --days 14 --min-apr 20
```

## Next step
Once Bean confirms, schedule `pull_loris_funding.py` every 60 minutes (or 30 minutes) so we can compute 14D stability from *our own collected history*.
