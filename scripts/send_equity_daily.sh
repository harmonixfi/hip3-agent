#!/bin/bash
# Send daily equity report to Discord via Clawdbot

set -e
cd "$(dirname "$0")/.."

source scripts/source_env.sh

CHANNEL_ID="${EQUITY_REPORT_DISCORD_CHANNEL:-${PM_ALERTS_DISCORD_CHANNEL:-}}"
if [ -z "$CHANNEL_ID" ]; then
  echo "Error: set EQUITY_REPORT_DISCORD_CHANNEL (or fallback PM_ALERTS_DISCORD_CHANNEL)" >&2
  exit 1
fi

# Snapshot then report
python3 scripts/equity_daily.py snapshot >/dev/null
MESSAGE=$(python3 scripts/equity_daily.py report --days 7)

CLAWDBOT_BIN="${CLAWDBOT_BIN:-/home/bean/.npm-global/bin/clawdbot}"
"$CLAWDBOT_BIN" message send --channel discord --target "$CHANNEL_ID" --message "$MESSAGE"
