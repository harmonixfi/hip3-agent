"""Carry monitoring for managed positions.

Computes funding rate carry and exit signals for delta-neutral arbitrage positions.
Detects when funding flips negative or drops below historical averages.
"""

from __future__ import annotations

import csv
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Iterable

from .carry_loris_window import read_tail_lines, ensure_header


# Venue name mappings for Loris CSV exchange field
# Maps venue names to Loris exchange names
VENUE_TO_LORIS = {
    "hyperliquid": "hyperliquid",
    "paradex": "paradex",
    "ethereal": "ethereal",
    "lighter": "lighter",
    "okx": "okx",
    "hyena": "hyena",
    # extra venues if we want to use the same carry logic from Loris
    "tradexyz": "tradexyz",
    "kinetiq": "kinetiq",
    "felix": "felix",
}

HYPERLIQUID_DEX_TO_LORIS = {
    "xyz": "tradexyz",
    "flx": "felix",
    "km": "kinetiq",
    "hyna": "hyena",
}

# Symbol aliases: maps internal/position names to Loris CSV symbols
# e.g. Hyperliquid perp uses "GOLD" but Loris CSV uses commodity code "XAU"
SYMBOL_ALIASES = {
    "GOLD": "XAU",
}


def _is_spot_leg(inst_id: str) -> bool:
    """
    Determine if a leg is a spot leg based on instrument ID.

    Args:
        inst_id: Instrument identifier

    Returns:
        True if spot leg, False if perp
    """
    # Spot legs typically have "/" separator (e.g., "LIT/USDC")
    return "/" in inst_id


def _get_funding_from_db(
    con: sqlite3.Connection,
    venue: str,
    inst_id: str,
    hours_lookback: float = 8.0
) -> Optional[float]:
    """
    Get latest 8h-equivalent funding rate from DB v3 funding_v3 table.

    Args:
        con: SQLite database connection
        venue: Venue name
        inst_id: Instrument ID
        hours_lookback: How many hours back to look for latest data

    Returns:
        8h-equivalent funding rate as decimal, or None if not found
    """
    # Query latest funding rate for (venue, inst_id)
    sql = """
    SELECT funding_rate, interval_hours
    FROM funding_v3
    WHERE venue = ? AND inst_id = ?
    ORDER BY ts DESC
    LIMIT 1
    """
    cursor = con.execute(sql, (venue, inst_id))
    row = cursor.fetchone()

    if not row:
        return None

    funding_rate, interval_hours = row

    # If interval_hours is None, assume it's already 8h-equivalent
    if interval_hours is None:
        return float(funding_rate)

    # Convert to 8h-equivalent
    # funding_8h = funding_rate * (8 / interval_hours)
    funding_8h = funding_rate * (8.0 / interval_hours)
    return funding_8h


def _normalize_loris_symbol(inst_id: str) -> str:
    """Normalize an inst_id into Loris CSV `symbol`.

    Conventions seen:
    - Hyperliquid builder dex: xyz:GOLD -> GOLD
    - Ethereal: BTCUSD -> BTC
    - Paradex: BTC-USD-PERP -> BTC
    - Lighter perp: MORPHO -> MORPHO
    - Spot: LIT/USDC stays spot but funding=0 anyway
    """

    symbol = str(inst_id)

    # Hyperliquid builder-dex / namespaced perp ids use dex:COIN
    if ":" in symbol:
        symbol = symbol.split(":", 1)[1]

    # Remove common perp suffixes
    for suffix in ["-PERP", "-USD-PERP", "-USDT-PERP", "-P"]:
        if symbol.endswith(suffix):
            symbol = symbol[: -len(suffix)]
            break

    # Remove quote suffixes
    for q in ["USD", "USDT"]:
        if symbol.endswith(q) and ("-" not in symbol) and ("/" not in symbol):
            # e.g. BTCUSD -> BTC
            symbol = symbol[: -len(q)]
            break

    # If paradex style with dashes remains (e.g. BTC-USD), keep base
    if "-" in symbol:
        symbol = symbol.split("-")[0]

    # Apply symbol aliases (e.g. GOLD -> XAU)
    symbol = SYMBOL_ALIASES.get(symbol, symbol)

    return symbol


