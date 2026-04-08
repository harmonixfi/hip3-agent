"""Felix equities private connector.

Provides access to Felix equity portfolio, orders, and fills via the Felix
proxy API. Requires a valid JWT from the Turnkey auth flow (felix_auth.py).

Felix API is accessed through the Cloudflare Workers proxy:
    https://spot-equities-proxy.white-star-bc1e.workers.dev

All endpoints require Authorization: Bearer <jwt> header.

Usage:
    from tracking.connectors.felix_private import FelixPrivateConnector

    # If the proxy only accepts a different path address than your ledger wallet, set both:
    connector = FelixPrivateConnector(
        jwt="eyJ...",
        wallet_address="0x...",  # ledger — pm_account_snapshots.account_id, DN merge
        api_account_address="0x...",  # optional — GET /v1/portfolio/{api}/... ; default: wallet_address
    )
    portfolio = connector.fetch_portfolio()
    fills = connector.fetch_fills()
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
import urllib.parse
from typing import Any, Dict, List, Optional

from .private_base import PrivateConnectorBase

_logger = logging.getLogger(__name__)

FELIX_PROXY_BASE = "https://spot-equities-proxy.white-star-bc1e.workers.dev"

# Operator-facing log lines (no secrets). Shown on HTTP errors from the proxy.
_FELIX_HINT_401 = (
    "Hint: refresh FELIX_EQUITIES_JWT in .arbit_env (expired or invalid bearer)."
)
_FELIX_HINT_403 = (
    "Hint: 403 — JWT may not be authorized for this wallet or endpoint; "
    "refresh the token and confirm FELIX_WALLET_ADDRESS matches your Felix account. "
    "See docs/felix-turnkey-auth-handoff.md."
)
_FELIX_HINT_WRONG_WALLET = (
    "Hint: FELIX_WALLET_ADDRESS must be the Felix/Turnkey wallet this JWT is issued for "
    "(same as /v1/portfolio/{address} in the Felix app). It is often not your Hyperliquid address."
)


def _felix_hint_from_error_body(body: str) -> str:
    """Map proxy JSON error body to a specific operator hint (no secrets)."""
    if not body:
        return ""
    low = body.lower()
    if "another account" in low or "cannot access" in low:
        return _FELIX_HINT_WRONG_WALLET
    return ""


def felix_operator_hint_for_http_error(exc: BaseException) -> str:
    """Return a short log line for operators when Felix HTTP fails (no JWT body)."""
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 401:
            return _FELIX_HINT_401
        if exc.code == 403:
            return _FELIX_HINT_403
    return ""


def felix_operator_hint_for_error_message(msg: str) -> str:
    """Best-effort hint when only the aggregated error string is available (e.g. puller)."""
    m = (msg or "").lower()
    if "another account" in m or "cannot access" in m:
        return _FELIX_HINT_WRONG_WALLET
    if " 401" in m or "unauthorized" in m:
        return _FELIX_HINT_401
    if " 403" in m or "forbidden" in m:
        return _FELIX_HINT_403
    return ""


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

    _logger.info("Felix GET %s", url)

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {jwt}",
            "User-Agent": "arbit-felix-private/0.1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = ""
        server_msg = ""
        try:
            parsed = json.loads(body_text) if body_text else {}
            if isinstance(parsed, dict):
                server_msg = str(parsed.get("message") or "").strip()
        except (json.JSONDecodeError, TypeError):
            server_msg = body_text[:300].strip() if body_text else ""

        hint = _felix_hint_from_error_body(body_text) or felix_operator_hint_for_http_error(e)
        tail = f" {hint}" if hint else ""
        detail = f" — {server_msg}" if server_msg else ""
        raise RuntimeError(
            f"Felix HTTP {e.code} {e.reason} url={url}{detail}.{tail}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Felix request failed (network) url={url}: {e.reason}. "
            "Hint: check outbound HTTPS to the Felix proxy."
        ) from e


# ---------------------------------------------------------------------------
# Response Parsers (module-level for testability)
# ---------------------------------------------------------------------------


def _first_float_keys(d: Dict[str, Any], *keys: str) -> Optional[float]:
    """Return first present numeric value for any of the given keys."""
    for k in keys:
        v = _to_float(d.get(k))
        if v is not None:
            return v
    return None


# Felix/proxy payloads vary; never treat avg entry or cost as a live mark here.
_FELIX_LIVE_MARK_KEYS = (
    "currentPrice",
    "markPrice",
    "lastPrice",
    "last_price",
    "dexMidPrice",
    "indexPrice",
    "marketPrice",
    "spotPrice",
    "midPrice",
    "oraclePrice",
    "price",
    "usdPrice",
    "priceUsd",
    "mark_price",
    "fairPrice",
    "livePrice",
    "lastTradePrice",
    "tradePrice",
    "quotedPrice",
    "navPrice",
    "fairMarketValue",
)


def _felix_mark_from_position_raw(rj: Dict[str, Any]) -> Optional[float]:
    """Best-effort live mark from one position dict (not entry/costBasis)."""
    if not isinstance(rj, dict):
        return None
    m = _first_float_keys(rj, *_FELIX_LIVE_MARK_KEYS)
    if m is not None:
        return m
    for nest in ("market", "valuation", "quote", "pricing"):
        sub = rj.get(nest)
        if isinstance(sub, dict):
            m = _first_float_keys(sub, *_FELIX_LIVE_MARK_KEYS)
            if m is not None:
                return m
    return None


def _stablecoin_balance_usd(raw: Dict[str, Any]) -> Optional[float]:
    """Felix may send ``stablecoinBalance`` as a number or ``{usdValue, amount}``."""
    sc = raw.get("stablecoinBalance") or raw.get("stablecoin_balance")
    if sc is None:
        return None
    if isinstance(sc, dict):
        return _first_float_keys(sc, "usdValue", "amount", "value", "usd")
    return _to_float(sc)


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

    Production payloads vary: ``accountValue`` vs rolled-up cash (``stablecoinBalance``)
    and per-position ``costBasisUsd`` / ``markPrice`` — we coalesce sensible aliases.
    """
    positions = []
    for p in raw.get("positions", []):
        if not isinstance(p, dict):
            continue
        symbol = str(p.get("symbol", ""))
        inst_id = _normalize_felix_inst_id(symbol)
        if not inst_id:
            continue

        size = _to_float(p.get("quantity") or p.get("qty") or p.get("size"))
        if size is None or size == 0:
            continue

        side = str(p.get("side", "")).upper()
        if side not in ("LONG", "SHORT"):
            side = "LONG"  # Felix equities are long by default

        entry = _first_float_keys(
            p,
            "averageEntryPrice",
            "average_entry_price",
            "avgEntryPrice",
        )
        if entry is None:
            cost_basis = _to_float(p.get("costBasisUsd") or p.get("cost_basis_usd"))
            if cost_basis is not None and abs(size) > 1e-12:
                entry = cost_basis / abs(size)

        # Live mark only — never use average cost as ``current_price``.
        mark = _first_float_keys(
            p,
            "currentPrice",
            "markPrice",
            "lastPrice",
            "last_price",
            "dexMidPrice",
            "indexPrice",
        )
        if mark is None:
            mark = _felix_mark_from_position_raw(p)

        positions.append({
            "inst_id": inst_id,
            "side": side,
            "size": abs(size),
            "entry_price": entry,
            "current_price": mark,
            "unrealized_pnl": _to_float(p.get("unrealizedPnl") or p.get("unrealized_pnl")),
            "raw": p,
        })

    total_balance = _first_float_keys(
        raw,
        "accountValue",
        "account_value",
        "totalAccountValue",
        "totalPortfolioValue",
        "portfolioValue",
        "netAssetValue",
    )
    if total_balance is None:
        stable = _stablecoin_balance_usd(raw) or 0.0
        pos_notional = 0.0
        for pos in positions:
            sz = pos.get("size") or 0.0
            m = pos.get("current_price")
            if m is not None and sz:
                pos_notional += float(sz) * float(m)
        cb_sum = 0.0
        for p in raw.get("positions", []):
            if not isinstance(p, dict):
                continue
            cb = _to_float(p.get("costBasisUsd") or p.get("cost_basis_usd"))
            if cb is not None:
                cb_sum += cb
        if pos_notional > 0:
            total_balance = stable + pos_notional
        elif stable > 0 or cb_sum > 0:
            total_balance = stable + cb_sum

    available_balance = _first_float_keys(
        raw,
        "availableBalance",
        "available_balance",
        "withdrawableBalance",
    )

    return {
        "account_id": wallet_address,
        "total_balance": total_balance,
        "available_balance": available_balance,
        "positions": positions,
        "raw_json": raw,
    }


