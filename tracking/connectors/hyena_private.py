"""Hyena account/positions connector.

Hyena is currently treated as a separate Hyperliquid-style account in Bean's setup.
Implementation reuses Hyperliquid public /info endpoints (no auth; address-only).

Environment variables:
- `HYENA_ADDRESS` (required; EVM address)

Endpoints (prod): https://api.hyperliquid.xyz
- POST /info {"type":"clearinghouseState","user":"0x..."}
- POST /info {"type":"allMids"}

Note: This is monitoring-only.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Dict, List, Optional

from .private_base import PrivateConnectorBase

BASE_URL = "https://api.hyperliquid.xyz"

# Hyena is a builder-deployed perp dex on Hyperliquid.
# Dex name discovered via /info {type: "perpDexs"}. For HyENA it's typically "hyna".
DEFAULT_DEX = "hyna"


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def _post(path: str, payload: Dict[str, Any], timeout: int = 30) -> Any:
    url = BASE_URL + path
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "arbit-hyena-monitor/0.1",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else None


def _strip_coin(coin: str) -> str:
    c = (coin or "").strip()
    if ":" in c:
        return c.split(":")[-1]
    return c


def _all_mids(*, dex: str) -> Dict[str, float]:
    data = _post("/info", {"type": "allMids", "dex": dex})
    if not isinstance(data, dict):
        return {}
    out: Dict[str, float] = {}
    for k, v in data.items():
        fv = _to_float(v)
        if fv is None:
            continue
        coin = _strip_coin(str(k))
        if not coin:
            continue
        out[coin] = float(fv)
    return out


class HyenaPrivateConnector(PrivateConnectorBase):
    """Monitoring connector for Hyena (Hyperliquid-style)."""

    def __init__(self):
        super().__init__("hyena")
        self.address = (os.environ.get("HYENA_ADDRESS") or "").strip()
        self.dex = (os.environ.get("HYENA_DEX") or DEFAULT_DEX).strip() or DEFAULT_DEX
        if not self.address:
            raise RuntimeError("Hyena config missing. Set HYENA_ADDRESS.")

    def fetch_account_snapshot(self) -> Dict:
        # Perps state must be fetched with the Hyena perp dex.
        perps = _post("/info", {"type": "clearinghouseState", "user": self.address, "dex": self.dex})
        if not isinstance(perps, dict):
            raise RuntimeError("Unexpected Hyena perps response")

        ms = (perps.get("marginSummary") or {}) if isinstance(perps.get("marginSummary"), dict) else {}
        perps_equity = _to_float(ms.get("accountValue")) or 0.0
        total_margin_used = _to_float(ms.get("totalMarginUsed"))

        perps_free = None
        if total_margin_used is not None:
            perps_free = float(perps_equity) - float(total_margin_used)

        # Spot state + spot pricing contexts (webData2 is convenient for spotAssetCtxs).
        wd = _post("/info", {"type": "webData2", "user": self.address})
        if not isinstance(wd, dict):
            wd = {}

        spot = wd.get("spotState") or {}
        bals = spot.get("balances") or []

        px_map: Dict[str, float] = {}
        ctxs = wd.get("spotAssetCtxs")
        if isinstance(ctxs, list):
            for it in ctxs:
                if not isinstance(it, dict):
                    continue
                coin = str(it.get("coin") or "")
                if not coin:
                    continue
                base = coin.split("/")[0]
                mp = _to_float(it.get("midPx")) or _to_float(it.get("markPx"))
                if base and mp and mp > 0:
                    px_map[base] = float(mp)

        STABLE = {"USD", "USDC", "USDT", "USDE"}

        spot_equity = 0.0
        for b in bals:
            if not isinstance(b, dict):
                continue
            coin = str(b.get("coin") or "")
            tot = _to_float(b.get("total"))
            if not coin or tot is None:
                continue
            if coin.upper() in STABLE:
                spot_equity += float(tot)
            else:
                px = px_map.get(coin)
                if px is None:
                    ent = _to_float(b.get("entryNtl"))
                    if ent is not None:
                        spot_equity += float(ent)
                else:
                    spot_equity += float(tot) * float(px)

        total_equity = float(perps_equity) + float(spot_equity)

        return {
            "account_id": self.address,
            "total_balance": total_equity,
            "available_balance": perps_free,  # perps-only free; spot free not modeled
            "margin_balance": total_equity,
            "unrealized_pnl": None,
            "position_value": _to_float(ms.get("totalNtlPos")),
            "raw_json": {"perps": perps, "webData2": wd},
        }

    def fetch_open_positions(self) -> List[Dict]:
        st = _post("/info", {"type": "clearinghouseState", "user": self.address, "dex": self.dex})
        if not isinstance(st, dict):
            return []

        mids = _all_mids(dex=self.dex)
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
            coin = _strip_coin(str(coin_raw or ""))
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

            # Handle cumFunding - flip sign for SHORT positions
            # Hyena stores cumFunding as negative for SHORT positions that earn funding
            # But user-facing should show positive (earned)
            cum_funding = p.get("cumFunding") or {}
            if isinstance(cum_funding, dict):
                for key in ["allTime", "sinceOpen", "sinceChange"]:
                    if key in cum_funding and cum_funding[key]:
                        val = _to_float(cum_funding[key])
                        if val is not None and side == "SHORT":
                            cum_funding[key] = -val  # Flip sign for SHORT

            raw = dict(p)
            if liq_px is not None:
                raw["liquidation_price"] = liq_px

            out.append(
                {
                    "leg_id": f"hyena:{self.address}:{coin}:{side}",
                    "position_id": "",
                    "inst_id": str(coin),
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