def _resolve_loris_market(venue: str, inst_id: str) -> Optional[Tuple[str, str]]:
    """Resolve a position leg into Loris (exchange, symbol)."""

    venue_l = str(venue or "").strip().lower()
    symbol = _normalize_loris_symbol(inst_id)
    if not symbol:
        return None

    if venue_l == "hyperliquid":
        raw_inst = str(inst_id or "").strip()
        if ":" in raw_inst:
            dex, _coin = raw_inst.split(":", 1)
            exchange = HYPERLIQUID_DEX_TO_LORIS.get(dex.strip().lower())
            if exchange is None:
                return None
            return exchange, symbol

    exchange = VENUE_TO_LORIS.get(venue_l)
    if exchange is None:
        return None
    return exchange, symbol


def _is_funding_leg(position: Dict[str, Any], leg: Dict[str, Any]) -> bool:
    """Return whether a position leg should resolve perp funding.

    Spot-perp positions often register spot legs with plain symbols like BTC or HYPE,
    so string-only spot detection is not sufficient here.
    """

    strategy = str(position.get("strategy") or "").upper()
    side = str(leg.get("side") or "").upper()
    inst_id = str(leg.get("inst_id") or "")

    if strategy == "SPOT_PERP":
        if side == "SHORT":
            return True
        if side == "LONG":
            return False

    return not _is_spot_leg(inst_id)


def _get_funding_from_csv(
    csv_path: Path,
    venue: str,
    inst_id: str,
    hours_lookback: float = 8.0
) -> Optional[Dict[str, Any]]:
    """
    Get latest funding rate from Loris funding history CSV.

    Args:
        csv_path: Path to loris_funding_history.csv
        venue: Venue name
        inst_id: Instrument ID
        hours_lookback: How many hours back to look for latest data

    Returns:
        Dict with 'funding_8h_rate' and 'source', or None if not found
    """
    if not csv_path.exists():
        return None

    resolved = _resolve_loris_market(venue, inst_id)
    if resolved is None:
        return None
    exchange, symbol = resolved

    # Read CSV and find latest matching row
    try:
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            latest_row = None
            latest_ts = None

            for row in reader:
                # Check if exchange matches
                if row.get('exchange', '').lower() != exchange.lower():
                    continue

                # Check if symbol matches (case-insensitive)
                if row.get('symbol', '').upper() != symbol.upper():
                    continue

                # Parse timestamp
                ts_str = row.get('timestamp_utc', '')
                try:
                    # Parse ISO 8601 format
                    ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    continue

                # Keep the latest row
                if latest_ts is None or ts > latest_ts:
                    latest_ts = ts
                    latest_row = row

        if latest_row is None:
            return None

        # Extract funding_8h_rate
        funding_8h_rate_str = latest_row.get('funding_8h_rate', '0')
        try:
            funding_8h_rate = float(funding_8h_rate_str)
        except (ValueError, TypeError):
            return None

        return {
            'funding_8h_rate': funding_8h_rate,
            'source': 'loris_csv',
            'timestamp': latest_ts,
        }
    except Exception:
        return None


def _get_historical_funding_from_db(
    con: sqlite3.Connection,
    venue: str,
    inst_id: str,
    days: int = 14
) -> Optional[List[Tuple[datetime, float]]]:
    """
    Get historical funding rates from DB v3 for computing averages.

    Args:
        con: SQLite database connection
        venue: Venue name
        inst_id: Instrument ID
        days: Number of days to look back

    Returns:
        List of (timestamp, funding_8h_rate) tuples, or None if not found
    """
    cutoff_ts = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)

    sql = """
    SELECT ts, funding_rate, interval_hours
    FROM funding_v3
    WHERE venue = ? AND inst_id = ? AND ts >= ?
    ORDER BY ts DESC
    """
    cursor = con.execute(sql, (venue, inst_id, cutoff_ts))
    rows = cursor.fetchall()

    if not rows:
        return None

    history = []
    for ts_ms, funding_rate, interval_hours in rows:
        ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)

        # Convert to 8h-equivalent
        if interval_hours is None:
            funding_8h = float(funding_rate)
        else:
            funding_8h = funding_rate * (8.0 / interval_hours)

        history.append((ts, funding_8h))

    return history


