"""Alert engine for managed positions.

Generates alerts from position rollups with severity levels and dedup keys.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import hashlib
import json


@dataclass
class Alert:
    """A single alert for a position."""
    severity: str  # INFO, WARN, CRITICAL, EMERGENCY
    position_id: str
    message: str
    dedup_key: str
    recommended_action: Optional[str] = None
    timestamp_ms: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.timestamp_ms is None:
            self.timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dict."""
        d = asdict(self)
        # Add @type for identification
        d["@type"] = "alert"
        return d


def _generate_dedup_key(severity: str, position_id: str, alert_type: str, context: str = "") -> str:
    """Generate a deduplication key for an alert."""
    key_str = f"{severity}:{position_id}:{alert_type}"
    if context:
        key_str += f":{context}"
    # Hash to keep it consistent and manageable length
    return hashlib.md5(key_str.encode()).hexdigest()[:16]


def _format_usd(value: Optional[float]) -> str:
    """Format a USD value."""
    if value is None:
        return "N/A"
    return f"${value:,.2f}"


def _format_pct(value: Optional[float]) -> str:
    """Format a percentage value."""
    if value is None:
        return "N/A"
    return f"{value * 100:.2f}%"


def _get_snapshots_missing_alert(rollup: Dict[str, Any]) -> Optional[Alert]:
    """Generate alert for missing snapshots."""
    if rollup["snapshots_status"] not in ("missing", "partial"):
        return None

    leg_count = rollup["leg_count"]
    with_snapshots = sum(1 for leg in rollup["legs"] if leg["has_snapshot"])
    missing_count = leg_count - with_snapshots

    position_id = rollup["position_id"]
    venue = rollup.get("venue", "unknown")
    strategy = rollup.get("strategy", "unknown")

    if rollup["snapshots_status"] == "missing":
        message = (
            f"**Missing Snapshots** - Position `{position_id}` ({venue}/{strategy}) "
            f"has {leg_count} legs but NO snapshots available. "
            f"Cannot assess risk status."
        )
        context = "all"
    else:  # partial
        message = (
            f"**Partial Snapshots** - Position `{position_id}` ({venue}/{strategy}) "
            f"has {missing_count} of {leg_count} legs missing snapshots. "
            f"Risk assessment may be incomplete."
        )
        context = f"{missing_count}/{leg_count}"

    recommended_action = (
        "Check connector / ensure leg registration / run snapshot pull. "
        "Legs with no snapshots: " +
        ", ".join(leg["inst_id"] for leg in rollup["legs"] if not leg["has_snapshot"])
    )

    dedup_key = _generate_dedup_key("WARN", position_id, "snapshots_missing", context)

    return Alert(
        severity="WARN",
        position_id=position_id,
        message=message,
        dedup_key=dedup_key,
        recommended_action=recommended_action,
        metadata={
            "alert_type": "snapshots_missing",
            "snapshots_status": rollup["snapshots_status"],
            "leg_count": leg_count,
            "with_snapshots": with_snapshots,
            "venue": venue,
            "strategy": strategy,
        }
    )


def _get_drift_alert(rollup: Dict[str, Any]) -> Optional[Alert]:
    """Generate alert for drift warnings/critical."""
    if not rollup["crit"] and not rollup["warn"]:
        return None

    position_id = rollup["position_id"]
    venue = rollup.get("venue", "unknown")
    strategy = rollup.get("strategy", "unknown")

    drift_usd = rollup.get("drift_usd")
    drift_pct = rollup.get("drift_pct")
    net_delta = rollup.get("net_delta_usd")
    gross_notional = rollup.get("gross_notional_usd")

    # If we can't compute drift (e.g., missing prices), skip drift alert.
    if drift_usd is None:
        return None

    # Determine severity
    if rollup["crit"]:
        severity = "CRITICAL"
        reason = rollup.get("crit_reason", "")
    else:
        severity = "WARN"
        reason = rollup.get("warn_reason", "")

    # Build message
    if severity == "CRITICAL":
        emoji = "🚨"
        action = "REBALANCE IMMEDIATELY"
    else:
        emoji = "⚠️"
        action = "Consider rebalancing"

    message = (
        f"{emoji} **Delta Drift {severity}** - Position `{position_id}` ({venue}/{strategy})\n"
        f"• Net Delta: {_format_usd(net_delta)}\n"
        f"• Drift: {_format_usd(drift_usd)} ({_format_pct(drift_pct)})\n"
        f"• Gross Notional: {_format_usd(gross_notional)}\n"
        f"• Threshold breached: {reason}"
    )

    # Recommended action
    recommended_action = (
        f"{action}. Review leg exposure and rebalance to delta-neutral. "
        f"Check for liquidation risk near current prices."
    )

    dedup_key = _generate_dedup_key(severity, position_id, "drift", f"{float(drift_usd):.2f}")

    return Alert(
        severity=severity,
        position_id=position_id,
        message=message,
        dedup_key=dedup_key,
        recommended_action=recommended_action,
        metadata={
            "alert_type": "drift",
            "drift_usd": drift_usd,
            "drift_pct": drift_pct,
            "net_delta": net_delta,
            "gross_notional": gross_notional,
            "venue": venue,
            "strategy": strategy,
        }
    )