def recompute_felix_account_total_usd(
    raw_json: Optional[Dict[str, Any]],
    positions: List[Dict[str, Any]],
    *,
    hl_marks_by_felix_inst_id: Optional[Dict[str, float]] = None,
) -> Optional[float]:
    """Roll up account USD total: stablecoin + Σ position MTM.

    For each leg, valuation is ``size × mark`` using in order:

    1. ``current_price`` from the connector
    2. Any live mark fields on ``raw_json`` (see ``_felix_mark_from_position_raw``)
    3. Optional ``hl_marks_by_felix_inst_id`` — HIP-3 hedge mid from ``prices_v3`` when
       Felix omits a mark (same underlying as the HL short; does not change stored leg marks)
    4. Last resort: ``costBasisUsd`` on the position (book cost, not a live mark)
    """
    raw = raw_json if isinstance(raw_json, dict) else {}
    stable = _stablecoin_balance_usd(raw) or 0.0
    pos_sum = 0.0
    hl = hl_marks_by_felix_inst_id or {}
    for p in positions:
        sz = _to_float(p.get("size"))
        if not sz:
            continue
        inst = (p.get("inst_id") or "").strip()
        rj = p.get("raw_json")
        if not isinstance(rj, dict):
            rj = {}

        m = _to_float(p.get("current_price"))
        if m is None:
            m = _felix_mark_from_position_raw(rj)
        if m is None and inst:
            m = _to_float(hl.get(inst))
        if m is not None:
            pos_sum += float(sz) * float(m)
            continue

        cb = _to_float(rj.get("costBasisUsd") or rj.get("cost_basis_usd"))
        if cb is not None:
            pos_sum += cb
    if stable <= 0 and pos_sum <= 0:
        return None
    return stable + pos_sum


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
        api_account_address: Optional[str] = None,
    ):
        super().__init__("felix")
        self.jwt = jwt.strip()
        self.ledger_address = wallet_address.strip().lower()
        self.api_address = (api_account_address or wallet_address).strip().lower()
        if not self.jwt:
            raise RuntimeError("Felix JWT is required")
        if not self.ledger_address:
            raise RuntimeError("Felix wallet address is required")
        if not self.api_address:
            raise RuntimeError("Felix API account address is required")

    def fetch_account_snapshot(self) -> Dict:
        """Fetch Felix portfolio snapshot.

        GET /v1/portfolio/{api_address}
        """
        raw = _felix_get(
            f"/v1/portfolio/{self.api_address}",
            self.jwt,
        )
        parsed = _parse_portfolio_response(raw, self.ledger_address)
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
            f"/v1/portfolio/{self.api_address}",
            self.jwt,
        )
        parsed = _parse_portfolio_response(raw, self.ledger_address)

        out = []
        for p in parsed["positions"]:
            out.append({
                "leg_id": f"felix:{self.ledger_address}:{p['inst_id']}:{p['side']}",
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
        return _parse_fills_response(raw, self.ledger_address)

    def fetch_portfolio(self) -> Dict[str, Any]:
        """Fetch full portfolio data (convenience method).

        Returns parsed portfolio dict with positions, balances.
        """
        raw = _felix_get(
            f"/v1/portfolio/{self.api_address}",
            self.jwt,
        )
        return _parse_portfolio_response(raw, self.ledger_address)