def _get_historical_funding_from_csv(
    csv_path: Path,
    venue: str,
    inst_id: str,
    days: int = 14
) -> Optional[List[Tuple[datetime, float]]]:
    """
    Get historical funding rates from Loris CSV for computing averages.

    Args:
        csv_path: Path to loris_funding_history.csv
        venue: Venue name
        inst_id: Instrument ID
        days: Number of days to look back

    Returns:
        List of (timestamp, funding_8h_rate) tuples, or None if not found
    """
    if not csv_path.exists():
        return None

    resolved = _resolve_loris_market(venue, inst_id)
    if resolved is None:
        return None
    exchange, symbol = resolved

    cutoff_ts = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            history = []

            for row in reader:
                # Check if exchange matches
                if row.get('exchange', '').lower() != exchange.lower():
                    continue

                # Check if symbol matches
                if row.get('symbol', '').upper() != symbol.upper():
                    continue

                # Parse timestamp
                ts_str = row.get('timestamp_utc', '')
                try:
                    ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    continue

                # Skip if too old
                if ts < cutoff_ts:
                    continue

                # Extract funding_8h_rate
                funding_8h_rate_str = row.get('funding_8h_rate', '0')
                try:
                    funding_8h_rate = float(funding_8h_rate_str)
                except (ValueError, TypeError):
                    continue

                history.append((ts, funding_8h_rate))

        return history if history else None
    except Exception:
        return None


def _compute_trimmed_mean(values: List[float], trim_pct: float = 0.1) -> Optional[float]:
    """
    Compute trimmed mean of values to reduce outlier impact.

    Args:
        values: List of float values
        trim_pct: Percentage to trim from each end (0.1 = trim 10% from each end)

    Returns:
        Trimmed mean or None if insufficient values
    """
    if not values:
        return None

    if len(values) < 3:
        # For very small samples, use simple mean
        return sum(values) / len(values)

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    k = int(n * trim_pct)

    # Trim k values from each end
    trimmed = sorted_vals[k:n-k] if k > 0 else sorted_vals

    return sum(trimmed) / len(trimmed)


def _position_amount_usd(position: Dict[str, Any]) -> Optional[float]:
    meta = position.get("meta") or {}
    try:
        amount_usd = float(meta.get("amount_usd"))
    except (TypeError, ValueError):
        return None
    return amount_usd if amount_usd > 0 else None


def _estimated_funding_leg_notional_usd(position: Dict[str, Any], leg: Dict[str, Any]) -> Optional[float]:
    amount_usd = _position_amount_usd(position)
    if amount_usd is None:
        return None

    funding_legs = [candidate for candidate in position.get("legs") or [] if _is_funding_leg(position, candidate)]
    if not funding_legs:
        return None

    return amount_usd / max(len(position.get("legs") or []), len(funding_legs), 1)


def _ledger_funding_sum(
    con: sqlite3.Connection,
    *,
    leg_id: str,
    since_dt: datetime,
) -> Optional[float]:
    row = con.execute(
        """
        SELECT SUM(amount)
        FROM pm_cashflows
        WHERE leg_id = ?
          AND cf_type = 'FUNDING'
          AND ts >= ?
          AND UPPER(currency) IN ('USD', 'USDC', 'USDT')
        """,
        (leg_id, int(since_dt.timestamp() * 1000)),
    ).fetchone()
    if not row or row[0] is None:
        return None
    return float(row[0])


def _compute_leg_carry_from_cashflows(
    position: Dict[str, Any],
    leg: Dict[str, Any],
    con: sqlite3.Connection,
) -> Optional[Dict[str, Any]]:
    """Fallback carry for existing positions when public funding series is unavailable."""

    leg_id = str(leg.get("leg_id") or "")
    if not leg_id:
        return None

    leg_notional_usd = _estimated_funding_leg_notional_usd(position, leg)
    if leg_notional_usd is None or leg_notional_usd <= 0:
        return None

    now = datetime.now(timezone.utc)
    funding_1d = _ledger_funding_sum(con, leg_id=leg_id, since_dt=now - timedelta(days=1))
    funding_7d = _ledger_funding_sum(con, leg_id=leg_id, since_dt=now - timedelta(days=7))
    funding_14d = _ledger_funding_sum(con, leg_id=leg_id, since_dt=now - timedelta(days=14))

    if funding_1d is None and funding_7d is None and funding_14d is None:
        return None

    result = {
        'leg_id': leg.get('leg_id'),
        'inst_id': leg.get('inst_id', ''),
        'venue': leg.get('venue', ''),
        'side': leg.get('side', ''),
        'funding_8h_cur': 0.0,
        'data_source': 'pm_cashflows',
        'missing_funding_data': False,
    }

    if funding_1d is not None:
        result['funding_8h_cur'] = funding_1d / 3.0 / leg_notional_usd
    if funding_7d is not None:
        result['funding_8h_7d_avg'] = funding_7d / 7.0 / 3.0 / leg_notional_usd
        result['historical_source'] = 'pm_cashflows'
    if funding_14d is not None:
        result['funding_8h_14d_avg'] = funding_14d / 14.0 / 3.0 / leg_notional_usd
        result['historical_source'] = 'pm_cashflows'

    return result