def _get_carry_alert(carry_rollup: Dict[str, Any]) -> Optional[Alert]:
    """Generate alert for carry degradation using smoothing + persistence.

    Bean rule:
    - BTC EXIT persistence window: 12h
    - Other symbols (alts) EXIT persistence window: 24h

    We still compute apr_cur, but we avoid acting on it directly (too noisy).
    """

    position_id = carry_rollup["position_id"]
    venue = carry_rollup.get("venue", "unknown")
    strategy = carry_rollup.get("strategy", "unknown")

    apr_cur = carry_rollup.get("apr_cur")
    apr_14d = carry_rollup.get("apr_14d")

    sym = carry_rollup.get("symbol_hint") or str(position_id).split("_", 1)[0]
    sym = str(sym).upper() if sym else ""

    apr_s12 = carry_rollup.get("apr_smooth_12h")
    apr_s24 = carry_rollup.get("apr_smooth_24h")

    ok12 = bool(carry_rollup.get("smooth_ok_12h"))
    ok24 = bool(carry_rollup.get("smooth_ok_24h"))

    persist_nonpos_12h = carry_rollup.get("persist_nonpos_12h")
    persist_nonpos_24h = carry_rollup.get("persist_nonpos_24h")

    persist_below_10_12h = carry_rollup.get("persist_below_10apr_12h")
    persist_below_half14_12h = carry_rollup.get("persist_below_half_14d_12h")

    n12 = int(carry_rollup.get("n_samples_12h") or 0)
    n24 = int(carry_rollup.get("n_samples_24h") or 0)

    severity = None
    reason = None
    action = None

    # EXIT (CRITICAL) conditions require the right persistence window to be OK.
    if sym == "BTC":
        if ok12 and persist_nonpos_12h and (apr_s12 is not None and float(apr_s12) <= 0.0):
            severity = "CRITICAL"
            reason = "APR_smooth_12h <= 0 for ~12h (persistence)"
            action = "EXIT"
    else:
        if ok24 and persist_nonpos_24h and (apr_s24 is not None and float(apr_s24) <= 0.0):
            severity = "CRITICAL"
            reason = "APR_smooth_24h <= 0 for ~24h (persistence)"
            action = "EXIT"

    # REDUCE / WARNING conditions (12h persistence)
    if severity is None:
        if ok12 and persist_below_half14_12h:
            severity = "WARN"
            reason = "APR_smooth_12h < 0.5×APR14 for ~12h"
            action = "REDUCE"
        elif ok12 and persist_below_10_12h:
            severity = "WARN"
            reason = "APR_smooth_12h < 10% for ~12h"
            action = "REDUCE"

    # If we don't yet have enough history to enforce persistence, optionally emit a soft monitor.
    if severity is None:
        # Only if smoothed is already negative and we have at least a few samples.
        if (apr_s12 is not None and float(apr_s12) <= 0.0) and n12 >= 6 and not ok12:
            severity = "WARN"
            reason = "APR_smooth trending <= 0, but <12h history collected (monitor)"
            action = "MONITOR"

    if severity is None:
        return None

    emoji = "🚨" if severity == "CRITICAL" else "⚠️"

    def fmt_apr(x):
        return _format_pct(float(x) / 100.0) if x is not None else "N/A"

    message = (
        f"{emoji} **Carry {severity}** - Position `{position_id}` ({venue}/{strategy})\n"
        f"• symbol: {sym}\n"
        f"• apr_smooth_12h: {fmt_apr(apr_s12)} (n={n12}, ok={ok12})\n"
        f"• apr_smooth_24h: {fmt_apr(apr_s24)} (n={n24}, ok={ok24})\n"
        f"• apr_14d: {fmt_apr(apr_14d)}\n"
        f"• apr_cur (noisy): {fmt_apr(apr_cur)}\n"
        f"• Trigger: {reason}"
    )

    if action == "EXIT":
        recommended_action = (
            "EXIT the position (regime likely broken). "
            "Before exiting: check basis/spread and order book depth (avoid bad fills)."
        )
    elif action == "REDUCE":
        recommended_action = (
            "REDUCE size / tighten monitoring. If this persists into the next window, prepare to EXIT. "
            "Before acting, check basis/spread and depth."
        )
    else:
        recommended_action = (
            "MONITOR closely. Do NOT exit on a single funding print. "
            "Wait for persistence window or realized cashflow mismatch confirmation."
        )

    if carry_rollup.get("missing_funding_data") or carry_rollup.get("missing_smooth_data"):
        recommended_action += " (data may be incomplete; verify funding manually)"

    dedup_key = _generate_dedup_key(severity, position_id, "carry", f"{sym}:{action}:{reason}")

    return Alert(
        severity=severity,
        position_id=position_id,
        message=message,
        dedup_key=dedup_key,
        recommended_action=recommended_action,
        metadata={
            "alert_type": "carry",
            "symbol": sym,
            "action": action,
            "apr_smooth_12h": apr_s12,
            "apr_smooth_24h": apr_s24,
            "apr_cur": apr_cur,
            "apr_14d": apr_14d,
            "n12": n12,
            "n24": n24,
            "ok12": ok12,
            "ok24": ok24,
            "missing_funding_data": bool(carry_rollup.get("missing_funding_data")),
            "missing_smooth_data": bool(carry_rollup.get("missing_smooth_data")),
        },
    )


