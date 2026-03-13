#!/bin/bash
# Setup crontab for Arbit funding arbitrage system
# Run this script to install/update crontab entries

# Script directory
SCRIPT_DIR="/mnt/data/agents/arbit"
cd "$SCRIPT_DIR" || exit 1

# Python interpreter
PYTHON="python3"

# Log directory
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

# Source environment helper
SOURCE_ENV="$SCRIPT_DIR/scripts/source_env.sh"

# Create temporary crontab file
TEMP_CRON=$(mktemp)

# Get existing crontab (if any)
crontab -l > "$TEMP_CRON" 2>/dev/null || true

# Remove old Arbit entries (if any)
sed -i '/# Arbit funding arbitrage/,/# End Arbit funding arbitrage/d' "$TEMP_CRON"

# Add crontab entries
cat >> "$TEMP_CRON" << 'EOF'

# Arbit funding arbitrage - Linux Crontab
# Updated: 2026-02-09

# Hourly data pulls (all venues)
# Note: Each entry sources .arbit_env before running Python scripts
# Loris pull cadence decided: 30 minutes (see docs/DECISIONS.md).
# Keep Loris scheduling separate to avoid duplicates.
# (Do not add a Loris cron line here.)
5 * * * * cd /mnt/data/agents/arbit && . scripts/source_env.sh && /usr/bin/python3 scripts/pull_okx_v3.py >> logs/pull_okx_v3.log 2>&1
10 * * * * cd /mnt/data/agents/arbit && . scripts/source_env.sh && /usr/bin/python3 scripts/pull_paradex_v3.py --inst-limit 50 --funding-limit 50 >> logs/pull_paradex_v3.log 2>&1
15 * * * * cd /mnt/data/agents/arbit && . scripts/source_env.sh && /usr/bin/python3 scripts/pull_ethereal_v3.py --inst-limit 50 --funding-limit 50 >> logs/pull_ethereal_v3.log 2>&1
20 * * * * cd /mnt/data/agents/arbit && . scripts/source_env.sh && /usr/bin/python3 scripts/pull_hyperliquid_v3.py --inst-limit 50 --funding-limit 50 >> logs/pull_hyperliquid_v3.log 2>&1
25 * * * * cd /mnt/data/agents/arbit && . scripts/source_env.sh && /usr/bin/python3 scripts/pull_lighter_v3.py --inst-limit 50 --funding-limit 50 >> logs/pull_lighter_v3.log 2>&1

# Hourly screeners (run analytics and report opportunities)
30 * * * * cd /mnt/data/agents/arbit && . scripts/source_env.sh && /usr/bin/python3 scripts/run_screeners_v3.py >> logs/run_screeners_v3.log 2>&1

# End Arbit funding arbitrage

EOF

# Install new crontab
echo "Installing crontab entries..."
crontab "$TEMP_CRON"

# Clean up
rm "$TEMP_CRON"

# Show current crontab
echo ""
echo "Current crontab entries:"
crontab -l | grep -A 100 "Arbit funding arbitrage"
echo ""
echo "✅ Crontab installed successfully!"
echo ""
echo "Note: Each cron job sources .arbit_env before running Python scripts"
echo ""
echo "To view logs:"
# Loris is scheduled separately at 30m cadence (see docs/DECISIONS.md)
echo "  tail -f logs/pull_loris_funding_30m.log   # if enabled in your crontab"
echo "  tail -f logs/pull_okx_v3.log"
echo "  tail -f logs/pull_paradex_v3.log"
echo "  tail -f logs/pull_ethereal_v3.log"
echo "  tail -f logs/pull_hyperliquid_v3.log"
echo "  tail -f logs/pull_lighter_v3.log"
echo "  tail -f logs/run_screeners_v3.log"
echo ""
echo "To check which environment variables are set:"
echo "  python3 scripts/check_env.py"
echo ""
echo "To edit crontab manually: crontab -e"