def compute_leg_carry(
    leg: Dict[str, Any],
    con: sqlite3.Connection,
    loris_csv_path: Path,
    use_historical: bool = True
) -> Dict[str, Any]:
    """
    Compute carry metrics for a single leg.

    Args:
        leg: Leg dict from pm_legs
        con: SQLite database connection
        loris_csv_path: Path to loris_funding_history.csv
        use_historical: Whether to compute historical averages

    Returns:
        Dict with carry metrics for the leg
    """
    inst_id = leg.get('inst_id', '')
    venue = leg.get('venue', '')
    side = leg.get('side', '')

    result = {
        'leg_id': leg.get('leg_id'),
        'inst_id': inst_id,
        'venue': venue,
        'side': side,
        'funding_8h_cur': 0.0,
        'data_source': 'none',
        'missing_funding_data': False,
    }

    # Spot legs have no funding
    if _is_spot_leg(inst_id):
        result['data_source'] = 'spot'
        result['funding_8h_cur'] = 0.0
        return result

    # Try to get funding from DB first
    funding_8h = _get_funding_from_db(con, venue, inst_id)

    if funding_8h is not None:
        result['funding_8h_cur'] = funding_8h
        result['data_source'] = 'funding_v3'
    else:
        # Fallback to Loris CSV
        loris_data = _get_funding_from_csv(loris_csv_path, venue, inst_id)
        if loris_data:
            result['funding_8h_cur'] = loris_data['funding_8h_rate']
            result['data_source'] = 'loris_csv'
        else:
            result['missing_funding_data'] = True
            result['funding_8h_cur'] = 0.0

    # Compute historical averages if requested
    if use_historical and not result['missing_funding_data']:
        # Try DB first
        hist_db = _get_historical_funding_from_db(con, venue, inst_id, days=14)

        if hist_db:
            # Compute 7D and 14D averages
            now = datetime.now(timezone.utc)
            hist_7d = [(ts, rate) for ts, rate in hist_db if ts >= now - timedelta(days=7)]
            hist_14d = hist_db

            result['funding_8h_7d_avg'] = _compute_trimmed_mean([r for _, r in hist_7d]) if hist_7d else None
            result['funding_8h_14d_avg'] = _compute_trimmed_mean([r for _, r in hist_14d]) if hist_14d else None
            result['historical_source'] = 'funding_v3'
        else:
            # Fallback to Loris CSV for historical
            hist_csv = _get_historical_funding_from_csv(loris_csv_path, venue, inst_id, days=14)

            if hist_csv:
                now = datetime.now(timezone.utc)
                hist_7d = [(ts, rate) for ts, rate in hist_csv if ts >= now - timedelta(days=7)]
                hist_14d = hist_csv

                result['funding_8h_7d_avg'] = _compute_trimmed_mean([r for _, r in hist_7d]) if hist_7d else None
                result['funding_8h_14d_avg'] = _compute_trimmed_mean([r for _, r in hist_14d]) if hist_14d else None
                result['historical_source'] = 'loris_csv'

    return result


def _apr_to_net8h(apr_pct: float) -> float:
    # APR% = net_8h * 3 * 365 * 100
    return float(apr_pct) / (3.0 * 365.0 * 100.0)


def _net8h_to_apr(net8h: float) -> float:
    return float(net8h) * 3.0 * 365.0 * 100.0