def generate_alerts(
    rollups: List[Dict[str, Any]],
    carry_rollups: Optional[List[Dict[str, Any]]] = None,
    expected_by_position: Optional[Dict[str, Dict[str, Any]]] = None,
    realized_24h_by_position: Optional[Dict[str, Dict[str, Any]]] = None,
    realized_7d_by_position: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Alert]:
    """
    Generate alerts from position rollups.

    Args:
        rollups: List of position rollup dicts from compute_all_rollups
        carry_rollups: Optional list of carry rollup dicts from compute_all_carries

    Returns:
        List of Alert objects
    """
    alerts = []

    for rollup in rollups:
        # Check for missing/partial snapshots
        snapshot_alert = _get_snapshots_missing_alert(rollup)
        if snapshot_alert:
            alerts.append(snapshot_alert)

        # Check for drift
        drift_alert = _get_drift_alert(rollup)
        if drift_alert:
            alerts.append(drift_alert)

    # Add carry alerts if provided
    if carry_rollups:
        for carry_rollup in carry_rollups:
            # Missing funding data should always WARN (graceful degradation)
            if carry_rollup.get("missing_funding_data"):
                position_id = carry_rollup["position_id"]
                venue = carry_rollup.get("venue", "unknown")
                strategy = carry_rollup.get("strategy", "unknown")
                msg = (
                    f"⚠️ **Missing Funding Data** - Position `{position_id}` ({venue}/{strategy}) has missing funding data "
                    f"for one or more legs. Carry/APR may be inaccurate."
                )
                action = "Verify funding rates manually (and check basis/depth) before acting on carry signals."
                dedup_key = _generate_dedup_key("WARN", position_id, "missing_funding_data")
                alerts.append(
                    Alert(
                        severity="WARN",
                        position_id=position_id,
                        message=msg,
                        dedup_key=dedup_key,
                        recommended_action=action,
                        metadata={"alert_type": "missing_funding_data"},
                    )
                )

            carry_alert = _get_carry_alert(carry_rollup)
            if carry_alert:
                alerts.append(carry_alert)

    # Realized vs expected carry alerts (cashflow sanity)
    if expected_by_position and (realized_24h_by_position or realized_7d_by_position):
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        for rollup in rollups:
            pid = rollup.get("position_id")
            if not pid or pid not in expected_by_position:
                continue

            exp = expected_by_position.get(pid) or {}
            exp_24h = exp.get("expected_net_usd_24h")
            exp_7d = exp.get("expected_net_usd_7d")
            exp_missing = bool(exp.get("missing") or False)

            # Position age (ms) comes from raw_position
            created_ms = None
            try:
                created_ms = (rollup.get("raw_position") or {}).get("created_at_ms")
            except Exception:
                created_ms = None
            age_hours = None
            if created_ms:
                try:
                    age_hours = (now_ms - int(created_ms)) / 3600_000.0
                except Exception:
                    age_hours = None

            # Suppress for very new positions
            if age_hours is not None and age_hours < 6.0:
                continue

            r24 = (realized_24h_by_position or {}).get(pid) or {
                "funding": 0.0,
                "fee": 0.0,
                "net": 0.0,
                "n_funding": 0,
                "n_fee": 0,
            }
            r7 = (realized_7d_by_position or {}).get(pid) or {
                "funding": 0.0,
                "fee": 0.0,
                "net": 0.0,
                "n_funding": 0,
                "n_fee": 0,
            }

            # If expected missing, warn only when expected is meaningfully positive
            if exp_missing:
                if exp_24h is not None and exp_24h >= 10.0:
                    msg = (
                        f"⚠️ **Carry Cashflow Check** - Position `{pid}` expected carry is positive, but expected calculation is incomplete (missing data).\n"
                        f"• expected_net_24h: {_format_usd(exp_24h)}\n"
                        f"• realized_net_24h (stable): {_format_usd(r24.get('net'))}\n"
                        f"• Note: missing leg funding and/or price data"
                    )
                    dedup_key = _generate_dedup_key("WARN", pid, "carry_cashflow_missing")
                    alerts.append(
                        Alert(
                            severity="WARN",
                            position_id=pid,
                            message=msg,
                            dedup_key=dedup_key,
                            recommended_action="Verify funding + prices manually for all legs; then decide reduce/exit. Also check basis/depth.",
                            metadata={"alert_type": "carry_cashflow_missing"},
                        )
                    )
                continue

            # Need expected value to compare
            if exp_24h is None:
                continue

            # Scale expected to position age for fair comparison
            scale_24 = 1.0
            if age_hours is not None:
                scale_24 = min(1.0, max(0.0, age_hours / 24.0))
            exp_24_window = float(exp_24h) * scale_24

            # Skip tiny expected (noise)
            if exp_24_window < 2.0:
                continue

            realized_net_24 = float(r24.get("net") or 0.0)
            realized_funding_24 = float(r24.get("funding") or 0.0)
            realized_fee_24 = float(r24.get("fee") or 0.0)

            # Require a minimum observation window before judging mismatch
            # (prevents false mismatch right after ledger baseline/init)
            obs_h = None
            try:
                mi = r24.get("min_ts")
                ma = r24.get("max_ts")
                if mi is not None and ma is not None and int(ma) >= int(mi):
                    obs_h = (int(ma) - int(mi)) / 3600_000.0
            except Exception:
                obs_h = None

            if (obs_h is None or obs_h < 6.0) and int(r24.get("n_funding") or 0) < 3:
                # Not enough samples yet — don't scream.
                continue

            ratio_24 = realized_net_24 / exp_24_window if exp_24_window != 0 else None

            # Special case: expected meaningful but we saw zero funding events
            if exp_24_window >= 5.0 and int(r24.get("n_funding") or 0) == 0:
                msg = (
                    f"⚠️ **No Realized Funding Seen** - Position `{pid}` expects funding, but no FUNDING cashflow events were recorded in last 24h.\n"
                    f"• expected_net_24h: {_format_usd(exp_24_window)}\n"
                    f"• realized_net_24h (stable): {_format_usd(realized_net_24)} (funding={_format_usd(realized_funding_24)}, fee={_format_usd(realized_fee_24)})\n"
                    f"• This can mean: ingestion missing / venue delay / mapping failed"
                )
                dedup_key = _generate_dedup_key("WARN", pid, "carry_cashflow_no_funding", f"{exp_24_window:.1f}")
                alerts.append(
                    Alert(
                        severity="WARN",
                        position_id=pid,
                        message=msg,
                        dedup_key=dedup_key,
                        recommended_action="Check pm_cashflows ingest logs + verify venue funding payouts manually. If carry actually flipped, EXIT. Also check basis/depth.",
                        metadata={"alert_type": "carry_cashflow_no_funding"},
                    )
                )
                continue

            # Severity rules
            severity = None
            reason = None
            if realized_net_24 <= 0.0 and exp_24_window >= 5.0:
                severity = "CRITICAL"
                reason = "realized_net_24h <= 0 while expected_net_24h is positive"
            elif realized_net_24 < 0.5 * exp_24_window:
                severity = "WARN"
                reason = "realized_net_24h < 50% of expected"

            if severity is None:
                continue

            emoji = "🚨" if severity == "CRITICAL" else "⚠️"
            ratio_str = "N/A" if ratio_24 is None else f"{ratio_24*100:.0f}%"

            msg = (
                f"{emoji} **Carry Cashflow Mismatch {severity}** - Position `{pid}`\n"
                f"• expected_net_24h (scaled): {_format_usd(exp_24_window)}\n"
                f"• realized_net_24h (stable): {_format_usd(realized_net_24)} (funding={_format_usd(realized_funding_24)}, fee={_format_usd(realized_fee_24)})\n"
                f"• ratio: {ratio_str}\n"
                f"• Trigger: {reason}"
            )

            action = (
                "If this persists, EXIT (you're not getting paid). "
                "First verify funding rate + payout schedule + mapping; then check basis/spread + depth before exiting."
            )

            ratio_bucket = "na" if ratio_24 is None else f"{round(ratio_24, 1):.1f}"
            dedup_key = _generate_dedup_key(severity, pid, "carry_cashflow_mismatch", ratio_bucket)

            alerts.append(
                Alert(
                    severity=severity,
                    position_id=pid,
                    message=msg,
                    dedup_key=dedup_key,
                    recommended_action=action,
                    metadata={
                        "alert_type": "carry_cashflow_mismatch",
                        "expected_net_24h": exp_24_window,
                        "realized_net_24h": realized_net_24,
                        "realized_funding_24h": realized_funding_24,
                        "realized_fee_24h": realized_fee_24,
                        "ratio_24": ratio_24,
                        "age_hours": age_hours,
                    },
                )
            )

    return alerts


