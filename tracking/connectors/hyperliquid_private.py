"""Hyperliquid account/positions connector.

Hyperliquid exposes user state via public POST endpoints; for monitoring we only
need the user's address. Builder-deployed perp dexes use the same API surface
with an additional `dex` name.

Environment variables:
- `HYPERLIQUID_ADDRESS` (optional)
- `HYPERLIQUID_DEX` (optional; default = base dex)
- `ETHEREAL_ACCOUNT_ADDRESS` (fallback)

Endpoints (prod): https://api.hyperliquid.xyz
- POST /info {"type":"clearinghouseState","user":"0x...","dex":"xyz"}
- POST /info {"type":"allMids","dex":"xyz"} (price proxy)
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from .private_base import PrivateConnectorBase

BASE_URL = "https://api.hyperliquid.xyz"
DEFAULT_DEX = ""


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def split_inst_id(inst_id: str) -> Tuple[str, str]:
    raw = str(inst_id or "").strip()
    if ":" in raw:
        dex, coin = raw.split(":", 1)
        return dex.strip(), coin.strip()
    return DEFAULT_DEX, raw


def strip_coin_namespace(coin: str) -> str:
    return str(coin or "").strip().split(":")[-1]


def namespaced_inst_id(*, dex: str, coin: str) -> str:
    base = strip_coin_namespace(coin)
    if not base:
        return ""
    dex = str(dex or "").strip()
    return f"{dex}:{base}" if dex else base


def _post(path: str, payload: Dict[str, Any], timeout: int = 30) -> Any:
    url = BASE_URL + path
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "arbit-hyperliquid-monitor/0.1",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else None


def post_info(payload: Dict[str, Any], *, dex: str = DEFAULT_DEX, timeout: int = 30) -> Any:
    body = dict(payload)
    dex = str(dex or "").strip()
    if dex:
        body["dex"] = dex
    return _post("/info", body, timeout=timeout)


def _all_mids(*, dex: str = DEFAULT_DEX) -> Dict[str, float]:
    data = post_info({"type": "allMids"}, dex=dex)
    if not isinstance(data, dict):
        return {}
    out: Dict[str, float] = {}
    for k, v in data.items():
        fv = _to_float(v)
        if fv is not None:
            out[strip_coin_namespace(str(k))] = float(fv)
    return out


class HyperliquidPrivateConnector(PrivateConnectorBase):
    """Monitoring connector for Hyperliquid and builder perp dexes."""

    def __init__(self, *, address: Optional[str] = None):
        super().__init__("hyperliquid")
        if address:
            self.address = address.strip()
        else:
            self.address = (
                os.environ.get("HYPERLIQUID_ADDRESS")
                or os.environ.get("ETHEREAL_ACCOUNT_ADDRESS")
                or ""
            ).strip()
        self.dex = (os.environ.get("HYPERLIQUID_DEX") or DEFAULT_DEX).strip()
        if not self.address:
            raise RuntimeError(
                "Hyperliquid config missing. Set HYPERLIQUID_ADDRESS or (fallback) ETHEREAL_ACCOUNT_ADDRESS."
            )

    def fetch_account_snapshot(self, *, dex: Optional[str] = None) -> Dict:
        use_dex = self.dex if dex is None else str(dex or "").strip()
        st = post_info({"type": "clearinghouseState", "user": self.address}, dex=use_dex)
        if not isinstance(st, dict):
            raise RuntimeError("Unexpected Hyperliquid response (not dict)")

        ms = st.get("marginSummary") or {}
        account_value = _to_float(ms.get("accountValue"))
        total_margin_used = _to_float(ms.get("totalMarginUsed"))

        free = None
        if account_value is not None and total_margin_used is not None:
            free = account_value - total_margin_used

        return {
            "account_id": self.address,
            "dex": use_dex,
            "total_balance": account_value,
            "available_balance": free,
            "margin_balance": account_value,
            "unrealized_pnl": None,
            "position_value": _to_float(ms.get("totalNtlPos")),
            "raw_json": st,
        }

    def fetch_open_positions(self, *, dex: Optional[str] = None) -> List[Dict]:
        use_dex = self.dex if dex is None else str(dex or "").strip()
        st = post_info({"type": "clearinghouseState", "user": self.address}, dex=use_dex)
        if not isinstance(st, dict):
            return []

        mids = _all_mids(dex=use_dex)

        aps = st.get("assetPositions") or []
        if not isinstance(aps, list):
            return []

        out: List[Dict[str, Any]] = []
        for it in aps:
            if not isinstance(it, dict):
                continue
            p = it.get("position") or {}
            if not isinstance(p, dict):
                continue

            coin_raw = p.get("coin")
            coin = strip_coin_namespace(str(coin_raw or ""))
            if not coin:
                continue

            szi = _to_float(p.get("szi"))
            if not szi or abs(szi) == 0:
                continue

            side = "LONG" if szi > 0 else "SHORT"
            size = abs(szi)
            entry_px = _to_float(p.get("entryPx"))
            u_pnl = _to_float(p.get("unrealizedPnl"))
            liq_px = _to_float(p.get("liquidationPx"))
            mark = mids.get(str(coin))

            cum_funding = p.get("cumFunding") or {}
            if isinstance(cum_funding, dict):
                for key in ["allTime", "sinceOpen", "sinceChange"]:
                    if key in cum_funding and cum_funding[key]:
                        val = _to_float(cum_funding[key])
                        if val is not None and side == "SHORT":
                            cum_funding[key] = -val

            raw = dict(p)
            if liq_px is not None:
                raw["liquidation_price"] = liq_px

            inst_id = namespaced_inst_id(dex=use_dex, coin=coin)
            out.append(
                {
                    "leg_id": f"hyperliquid:{self.address}:{inst_id}:{side}",
                    "position_id": "",
                    "inst_id": inst_id,
                    "side": side,
                    "size": float(size),
                    "entry_price": entry_px,
                    "current_price": mark,
                    "unrealized_pnl": u_pnl,
                    "realized_pnl": None,
                    "raw_json": raw,
                }
            )

        return out
