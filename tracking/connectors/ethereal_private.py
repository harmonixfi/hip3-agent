"""Ethereal account/positions connector.

Ethereal exposes account-scoped endpoints that are queryable by **sender address** and **subaccountId**.
For monitoring we don't need trading auth; we just need to know your account address.

Environment variables:
- `ETHEREAL_ACCOUNT_ADDRESS` (or `ETHEREAL_SENDER`) — EVM address (0x...)
- Optional: `ETHEREAL_SUBACCOUNT_ID` — restrict to a single subaccount UUID

Endpoints used (prod): https://api.ethereal.trade
- GET /v1/subaccount?sender=<address>
- GET /v1/subaccount/balance?subaccountId=<uuid>
- GET /v1/position?subaccountId=<uuid>&open=true
- GET /v1/product/market-price?productIds=<uuid> (for oraclePrice)

Note: For order placement/mutations, Ethereal uses EIP-712 signing; not implemented here.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from .private_base import PrivateConnectorBase
from . import ethereal_public

BASE_URL = "https://api.ethereal.trade"


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def _get(path: str, params: Optional[Dict[str, Any]] = None, timeout: int = 30) -> Dict[str, Any]:
    url = BASE_URL + path
    if params:
        url = url + "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "arbit-ethereal-monitor/0.1",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _product_id_to_symbol_map() -> Dict[str, str]:
    """Map product UUID -> ticker symbol (inst_id) via public instruments endpoint."""
    m = {}
    try:
        insts = ethereal_public.get_instruments(force_refresh=False)
        for it in insts:
            pid = it.get("inst_id")
            sym = it.get("symbol")
            if pid and sym:
                m[str(pid)] = str(sym)
    except Exception:
        pass
    return m


def _market_prices(product_ids: List[str]) -> Dict[str, float]:
    """Fetch oraclePrice for product ids. Returns productId -> oraclePrice."""
    if not product_ids:
        return {}

    data = _get("/v1/product/market-price", {"productIds": product_ids})
    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return {}

    out: Dict[str, float] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        pid = r.get("productId") or r.get("product_id") or r.get("id")
        op = _to_float(r.get("oraclePrice"))
        if pid and op is not None:
            out[str(pid)] = float(op)
    return out


class EtherealPrivateConnector(PrivateConnectorBase):
    """Connector for Ethereal that fetches subaccount balances + positions."""

    def __init__(self, *, address: Optional[str] = None):
        super().__init__("ethereal")
        self.sender = (
            address
            or os.environ.get("ETHEREAL_ACCOUNT_ADDRESS")
            or os.environ.get("ETHEREAL_SENDER")
            or ""
        ).strip()
        self.subaccount_id = os.environ.get("ETHEREAL_SUBACCOUNT_ID", "").strip()
        if not self.sender:
            raise RuntimeError("Ethereal config missing. Set ETHEREAL_ACCOUNT_ADDRESS or ETHEREAL_SENDER.")

    def _subaccounts(self) -> List[Dict[str, Any]]:
        data = _get("/v1/subaccount", {"sender": self.sender, "order": "desc", "limit": 200})
        rows = data.get("data") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return []
        if self.subaccount_id:
            rows = [r for r in rows if str(r.get("id")) == self.subaccount_id]
        return rows

    def fetch_account_snapshot(self) -> Dict:
        """Fetch a rollup account snapshot (sum across subaccounts, USD-like units)."""
        subs = self._subaccounts()

        total_balance = 0.0
        available_balance = 0.0
        margin_used = 0.0
        raw = {"sender": self.sender, "subaccounts": subs, "balances": []}

        for s in subs:
            sid = s.get("id")
            if not sid:
                continue
            bal = _get("/v1/subaccount/balance", {"subaccountId": sid, "limit": 200, "order": "desc"})
            rows = bal.get("data") if isinstance(bal, dict) else None
            if not isinstance(rows, list):
                continue
            raw["balances"].append({"subaccountId": sid, "data": rows})

            # Most accounts will have a single settlement token row; sum all rows anyway.
            for r in rows:
                total_balance += float(_to_float(r.get("amount")) or 0.0)
                available_balance += float(_to_float(r.get("available")) or 0.0)
                margin_used += float(_to_float(r.get("totalUsed")) or 0.0)

        return {
            "account_id": self.sender,
            "total_balance": total_balance,
            "available_balance": available_balance,
            "margin_balance": total_balance,
            "unrealized_pnl": None,
            "position_value": None,
            "raw_json": {"rollup": {"margin_used": margin_used}, **raw},
        }

    def fetch_open_positions(self) -> List[Dict]:
        """Fetch open positions across subaccounts."""
        subs = self._subaccounts()
        pid2sym = _product_id_to_symbol_map()

        # Collect raw positions
        positions_raw: List[Dict[str, Any]] = []
        product_ids: List[str] = []

        for s in subs:
            sid = s.get("id")
            if not sid:
                continue
            data = _get("/v1/position", {"subaccountId": sid, "open": "true", "limit": 200, "order": "desc"})
            rows = data.get("data") if isinstance(data, dict) else None
            if not isinstance(rows, list):
                continue
            for r in rows:
                if not isinstance(r, dict):
                    continue
                positions_raw.append({"subaccountId": sid, **r})
                if r.get("productId"):
                    product_ids.append(str(r.get("productId")))

        prices = _market_prices(sorted(set(product_ids)))

        out: List[Dict[str, Any]] = []
        for r in positions_raw:
            pid = str(r.get("productId") or "")
            sym = pid2sym.get(pid) or pid

            size_raw = _to_float(r.get("size")) or 0.0
            size = abs(size_raw)

            side_num = r.get("side")
            side = "SHORT" if (size_raw < 0 or side_num == 1) else "LONG"

            # average entry price approx
            inc_notional = _to_float(r.get("totalIncreaseNotional"))
            inc_qty = _to_float(r.get("totalIncreaseQuantity"))
            entry_price = (inc_notional / inc_qty) if (inc_notional and inc_qty) else None

            current_price = prices.get(pid)

            out.append(
                {
                    "leg_id": f"ethereal:{r.get('subaccountId')}:{pid}:{side}",
                    "position_id": "",
                    "inst_id": sym,
                    "side": side,
                    "size": float(size),
                    "entry_price": entry_price,
                    "current_price": current_price,
                    "unrealized_pnl": None,
                    "realized_pnl": _to_float(r.get("realizedPnl")),
                    "raw_json": r,
                }
            )

        return out
