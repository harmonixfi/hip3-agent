#!/bin/bash
# Setup crontab for Arbit Position Manager monitoring loop
# Run this script to install/update position manager crontab entries

set -e

# Script directory
SCRIPT_DIR="/mnt/data/agents/arbit"
cd "$SCRIPT_DIR" || exit 1

# Log directory
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

# Source environment helper
SOURCE_ENV="$SCRIPT_DIR/scripts/source_env.sh"

# Create temporary crontab file
TEMP_CRON=$(mktemp)

# Get existing crontab (if any)
crontab -l > "$TEMP_CRON" 2>/dev/null || true

# Detect legacy loris_30m cron line and warn (bonus feature)
if grep -q "loris_30m" "$TEMP_CRON" 2>/dev/null; then
    echo "⚠️  WARNING: Found legacy 'loris_30m' cron entry."
    echo "   This appears to be an old entry that may conflict with the new position manager setup."
    echo "   Please review and remove it manually if no longer needed."
    echo "   To edit crontab: crontab -e"
    echo ""
    # Show the legacy entry
    echo "Legacy entry found:"
    grep "loris_30m" "$TEMP_CRON"
    echo ""
fi

# Remove old PM entries (if any)
sed -i '/# Arbit position manager/,/# End Arbit position manager/d' "$TEMP_CRON"

# Add crontab entries
cat >> "$TEMP_CRON" << EOF

# Arbit position manager - Linux Crontab
# Updated: $(date +%Y-%m-%d)
# 5-minute cadence monitoring loop

# Pull position snapshots every 5 minutes
*/5 * * * * cd /mnt/data/agents/arbit && . scripts/source_env.sh && /usr/bin/python3 scripts/pull_positions_v3.py --db tracking/db/arbit_v3.db --venues paradex,ethereal,lighter,hyperliquid,hyena,okx >> logs/pull_positions_v3.log 2>&1

# Check alerts every 5 minutes (offset by 1 minute)
1-56/5 * * * * cd /mnt/data/agents/arbit && . scripts/source_env.sh && /usr/bin/python3 scripts/pm_alerts.py >> logs/pm_alerts.log 2>&1

# Send alerts to Discord only when alerts exist (offset by 2 minutes)
2-57/5 * * * * cd /mnt/data/agents/arbit && . scripts/source_env.sh && /bin/bash scripts/send_pm_alerts.sh >> logs/send_pm_alerts.log 2>&1

# System healthcheck (send only on issues) — every 15 minutes
4-59/15 * * * * cd /mnt/data/agents/arbit && . scripts/source_env.sh && /bin/bash scripts/send_pm_health.sh >> logs/pm_health.log 2>&1

# Realized funding/fees ledger ingest (hourly)
37 * * * * cd /mnt/data/agents/arbit && . scripts/source_env.sh && /usr/bin/python3 scripts/pm_cashflows.py ingest --venues paradex,ethereal,hyperliquid,lighter,okx >> logs/pm_cashflows_ingest.log 2>&1

# Daily cashflow rollup snapshot to logs
45 0 * * * cd /mnt/data/agents/arbit && . scripts/source_env.sh && /usr/bin/python3 scripts/pm_cashflows.py report >> logs/pm_cashflows_report.log 2>&1

# Daily funding report + portfolio review to Discord (09:05 and 21:05 local)
5 9 * * * cd /mnt/data/agents/arbit && . scripts/source_env.sh && /bin/bash scripts/send_daily_funding_with_portfolio.sh >> logs/daily_funding_portfolio.log 2>&1
5 21 * * * cd /mnt/data/agents/arbit && . scripts/source_env.sh && /bin/bash scripts/send_daily_funding_with_portfolio.sh >> logs/daily_funding_portfolio.log 2>&1

# Daily equity snapshot + report to Discord (09:10 local)
10 9 * * * cd /mnt/data/agents/arbit && . scripts/source_env.sh && /bin/bash scripts/send_equity_daily.sh >> logs/equity_daily.log 2>&1

# Daily DB backup (non-destructive)
50 2 * * * cd /mnt/data/agents/arbit && . scripts/source_env.sh && /usr/bin/python3 scripts/db_v3_backup.py --keep-days 14 >> logs/db_v3_backup.log 2>&1

# End Arbit position manager

EOF

# Install new crontab
echo "Installing position manager crontab entries..."
crontab "$TEMP_CRON"

# Clean up
rm "$TEMP_CRON"

# Show current PM crontab entries
echo ""
echo "Position manager crontab entries installed:"
crontab -l | grep -A 20 "# Arbit position manager" | head -n 20
echo ""
echo "✅ Position manager crontab installed successfully!"
echo ""
echo "Cron schedule:"
echo "  - Position pulls: Every 5 minutes (on the hour, :05, :10, etc.)"
echo "  - Alert checks: Every 5 minutes, offset by 1 minute (:01, :06, :11, etc.)"
echo ""
echo "To view logs:"
echo "  tail -f logs/pull_positions_v3.log"
echo "  tail -f logs/pm_alerts.log"
echo ""
echo "To check which environment variables are set:"
echo "  python3 scripts/check_env.py"
echo ""
echo "To edit crontab manually: crontab -e"
