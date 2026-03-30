"""Felix equities private connector.

Provides access to Felix equity portfolio, orders, and fills via the Felix
proxy API. Requires a valid JWT from the Turnkey auth flow (felix_auth.py).

Felix API is accessed through the Cloudflare Workers proxy:
    https://spot-equities-proxy.white-star-bc1e.workers.dev

All endpoints require Authorization: Bearer <jwt> header.

Usage:
    from tracking.connectors.felix_private import FelixPrivateConnector

    connector = FelixPrivateConnector(jwt="eyJ...", wallet_address="0x...")
    portfolio = connector.fetch_portfolio()
    fills = connector.fetch_fills()
"""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.parse
from typing import Any, Dict, List, Optional

from .private_base import PrivateConnectorBase

FELIX_PROXY_BASE = "https://spot-equities-proxy.white-star-bc1e.workers.dev"


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def _normalize_felix_inst_id(symbol: str) -> str:
    """Normalize Felix equity symbol to SYMBOL/USDC format.

    Felix API returns plain symbols (AAPL, GOOGL). Our schema uses
    SYMBOL/USDC for spot instruments (consistent with HL spot).
    """
    s = str(symbol or "").strip()
    if not s:
        return ""
    if "/" in s:
        return s  # already normalized
    return f"{s}/USDC"


def _iso_to_epoch_ms(iso_str: str) -> int:
    """Convert ISO 8601 datetime string to epoch milliseconds.

    Handles common formats: 2026-03-15T10:00:00Z, 2026-03-15T10:00:00.000Z
    """
    from datetime import datetime, timezone

    s = str(iso_str or "").strip()
    if not s:
        return 0

    # Handle milliseconds if present
    if "." in s:
        s = s.split(".")[0] + "Z"

    # Remove trailing Z and parse as UTC
    s = s.rstrip("Z")
    try:
        dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
        dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return 0


