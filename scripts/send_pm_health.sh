#!/bin/bash
# Send healthcheck only when issues exist

set -e
cd "$(dirname "$0")/.."

source scripts/source_env.sh

CHANNEL_ID="${PM_HEALTH_DISCORD_CHANNEL:-${PM_ALERTS_DISCORD_CHANNEL:-}}"
if [ -z "$CHANNEL_ID" ]; then
  echo "Error: PM_HEALTH_DISCORD_CHANNEL not set (or fallback PM_ALERTS_DISCORD_CHANNEL missing)" >&2
  exit 1
fi

MESSAGE=$(python3 scripts/pm_healthcheck.py)

if [ -n "$MESSAGE" ]; then
  CLAWDBOT_BIN="${CLAWDBOT_BIN:-/home/bean/.npm-global/bin/clawdbot}"
  EXTRA_ARGS=()
  if [ "${PM_HEALTH_DRY_RUN:-}" = "1" ]; then
    EXTRA_ARGS+=(--dry-run)
  fi
  "$CLAWDBOT_BIN" message send --channel discord --target "$CHANNEL_ID" --message "$MESSAGE" "${EXTRA_ARGS[@]}"
fi