def _loris_net_series_for_position(
    position: Dict[str, Any],
    loris_csv_path: Path,
    *,
    window_hours: float,
) -> Tuple[List[Tuple[datetime, float]], bool]:
    """Compute position net_8h time series from loris CSV for last window_hours.

    Returns:
      (series, missing)

    series timestamps are CSV timestamps.
    missing=True if any perp leg missing too often.
    """

    if not loris_csv_path.exists():
        return [], True

    legs = position.get("legs") or []
    perp_legs = [l for l in legs if _is_funding_leg(position, l)]

    # If no perp legs, nothing to do
    if not perp_legs:
        return [], False

    # Build keys for each leg
    leg_keys = []
    missing = False
    for leg in perp_legs:
        venue = str(leg.get("venue") or "").lower()
        resolved = _resolve_loris_market(venue, str(leg.get("inst_id") or ""))
        if not resolved:
            missing = True
            continue
        ex, sym = resolved
        side = str(leg.get("side") or "").upper()
        sign = 1.0 if side == "SHORT" else -1.0
        leg_keys.append((ex.lower(), sym.upper(), sign))

    if not leg_keys:
        return [], True

    cutoff = datetime.now(timezone.utc) - timedelta(hours=float(window_hours))

    # Read tail chunk and parse
    lines = ensure_header(read_tail_lines(loris_csv_path, max_bytes=2_000_000))
    if len(lines) < 2:
        return [], True

    # Build per-timestamp dict of (exchange,symbol)->rate
    # Loris writes many rows per timestamp.
    by_ts: Dict[datetime, Dict[Tuple[str, str], float]] = {}

    try:
        reader = csv.DictReader(lines)
        for row in reader:
            try:
                ts = datetime.fromisoformat(str(row.get("timestamp_utc") or "").replace("Z", "+00:00"))
            except Exception:
                continue
            if ts < cutoff:
                continue
            ex = str(row.get("exchange") or "").lower()
            sym = str(row.get("symbol") or "").upper()
            try:
                fr = float(row.get("funding_8h_rate") or 0.0)
            except Exception:
                continue
            by_ts.setdefault(ts, {})[(ex, sym)] = fr
    except Exception:
        return [], True

    series: List[Tuple[datetime, float]] = []
    for ts in sorted(by_ts.keys()):
        m = by_ts[ts]
        ok = True
        net = 0.0
        for ex, sym, sign in leg_keys:
            key = (ex, sym)
            if key not in m:
                ok = False
                break
            net += sign * float(m[key])
        if ok:
            series.append((ts, net))

    # Require enough samples for persistence
    expected = int(window_hours * 2)  # 30m cadence
    if len(series) < max(6, int(0.5 * expected)):
        missing = True

    return series, missing


