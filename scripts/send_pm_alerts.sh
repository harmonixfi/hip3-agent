#!/bin/bash
# Send Position Manager alerts to Discord via Clawdbot
# This script runs pm_alerts_compose.py and sends the message only if alerts exist
# Edit the CHANNEL_ID below to match your target Discord channel

set -e

# Project root
cd "$(dirname "$0")/.."

# Source environment variables
source scripts/source_env.sh

# Discord channel to send alerts to (replace with your channel ID)
CHANNEL_ID="${PM_ALERTS_DISCORD_CHANNEL:-}"

if [ -z "$CHANNEL_ID" ]; then
    echo "Error: PM_ALERTS_DISCORD_CHANNEL environment variable not set" >&2
    echo "Please set PM_ALERTS_DISCORD_CHANNEL in .arbit_env" >&2
    exit 1
fi

# Compose alert message (empty if no alerts)
MESSAGE=$(python3 scripts/pm_alerts_compose.py)

# Send only if non-empty
if [ -n "$MESSAGE" ]; then
    # Send via Clawdbot (deterministic; no LLM)
    CLAWDBOT_BIN="${CLAWDBOT_BIN:-/home/bean/.npm-global/bin/clawdbot}"
    if [ ! -x "$CLAWDBOT_BIN" ]; then
        echo "Error: clawdbot binary not found at $CLAWDBOT_BIN" >&2
        exit 1
    fi

    EXTRA_ARGS=()
    if [ "${PM_ALERTS_DRY_RUN:-}" = "1" ]; then
        EXTRA_ARGS+=(--dry-run)
    fi

    "$CLAWDBOT_BIN" message send --channel discord --target "$CHANNEL_ID" --message "$MESSAGE" "${EXTRA_ARGS[@]}"
else
    # No alerts - silent exit (this is normal)
    exit 0
fi
