#!/usr/bin/env python3
"""Compose a single Discord message from Position Manager alerts.

Runs pm_alerts.py --json and outputs a formatted Discord message if alerts exist.
Prints nothing (empty output) if no alerts.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path for imports
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.position_manager.alerts import format_alerts_for_discord, Alert


def run_pm_alerts_json() -> Dict[str, Any]:
    """Run pm_alerts.py --json and return parsed output."""
    pm_alerts_path = ROOT / "scripts" / "pm_alerts.py"

    result = subprocess.run(
        ["python3", str(pm_alerts_path), "--json"],
        capture_output=True,
        text=True,
        check=False
    )

    if result.returncode != 0:
        print(f"Error running pm_alerts.py: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    return json.loads(result.stdout)


def dict_to_alert(alert_dict: Dict[str, Any]) -> Alert:
    """Convert alert dict back to Alert object for formatting."""
    return Alert(
        severity=alert_dict["severity"],
        position_id=alert_dict["position_id"],
        message=alert_dict["message"],
        dedup_key=alert_dict["dedup_key"],
        recommended_action=alert_dict.get("recommended_action"),
        timestamp_ms=alert_dict.get("timestamp_ms"),
        metadata=alert_dict.get("metadata")
    )


def main():
    # Run pm_alerts.py and get JSON output
    data = run_pm_alerts_json()

    # Check if there are any filtered alerts
    filtered_count = data.get("filtered_alerts", 0)

    if filtered_count == 0:
        # No alerts - print nothing (empty output)
        sys.exit(0)

    # Alerts exist - compose Discord message
    alert_dicts = data.get("alerts", [])
    alerts = [dict_to_alert(a) for a in alert_dicts]

    # Format for Discord
    discord_message = format_alerts_for_discord(alerts)

    # Print the message (this is what gets sent to Discord)
    print(discord_message)


if __name__ == "__main__":
    main()
