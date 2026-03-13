"""Paradex private connector (account + positions).

Supported credential modes:

1) **Readonly JWT token** (recommended for monitoring):
   - Set `PARADEX_JWT` (or `PARADEX_READONLY_TOKEN`) to the read-only token generated in Paradex UI.
   - This is sufficient for GET endpoints like `/v1/account` and `/v1/positions`.

2) **Trading key / subkey** (future):
   - Paradex supports generating JWT tokens via signed auth flows.
   - We are NOT implementing key-based JWT generation yet (needs signing utilities).

Optional:
- `PARADEX_ACCOUNT_ADDRESS` can be set to help tagging the account if API omits it.

API base (prod): https://api.prod.paradex.trade/v1
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Dict, List, Optional

from .private_base import PrivateConnectorBase

BASE_URL = "https://api.prod.paradex.trade/v1"


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def _get(path: str, jwt: str, timeout: int = 30) -> Dict[str, Any]:
    url = BASE_URL + path
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {jwt}",
            "User-Agent": "arbit-paradex-private/0.1",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


class ParadexPrivateConnector(PrivateConnectorBase):
    """Private connector for Paradex using Bearer JWT."""

    def __init__(self):
        super().__init__("paradex")
        self.jwt = (os.environ.get("PARADEX_JWT") or os.environ.get("PARADEX_READONLY_TOKEN") or "").strip()
        self.account_address = (os.environ.get("PARADEX_ACCOUNT_ADDRESS") or "").strip()
        if not self.jwt:
            raise RuntimeError(
                "Paradex credentials missing. Set PARADEX_JWT (recommended: readonly token) or PARADEX_READONLY_TOKEN."
            )

    def fetch_account_snapshot(self) -> Dict:
        """Fetch current account snapshot from Paradex (GET /v1/account)."""
        acct = _get("/account", self.jwt)

        # Paradex fields are strings; normalize to floats where useful.
        total_collateral = _to_float(acct.get("total_collateral"))
        account_value = _to_float(acct.get("account_value"))
        free_collateral = _to_float(acct.get("free_collateral"))

        snapshot = {
            "account_id": acct.get("account") or self.account_address or "",
            "total_balance": total_collateral if total_collateral is not None else account_value,
            "available_balance": free_collateral,
            "margin_balance": account_value,
            "unrealized_pnl": None,  # not directly provided; positions endpoint has uPnL
            "position_value": None,
            "raw_json": acct,
        }

        # Optional endpoints exist on Paradex; best-effort enrich.
        for extra_path in ("/balance", "/balances"):
            try:
                extra = _get(extra_path, self.jwt)
                # store in raw_json for future parsing
                snapshot["raw_json"][extra_path.lstrip("/")] = extra
                break
            except Exception:
                continue

        return snapshot

    def fetch_open_positions(self) -> List[Dict]:
        """Fetch all open positions from Paradex (GET /v1/positions)."""
        data = _get("/positions", self.jwt)
        rows = data.get("results") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return []

        out: List[Dict[str, Any]] = []
        for r in rows:
            if not isinstance(r, dict):
                continue

            status = (r.get("status") or "").upper()
            if status and status not in ("OPEN", "CLOSING"):
                # ignore closed positions
                continue

            side = (r.get("side") or "").upper()
            size_raw = _to_float(r.get("size"))
            size = abs(size_raw) if size_raw is not None else 0.0

            pos_id = r.get("id") or r.get("position_id") or ""
            market = r.get("market") or ""

            # Get current_price from public orderbook (best-effort)
            current_price = None
            try:
                from . import paradex_public
                ob = paradex_public.get_orderbook(market, timeout_s=3)
                mid = ob.get("mid")
                if mid is not None and mid > 0:
                    current_price = float(mid)
            except Exception:
                # Best-effort: if orderbook fails, continue without price
                pass

            out.append(
                {
                    "leg_id": f"paradex:{pos_id}" if pos_id else f"paradex:{market}:{side}",
                    "position_id": "",  # mapping to managed position happens in risk/reconciliation later
                    "inst_id": market,
                    "side": "LONG" if side == "LONG" else "SHORT" if side == "SHORT" else side,
                    "size": float(size),
                    "entry_price": _to_float(r.get("average_entry_price")) or _to_float(r.get("average_entry_price_usd")),
                    "current_price": current_price,
                    "unrealized_pnl": _to_float(r.get("unrealized_pnl")),
                    "realized_pnl": _to_float(r.get("realized_positional_pnl")),
                    "raw_json": r,
                }
            )

        return out

    def fetch_funding_payments(
        self,
        market: str,
        *,
        start_at_ms: Optional[int] = None,
        end_at_ms: Optional[int] = None,
        page_size: int = 500,
        max_pages: int = 20,
    ) -> List[Dict[str, Any]]:
        """Fetch funding payments history for a given market.

        Endpoint: GET /v1/funding/payments?market=...&start_at=...&end_at=...
        Returns list of raw payment objects.
        """
        out: List[Dict[str, Any]] = []
        cursor: Optional[str] = None

        for _ in range(max_pages):
            params: Dict[str, Any] = {"market": market, "page_size": int(page_size)}
            if start_at_ms is not None:
                params["start_at"] = int(start_at_ms)
            if end_at_ms is not None:
                params["end_at"] = int(end_at_ms)
            if cursor:
                params["cursor"] = cursor

            # paradex private _get doesn't currently accept params, so build URL manually
            import urllib.parse
            import urllib.request

            url = BASE_URL + "/funding/payments" + "?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.jwt}",
                    "User-Agent": "arbit-paradex-private/0.1",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw) if raw else {}

            rows = data.get("results") if isinstance(data, dict) else None
            if isinstance(rows, list):
                out.extend([r for r in rows if isinstance(r, dict)])

            cursor = data.get("next") if isinstance(data, dict) else None
            if not cursor:
                break

        return out