def compute_position_carry(
    position: Dict[str, Any],
    con: sqlite3.Connection,
    loris_csv_path: Path
) -> Dict[str, Any]:
    """
    Compute carry metrics for a position.

    Args:
        position: Position dict with legs (from load_managed_positions)
        con: SQLite database connection
        loris_csv_path: Path to loris_funding_history.csv

    Returns:
        Dict with carry rollup for the position
    """
    pid = position['position_id']
    symbol_hint = str(pid).split("_", 1)[0] if pid else None

    result = {
        'position_id': pid,
        'status': position['status'],
        'venue': position['venue'],
        'strategy': position.get('strategy'),
        'symbol_hint': symbol_hint,
        'legs': [],
        'net_8h_cur': 0.0,
        'apr_cur': 0.0,
        'apr_7d': None,
        'apr_14d': None,
        # Smoothed carry + persistence (loris-aligned)
        'net_8h_smooth_12h': None,
        'apr_smooth_12h': None,
        'n_samples_12h': 0,
        'smooth_ok_12h': False,
        'persist_nonpos_12h': None,
        'persist_below_10apr_12h': None,
        'persist_below_half_14d_12h': None,
        'net_8h_smooth_24h': None,
        'apr_smooth_24h': None,
        'n_samples_24h': 0,
        'smooth_ok_24h': False,
        'persist_nonpos_24h': None,
        'smooth_source': None,
        'missing_funding_data': False,
        'missing_smooth_data': False,
    }

    # Compute carry for each leg
    leg_carries = []
    net_8h = 0.0
    historical_7d_rates = []
    historical_14d_rates = []

    for leg in position['legs']:
        leg_carry = compute_leg_carry(leg, con, loris_csv_path, use_historical=True)
        if _is_funding_leg(position, leg) and leg_carry['missing_funding_data']:
            ledger_carry = _compute_leg_carry_from_cashflows(position, leg, con)
            if ledger_carry is not None:
                leg_carry = ledger_carry
        if not _is_funding_leg(position, leg):
            leg_carry['data_source'] = 'spot'
            leg_carry['missing_funding_data'] = False
            leg_carry['funding_8h_cur'] = 0.0
            leg_carry.pop('funding_8h_7d_avg', None)
            leg_carry.pop('funding_8h_14d_avg', None)
            leg_carry.pop('historical_source', None)
        leg_carries.append(leg_carry)

        # Track missing data
        if leg_carry['missing_funding_data']:
            result['missing_funding_data'] = True

        # Compute contribution to net funding
        # For SHORT: we RECEIVE funding (+)
        # For LONG: we PAY funding (-)
        sign = 1.0 if leg['side'] == 'SHORT' else -1.0
        contribution = sign * leg_carry['funding_8h_cur']
        net_8h += contribution

        # Collect historical rates for position-level averages
        if 'funding_8h_7d_avg' in leg_carry and leg_carry['funding_8h_7d_avg'] is not None:
            historical_7d_rates.append(sign * leg_carry['funding_8h_7d_avg'])
        if 'funding_8h_14d_avg' in leg_carry and leg_carry['funding_8h_14d_avg'] is not None:
            historical_14d_rates.append(sign * leg_carry['funding_8h_14d_avg'])

    result['legs'] = leg_carries
    result['net_8h_cur'] = net_8h

    # Annualize to APR: net_8h * 3 * 365 * 100 (percentage)
    result['apr_cur'] = net_8h * 3.0 * 365.0 * 100.0

    # Compute historical APR averages
    if historical_7d_rates:
        net_7d_avg = sum(historical_7d_rates) / len(historical_7d_rates)
        result['apr_7d'] = net_7d_avg * 3.0 * 365.0 * 100.0

    if historical_14d_rates:
        net_14d_avg = sum(historical_14d_rates) / len(historical_14d_rates)
        result['apr_14d'] = net_14d_avg * 3.0 * 365.0 * 100.0

    # --- Smoothed carry + persistence from loris (aligned timestamps) ---
    # This reduces false exits from single-sample funding noise.
    series12, miss12 = _loris_net_series_for_position(position, loris_csv_path, window_hours=12)
    v12 = [v for _, v in series12]
    result['n_samples_12h'] = len(v12)
    result['smooth_ok_12h'] = len(v12) >= 12

    if v12:
        net12 = _compute_trimmed_mean(v12, trim_pct=0.1)
        if net12 is not None:
            result['net_8h_smooth_12h'] = float(net12)
            result['apr_smooth_12h'] = _net8h_to_apr(net12)

        # Persistence checks ("continuously")
        # Treat <=0 as non-positive.
        if result['smooth_ok_12h']:
            result['persist_nonpos_12h'] = all(v <= 0 for v in v12)

            net_thresh_10 = _apr_to_net8h(10.0)
            result['persist_below_10apr_12h'] = all(v <= net_thresh_10 for v in v12)

            if result.get('apr_14d') is not None:
                thr = 0.5 * _apr_to_net8h(float(result['apr_14d']))
                result['persist_below_half_14d_12h'] = all(v <= thr for v in v12)

        result['smooth_source'] = 'loris_csv'
    else:
        result['missing_smooth_data'] = True

    series24, miss24 = _loris_net_series_for_position(position, loris_csv_path, window_hours=24)
    v24 = [v for _, v in series24]
    result['n_samples_24h'] = len(v24)
    result['smooth_ok_24h'] = len(v24) >= 24

    if v24:
        net24 = _compute_trimmed_mean(v24, trim_pct=0.1)
        if net24 is not None:
            result['net_8h_smooth_24h'] = float(net24)
            result['apr_smooth_24h'] = _net8h_to_apr(net24)
        if result['smooth_ok_24h']:
            result['persist_nonpos_24h'] = all(v <= 0 for v in v24)
        result['smooth_source'] = result.get('smooth_source') or 'loris_csv'
    else:
        result['missing_smooth_data'] = True

    if miss12 or miss24:
        result['missing_smooth_data'] = True

    return result


def compute_all_carries(
    con: sqlite3.Connection,
    loris_csv_path: Path,
    positions: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Compute carry rollups for all managed positions.

    Args:
        con: SQLite database connection
        loris_csv_path: Path to loris_funding_history.csv
        positions: List of positions (from load_managed_positions), or None to load from DB

    Returns:
        List of position carry rollup dicts
    """
    # Load positions if not provided
    from .risk import load_managed_positions

    if positions is None:
        positions = load_managed_positions(con)

    if not positions:
        return []

    # Compute carry for each position
    carry_rollups = []
    for position in positions:
        carry_rollup = compute_position_carry(position, con, loris_csv_path)
        carry_rollups.append(carry_rollup)

    return carry_rollups