def filter_alerts_by_cooldown(
    alerts: List[Alert],
    last_alerts: Dict[str, Dict[str, Any]],
    cooldown_min: float = 30.0
) -> List[Alert]:
    """
    Filter alerts based on cooldown to prevent spam.

    Args:
        alerts: List of Alert objects to filter
        last_alerts: Dict of last alert state from cooldown file
        cooldown_min: Cooldown period in minutes

    Returns:
        List of alerts that are not in cooldown
    """
    current_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    cooldown_ms = int(cooldown_min * 60 * 1000)

    filtered_alerts = []
    updated_last_alerts = {}

    for alert in alerts:
        dedup_key = alert.dedup_key
        last_sent = last_alerts.get(dedup_key, {}).get("last_sent_ms", 0)

        # Check if cooldown has passed
        if current_ms - last_sent >= cooldown_ms:
            filtered_alerts.append(alert)
            # Update last sent time
            updated_last_alerts[dedup_key] = {
                "last_sent_ms": current_ms,
                "severity": alert.severity,
                "position_id": alert.position_id,
                "message": alert.message,
                "recommended_action": alert.recommended_action,
            }

    return filtered_alerts, updated_last_alerts


def format_alerts_for_discord(alerts: List[Alert]) -> str:
    """
    Format alerts for Discord posting.

    Args:
        alerts: List of Alert objects

    Returns:
        Formatted string ready for Discord message
    """
    if not alerts:
        return "No alerts to report."

    lines = []

    # Header
    lines.append(f"# 🚨 Position Manager Alert ({len(alerts)} alerts)")
    lines.append("")

    # Group by severity
    for severity in ["CRITICAL", "WARN", "INFO"]:
        severity_alerts = [a for a in alerts if a.severity == severity]
        if not severity_alerts:
            continue

        # Section header
        if severity == "CRITICAL":
            lines.append(f"## 🚨 {severity}")
        elif severity == "WARN":
            lines.append(f"## ⚠️ {severity}")
        else:
            lines.append(f"## ℹ️ {severity}")

        lines.append("")

        # Alerts for this severity
        for alert in severity_alerts:
            lines.append(alert.message)
            if alert.recommended_action:
                lines.append(f"💡 **Action:** {alert.recommended_action}")
            lines.append("")

    # Footer with timestamp
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"*Generated at {timestamp}*")

    return "\n".join(lines)
