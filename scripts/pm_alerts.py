#!/usr/bin/env python3
"""Position Manager Alert CLI

Computes rollups, generates alerts, and prints them in human-readable or JSON format.
Supports cooldown to prevent repeated alert spam.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path for imports
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.position_manager.risk import compute_all_rollups, DEFAULT_WARN_DRIFT_USD, DEFAULT_CRIT_DRIFT_USD, DEFAULT_WARN_DRIFT_PCT, DEFAULT_CRIT_DRIFT_PCT
from tracking.position_manager.carry import compute_all_carries
from tracking.position_manager.cashflows import rollup_stable_by_position
from tracking.position_manager.alerts import generate_alerts, filter_alerts_by_cooldown, format_alerts_for_discord


DEFAULT_COOLDOWN_MIN = 30.0
DEFAULT_COOLDOWN_FILE = ROOT / "tracking" / "pm_alert_state.json"


def load_cooldown_state(file_path: Path) -> dict:
    """Load cooldown state from file."""
    if not file_path.exists():
        return {}

    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_cooldown_state(file_path: Path, state: dict):
    """Save cooldown state to file."""
    # Ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w") as f:
        json.dump(state, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Generate alerts for managed positions from rollups"
    )
    parser.add_argument(
        "--db",
        type=str,
        default=str(ROOT / "tracking" / "db" / "arbit_v3.db"),
        help="Path to SQLite database (default: tracking/db/arbit_v3.db)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of human-readable format"
    )
    parser.add_argument(
        "--cooldown-min",
        type=float,
        default=DEFAULT_COOLDOWN_MIN,
        help=f"Cooldown period in minutes before repeating same alert (default: {DEFAULT_COOLDOWN_MIN})"
    )
    parser.add_argument(
        "--cooldown-file",
        type=str,
        default=str(DEFAULT_COOLDOWN_FILE),
        help=f"Path to cooldown state file (default: {DEFAULT_COOLDOWN_FILE})"
    )
    parser.add_argument(
        "--no-cooldown",
        action="store_true",
        help="Disable cooldown (emit all alerts regardless of recent history)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate alerts but don't update cooldown state"
    )
    parser.add_argument(
        "--warn-drift-usd",
        type=float,
        default=DEFAULT_WARN_DRIFT_USD,
        help=f"Warning threshold for drift in USD (default: ${DEFAULT_WARN_DRIFT_USD})"
    )
    parser.add_argument(
        "--crit-drift-usd",
        type=float,
        default=DEFAULT_CRIT_DRIFT_USD,
        help=f"Critical threshold for drift in USD (default: ${DEFAULT_CRIT_DRIFT_USD})"
    )
    parser.add_argument(
        "--warn-drift-pct",
        type=float,
        default=DEFAULT_WARN_DRIFT_PCT,
        help=f"Warning threshold for drift percentage (default: {DEFAULT_WARN_DRIFT_PCT*100:.0f} pct)"
    )
    parser.add_argument(
        "--crit-drift-pct",
        type=float,
        default=DEFAULT_CRIT_DRIFT_PCT,
        help=f"Critical threshold for drift percentage (default: {DEFAULT_CRIT_DRIFT_PCT*100:.0f} pct)"
    )

    args = parser.parse_args()

    # Connect to database
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")

    try:
        # Load cooldown state
        cooldown_file = Path(args.cooldown_file)
        last_alerts = load_cooldown_state(cooldown_file)

        # Compute rollups
        rollups = compute_all_rollups(
            con,
            warn_drift_usd=args.warn_drift_usd,
            crit_drift_usd=args.crit_drift_usd,
            warn_drift_pct=args.warn_drift_pct,
            crit_drift_pct=args.crit_drift_pct
        )

        # Generate alerts
        # Compute carry rollups for carry alerts
        loris_csv_path = ROOT / "data" / "loris_funding_history.csv"
        carry_rollups = compute_all_carries(con, loris_csv_path)

        # Realized cashflows (stable only) for sanity checks
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        realized_24h = rollup_stable_by_position(con, now_ms - 24 * 3600 * 1000)
        realized_7d = rollup_stable_by_position(con, now_ms - 7 * 24 * 3600 * 1000)

        # Expected funding (USD) from carry rates × leg notionals
        carry_by_pos = {c["position_id"]: c for c in carry_rollups}
        expected_by_pos = {}

        for r in rollups:
            pid = r.get("position_id")
            if not pid or pid not in carry_by_pos:
                continue

            c = carry_by_pos[pid]
            funding_by_leg = {leg.get("leg_id"): float(leg.get("funding_8h_cur") or 0.0) for leg in (c.get("legs") or [])}

            missing = bool(c.get("missing_funding_data")) or (r.get("snapshots_status") == "partial_price")

            exp_8h_usd = 0.0
            legs_used = 0
            for leg in (r.get("legs") or []):
                leg_id = leg.get("leg_id")
                side = str(leg.get("side") or "").upper()
                notional = leg.get("notional_usd")
                if notional is None:
                    missing = True
                    continue
                if not leg_id:
                    missing = True
                    continue

                fr = funding_by_leg.get(leg_id)
                if fr is None:
                    missing = True
                    continue

                sign = 1.0 if side == "SHORT" else -1.0
                exp_8h_usd += sign * float(fr) * float(notional)
                legs_used += 1

            exp_24h = exp_8h_usd * 3.0
            exp_7d = exp_24h * 7.0

            expected_by_pos[pid] = {
                "expected_net_usd_8h": exp_8h_usd,
                "expected_net_usd_24h": exp_24h,
                "expected_net_usd_7d": exp_7d,
                "legs_used": legs_used,
                "missing": bool(missing),
            }

        all_alerts = generate_alerts(
            rollups,
            carry_rollups=carry_rollups,
            expected_by_position=expected_by_pos,
            realized_24h_by_position=realized_24h,
            realized_7d_by_position=realized_7d,
        )

        # Filter by cooldown (unless disabled)
        if args.no_cooldown:
            filtered_alerts = all_alerts
            updated_last_alerts = {}
        else:
            filtered_alerts, updated_last_alerts = filter_alerts_by_cooldown(
                all_alerts,
                last_alerts,
                cooldown_min=args.cooldown_min
            )

        # Output
        if args.json:
            output = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_positions": len(rollups),
                "total_alerts": len(all_alerts),
                "filtered_alerts": len(filtered_alerts),
                "alerts": [alert.to_dict() for alert in filtered_alerts]
            }
            print(json.dumps(output, indent=2))
        else:
            # Human-readable output
            print("=" * 80)
            print(f"Position Manager Alert Report")
            print(f"Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print("=" * 80)
            print()

            # Summary
            print(f"Positions analyzed: {len(rollups)}")
            print(f"Alerts generated: {len(all_alerts)}")
            print(f"Alerts after cooldown filter: {len(filtered_alerts)}")

            if not args.no_cooldown and len(all_alerts) > len(filtered_alerts):
                print(f"  ({len(all_alerts) - len(filtered_alerts)} suppressed by {args.cooldown_min}min cooldown)")

            print()

            # Show alerts
            if filtered_alerts:
                print("🚨 ALERTS:")
                print("-" * 80)
                print(format_alerts_for_discord(filtered_alerts))
            else:
                print("✅ No alerts to report.")

        # Update cooldown state (unless dry run or no cooldown)
        if not args.dry_run and not args.no_cooldown:
            # Merge updated alerts with existing state
            last_alerts.update(updated_last_alerts)
            save_cooldown_state(cooldown_file, last_alerts)

    finally:
        con.close()


if __name__ == "__main__":
    main()
