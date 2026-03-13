#!/bin/bash
# Source .arbit_env safely if it exists
# This script should be sourced before running any Python scripts

# Prefer CWD-based lookup (works in cron's /bin/sh too)
# Cron entries `cd /mnt/data/agents/arbit` before sourcing this file.
ENV_FILE="$(pwd)/.arbit_env"

# Fallback: resolve relative to this file when running in bash
if [ ! -f "$ENV_FILE" ] && [ -n "${BASH_SOURCE[0]:-}" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  ENV_FILE="$SCRIPT_DIR/.arbit_env"
fi

# Source environment file if it exists
if [ -f "$ENV_FILE" ]; then
  set -a  # Automatically export all variables
  . "$ENV_FILE"
  set +a
else
  echo "Warning: $ENV_FILE not found. Some scripts may fail without environment variables." >&2
fi