def _felix_get(
    path: str,
    jwt: str,
    *,
    params: Optional[Dict[str, str]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Make an authenticated GET request to Felix proxy API."""
    url = FELIX_PROXY_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {jwt}",
            "User-Agent": "arbit-felix-private/0.1",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


# ---------------------------------------------------------------------------
# Response Parsers (module-level for testability)
# ---------------------------------------------------------------------------


def _parse_portfolio_response(
    raw: Dict[str, Any],
    wallet_address: str,
) -> Dict[str, Any]:
    """Parse Felix portfolio response into normalized structure.

    Args:
        raw: raw API response from /v1/portfolio/{address}
        wallet_address: the wallet address used for the query

    Returns:
        Normalized dict with account_id, balances, and positions list
    """
    positions = []
    for p in raw.get("positions", []):
        if not isinstance(p, dict):
            continue
        symbol = str(p.get("symbol", ""))
        inst_id = _normalize_felix_inst_id(symbol)
        if not inst_id:
            continue

        size = _to_float(p.get("quantity"))
        if size is None or size == 0:
            continue

        side = str(p.get("side", "")).upper()
        if side not in ("LONG", "SHORT"):
            side = "LONG"  # Felix equities are long by default

        positions.append({
            "inst_id": inst_id,
            "side": side,
            "size": abs(size),
            "entry_price": _to_float(p.get("averageEntryPrice")),
            "current_price": _to_float(p.get("currentPrice")),
            "unrealized_pnl": _to_float(p.get("unrealizedPnl")),
            "raw": p,
        })

    return {
        "account_id": wallet_address,
        "total_balance": _to_float(raw.get("accountValue")),
        "available_balance": _to_float(raw.get("availableBalance")),
        "positions": positions,
        "raw_json": raw,
    }


def _parse_fills_response(
    raw: Dict[str, Any],
    wallet_address: str,
) -> List[Dict[str, Any]]:
    """Parse Felix orders/fills response into pm_fills-compatible dicts.

    Felix may return orders rather than individual fills. Each FILLED order
    is treated as a single fill with averageFilledPrice and filledQuantity.

    Unfilled, cancelled, or pending orders are skipped.

    Args:
        raw: raw API response from /v1/trading/orders
        wallet_address: the wallet address

    Returns:
        List of fill dicts compatible with insert_fills()
    """
    from tracking.pipeline.fill_ingester import generate_synthetic_tid

    fills = []
    orders = raw.get("orders", [])
    if not isinstance(orders, list):
        return fills

    for order in orders:
        if not isinstance(order, dict):
            continue

        status = str(order.get("status", "")).upper()
        if status not in ("FILLED", "PARTIALLY_FILLED"):
            continue

        symbol = str(order.get("symbol", ""))
        inst_id = _normalize_felix_inst_id(symbol)
        if not inst_id:
            continue

        px = _to_float(order.get("averageFilledPrice"))
        sz = _to_float(order.get("filledQuantity"))
        if not px or px <= 0 or not sz or sz <= 0:
            continue

        side = str(order.get("side", "")).upper()
        if side not in ("BUY", "SELL"):
            continue

        fee = _to_float(order.get("fee")) or 0.0

        # Timestamp: prefer updatedAt (fill time), fallback to createdAt
        ts_str = order.get("updatedAt") or order.get("createdAt") or ""
        ts_ms = _iso_to_epoch_ms(ts_str)

        # Trade ID: use order ID if available, otherwise synthetic
        order_id = str(order.get("id", "")) or None
        if order_id:
            tid = f"felix_{order_id}"
        else:
            tid = generate_synthetic_tid(
                venue="felix",
                account_id=wallet_address,
                inst_id=inst_id,
                side=side,
                px=px,
                sz=sz,
                ts=ts_ms,
            )

        fills.append({
            "venue": "felix",
            "account_id": wallet_address,
            "tid": tid,
            "oid": order_id,
            "inst_id": inst_id,
            "side": side,
            "px": px,
            "sz": sz,
            "fee": fee,
            "fee_currency": "USDC",
            "ts": ts_ms,
            "closed_pnl": None,
            "dir": None,
            "builder_fee": None,
            "position_id": None,  # mapped later by fill ingester
            "leg_id": None,  # mapped later by fill ingester
            "raw_json": json.dumps(order),
            "meta_json": json.dumps({"source": "felix", "raw_symbol": symbol}),
        })

    return fills


# ---------------------------------------------------------------------------
# Connector Class
# ---------------------------------------------------------------------------


class FelixPrivateConnector(PrivateConnectorBase):
    """Private connector for Felix equities using JWT auth.

    Requires a valid Turnkey JWT. Use felix_auth.py to obtain/refresh.
    """

    def __init__(
        self,
        *,
        jwt: str,
        wallet_address: str,
    ):
        super().__init__("felix")
        self.jwt = jwt.strip()
        self.wallet_address = wallet_address.strip().lower()
        if not self.jwt:
            raise RuntimeError("Felix JWT is required")
        if not self.wallet_address:
            raise RuntimeError("Felix wallet address is required")

    def fetch_account_snapshot(self) -> Dict:
        """Fetch Felix portfolio snapshot.

        GET /v1/portfolio/{address}
        """
        raw = _felix_get(
            f"/v1/portfolio/{self.wallet_address}",
            self.jwt,
        )
        parsed = _parse_portfolio_response(raw, self.wallet_address)
        return {
            "account_id": parsed["account_id"],
            "total_balance": parsed["total_balance"],
            "available_balance": parsed["available_balance"],
            "margin_balance": parsed["total_balance"],
            "unrealized_pnl": None,
            "position_value": None,
            "raw_json": parsed["raw_json"],
        }

    def fetch_open_positions(self) -> List[Dict]:
        """Fetch Felix open positions.

        Derives from portfolio endpoint since Felix exposes positions there.
        """
        raw = _felix_get(
            f"/v1/portfolio/{self.wallet_address}",
            self.jwt,
        )
        parsed = _parse_portfolio_response(raw, self.wallet_address)

        out = []
        for p in parsed["positions"]:
            out.append({
                "leg_id": f"felix:{self.wallet_address}:{p['inst_id']}:{p['side']}",
                "position_id": "",
                "inst_id": p["inst_id"],
                "side": p["side"],
                "size": p["size"],
                "entry_price": p["entry_price"],
                "current_price": p["current_price"],
                "unrealized_pnl": p["unrealized_pnl"],
                "realized_pnl": None,
                "raw_json": p.get("raw", {}),
            })
        return out

    def fetch_fills(
        self,
        *,
        since_ms: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch Felix trade fills (from orders endpoint).

        GET /v1/trading/orders

        Returns list of fill dicts compatible with pm_fills schema.
        """
        params = {}
        if since_ms:
            from datetime import datetime, timezone
            dt = datetime.fromtimestamp(since_ms / 1000, tz=timezone.utc)
            params["since"] = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        raw = _felix_get("/v1/trading/orders", self.jwt, params=params)
        return _parse_fills_response(raw, self.wallet_address)

    def fetch_portfolio(self) -> Dict[str, Any]:
        """Fetch full portfolio data (convenience method).

        Returns parsed portfolio dict with positions, balances.
        """
        raw = _felix_get(
            f"/v1/portfolio/{self.wallet_address}",
            self.jwt,
        )
        return _parse_portfolio_response(raw, self.wallet_address)
