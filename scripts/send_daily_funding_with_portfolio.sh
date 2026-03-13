#!/bin/bash
# Send daily funding report + portfolio review to Discord via Clawdbot

set -e
cd "$(dirname "$0")/.."

source scripts/source_env.sh

CHANNEL_ID="${PM_ALERTS_DISCORD_CHANNEL:-}"
if [ -z "$CHANNEL_ID" ]; then
  echo "Error: PM_ALERTS_DISCORD_CHANNEL not set" >&2
  exit 1
fi

# Keep it deterministic: pull loris first, refresh equity snapshot, ingest cashflows
python3 scripts/pull_loris_funding.py >/dev/null || true
python3 scripts/equity_daily.py snapshot >/dev/null || true
python3 scripts/pm_cashflows.py ingest --venues paradex,hyperliquid,hyena,ethereal,lighter,okx --since-hours 24 >/dev/null || true
python3 scripts/pull_positions_v3.py --db tracking/db/arbit_v3.db --venues paradex,hyperliquid,lighter,ethereal,hyena,okx -q >/dev/null || true

MESSAGE=$(python3 scripts/report_daily_funding_with_portfolio.py --top 5 --since-hours 24 --mode brief)

CLAWDBOT_BIN="${CLAWDBOT_BIN:-/home/bean/.npm-global/bin/clawdbot}"
"$CLAWDBOT_BIN" message send --channel discord --target "$CHANNEL_ID" --message "$MESSAGE"
