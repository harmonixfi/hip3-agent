#!/bin/bash
set -e

# Source environment variables and export them for cron
if [ -f /app/.arbit_env ]; then
    set -a
    source /app/.arbit_env
    set +a
fi

# Write env vars to a file that cron can source
env | grep -v "^_=" > /etc/environment

# Start cron daemon in background
cron

# Start FastAPI server
exec uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1
