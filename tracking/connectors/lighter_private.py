"""Lighter account + positions connector (perp + spot).

For monitoring we can query Lighter using just the **L1 address** (no trading key required).

Environment variables:
- `LIGHTER_L1_ADDRESS` (optional)
- `ETHEREAL_ACCOUNT_ADDRESS` (fallback; Bean uses a single address across venues)

Endpoints used (mainnet): https://mainnet.zklighter.elliot.ai
- GET `/api/v1/account?by=l1_address&value=<address>` (returns positions + spot assets)
- GET `/api/v1/orderBooks` (map market_id <-> symbol, spot vs perp)
- GET `/api/v1/orderBookDetails?market_id=<id>` (last_trade_price as price proxy)

Spot handling:
- Spot balances come from `assets[]` in the account response.
- We represent spot legs as `inst_id = "<SYMBOL>/USDC"` (e.g., `LIT/USDC`).

Note: Trading/auth-token flows exist in Lighter, but not needed for this monitoring connector.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from .private_base import PrivateConnectorBase

BASE_URL = "https://mainnet.zklighter.elliot.ai"


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
            "User-Agent": "arbit-lighter-monitor/0.1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except Exception as e:
        # Best-effort parse HTTP error bodies (Lighter often returns JSON with {code,message}).
        try:
            from urllib.error import HTTPError

            if isinstance(e, HTTPError):
                body = e.read().decode("utf-8")
                j = json.loads(body) if body else {}
                if isinstance(j, dict):
                    j.setdefault("http_status", e.code)
                    return j
        except Exception:
            pass
        raise


def _orderbooks_index() -> Tuple[Dict[int, Dict[str, Any]], Dict[str, int]]:
    """Return (market_id->book, symbol->market_id) for all markets."""
    data = _get("/api/v1/orderBooks")
    books = data.get("order_books") if isinstance(data, dict) else None
    if not isinstance(books, list):
        return {}, {}

    by_id: Dict[int, Dict[str, Any]] = {}
    by_sym: Dict[str, int] = {}
    for b in books:
        try:
            mid = int(b.get("market_id"))
        except Exception:
            continue
        sym = b.get("symbol")
        by_id[mid] = b
        if sym:
            by_sym[str(sym)] = mid
    return by_id, by_sym


def _last_trade_price(market_id: int) -> Optional[float]:
    """Get last trade price.

    Notes:
    - Perp markets populate `order_book_details`.
    - Spot markets populate `spot_order_book_details`.
    - If last_trade_price is missing, we try to fallback to a mid from bid/ask fields.
    """
    data = _get("/api/v1/orderBookDetails", {"market_id": str(market_id)})
    if not isinstance(data, dict):
        return None

    # Try perp details first
    rows = data.get("order_book_details")
    if isinstance(rows, list) and rows:
        d = rows[0]
        last_px = _to_float(d.get("last_trade_price"))
        if last_px is not None:
            return last_px

        bid = _to_float(d.get("highest_bid"))
        ask = _to_float(d.get("lowest_ask"))
        if bid is not None and ask is not None:
            return (bid + ask) / 2.0
        if bid is not None:
            return bid
        if ask is not None:
            return ask

    # Spot details
    srows = data.get("spot_order_book_details")
    if isinstance(srows, list) and srows:
        d = srows[0]
        last_px = _to_float(d.get("last_trade_price"))
        if last_px is not None:
            return last_px

        # Some spot payloads may expose best bid/ask too
        bid = _to_float(d.get("highest_bid"))
        ask = _to_float(d.get("lowest_ask"))
        if bid is not None and ask is not None:
            return (bid + ask) / 2.0
        if bid is not None:
            return bid
        if ask is not None:
            return ask

    return None


class LighterPrivateConnector(PrivateConnectorBase):
    """Connector for Lighter that fetches perp positions and spot balances."""

    def __init__(self):
        super().__init__("lighter")
        self.l1_address = (os.environ.get("LIGHTER_L1_ADDRESS") or os.environ.get("ETHEREAL_ACCOUNT_ADDRESS") or "").strip()
        if not self.l1_address:
            raise RuntimeError(
                "Lighter credentials missing. Set LIGHTER_L1_ADDRESS or (fallback) ETHEREAL_ACCOUNT_ADDRESS."
            )

        # Readonly token for funding API (set via environment)
        # This is a permanent token that doesn't expire
        self.readonly_token = os.environ.get("LIGHTER_READONLY_TOKEN", "").strip()

        self._by_market_id, self._by_symbol = _orderbooks_index()
        self._account_index = None  # Lazy fetch

    def _fetch_account_raw(self) -> Dict[str, Any]:
        data = _get("/api/v1/account", {"by": "l1_address", "value": self.l1_address})
        # Expected shape: {code, message?, total, accounts:[...]}
        code = data.get("code")
        if code not in (200, "200", None):
            # Lighter uses numeric codes in body sometimes.
            msg = data.get("message") or f"code={code}"
            raise RuntimeError(f"Lighter API error: {msg}")
        return data

    def fetch_account_snapshot(self) -> Dict:
        raw = self._fetch_account_raw()
        accounts = raw.get("accounts") if isinstance(raw, dict) else None
        if not isinstance(accounts, list) or not accounts:
            raise RuntimeError("Lighter account not found (no accounts returned)")

        total_balance = 0.0
        available_balance = 0.0
        unrealized_pnl = 0.0
        position_value = 0.0

        for a in accounts:
            if not isinstance(a, dict):
                continue
            total_balance += float(_to_float(a.get("collateral")) or 0.0)
            available_balance += float(_to_float(a.get("available_balance")) or 0.0)

            # Sum perp position metrics
            for p in (a.get("positions") or []):
                if not isinstance(p, dict):
                    continue
                unrealized_pnl += float(_to_float(p.get("unrealized_pnl")) or 0.0)
                position_value += float(abs(_to_float(p.get("position_value")) or 0.0))

        return {
            "account_id": self.l1_address,
            "total_balance": total_balance,
            "available_balance": available_balance,
            "margin_balance": total_balance,
            "unrealized_pnl": unrealized_pnl,
            "position_value": position_value,
            "raw_json": raw,
        }

    def fetch_open_positions(self) -> List[Dict]:
        raw = self._fetch_account_raw()
        accounts = raw.get("accounts") if isinstance(raw, dict) else None
        if not isinstance(accounts, list) or not accounts:
            return []

        out: List[Dict[str, Any]] = []

        # 1) Perp positions
        for a in accounts:
            if not isinstance(a, dict):
                continue
            acct_idx = a.get("index")
            for p in (a.get("positions") or []):
                if not isinstance(p, dict):
                    continue

                pos_qty = _to_float(p.get("position"))
                if not pos_qty or abs(pos_qty) == 0:
                    continue

                sign = int(p.get("sign") or (1 if pos_qty > 0 else -1))
                side = "LONG" if sign == 1 else "SHORT"

                market_id = int(p.get("market_id"))
                inst_id = str(p.get("symbol"))
                px = _last_trade_price(market_id)

                out.append(
                    {
                        "leg_id": f"lighter:{self.l1_address}:{acct_idx}:perp:{market_id}",
                        "position_id": "",
                        "inst_id": inst_id,
                        "side": side,
                        "size": float(abs(pos_qty)),
                        "entry_price": _to_float(p.get("avg_entry_price")),
                        "current_price": px,
                        "unrealized_pnl": _to_float(p.get("unrealized_pnl")),
                        "realized_pnl": _to_float(p.get("realized_pnl")),
                        "raw_json": p,
                    }
                )

        # 2) Spot balances (assets)
        for a in accounts:
            if not isinstance(a, dict):
                continue
            acct_idx = a.get("index")
            for asst in (a.get("assets") or []):
                if not isinstance(asst, dict):
                    continue
                sym = str(asst.get("symbol") or "").strip()
                if not sym:
                    continue

                bal = _to_float(asst.get("balance")) or 0.0
                locked = _to_float(asst.get("locked_balance")) or 0.0
                if bal == 0 and locked == 0:
                    continue

                # Represent spot market as <SYM>/USDC (consistent with orderBooks)
                spot_market = sym if "/" in sym else f"{sym}/USDC"
                mid = None
                mid_id = self._by_symbol.get(spot_market)
                if mid_id is not None:
                    mid = _last_trade_price(int(mid_id))

                out.append(
                    {
                        "leg_id": f"lighter:{self.l1_address}:{acct_idx}:spot:{spot_market}",
                        "position_id": "",
                        "inst_id": spot_market,
                        "side": "LONG",
                        "size": float(bal),
                        "entry_price": None,
                        "current_price": mid,
                        "unrealized_pnl": None,
                        "realized_pnl": None,
                        "raw_json": asst,
                    }
                )

        return out

    def _get_account_index(self) -> Optional[int]:
        """Lazy fetch account index from account API."""
        if self._account_index is not None:
            return self._account_index

        raw = self._fetch_account_raw()
        accounts = raw.get("accounts") if isinstance(raw, dict) else None
        if isinstance(accounts, list) and accounts:
            self._account_index = int(accounts[0].get("index", 0))
        return self._account_index

    def fetch_funding_history(self, limit: int = 100, side: str = "all") -> List[Dict[str, Any]]:
        """Fetch funding history from Lighter API.

        Args:
            limit: Number of records to fetch (default 100)
            side: Filter by "long", "short", or "all" (default "all")

        Returns:
            List of funding records with timestamp, market_id, change, rate, etc.
        """
        account_idx = self._get_account_index()
        if not account_idx:
            raise RuntimeError("Cannot get account index for funding API")

        # Use readonly token for funding API (permanent, doesn't expire)
        if not self.readonly_token:
            raise RuntimeError("Lighter readonly token missing. Set LIGHTER_READONLY_TOKEN.")
        
        url = f"{BASE_URL}/api/v1/positionFunding"
        params = {
            "account_index": str(account_idx),
            "limit": str(limit),
            "side": side,
        }
        url = url + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": self.readonly_token,
                "User-Agent": "arbit-lighter-monitor/0.1",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw) if raw else {}
                if isinstance(data, dict) and data.get("code") == 200:
                    return data.get("position_fundings", [])
        except Exception as e:
            raise RuntimeError(f"Lighter funding API error: {e}")

        return []
