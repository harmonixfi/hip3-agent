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
import time
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

    def fetch_account_snapshot(
        self,
        *,
        dex: Optional[str] = None,
        builder_dexes: Optional[List[str]] = None,
        exclude_spot_tokens: Optional[List[str]] = None,
    ) -> Dict:
        use_dex = self.dex if dex is None else str(dex or "").strip()

        # --- 1. Native perp margin ---
        st = post_info({"type": "clearinghouseState", "user": self.address}, dex=use_dex)
        if not isinstance(st, dict):
            raise RuntimeError("Unexpected Hyperliquid response (not dict)")

        ms = st.get("marginSummary") or {}
        perp_native = _to_float(ms.get("accountValue")) or 0.0
        total_margin_used = _to_float(ms.get("totalMarginUsed"))

        free = None
        if perp_native and total_margin_used is not None:
            free = perp_native - total_margin_used

        # If no builder dexes requested, return simple snapshot (backward compat)
        if not builder_dexes:
            return {
                "account_id": self.address,
                "dex": use_dex,
                "total_balance": perp_native or None,
                "available_balance": free,
                "margin_balance": perp_native or None,
                "unrealized_pnl": None,
                "position_value": _to_float(ms.get("totalNtlPos")),
                "raw_json": st,
            }

        # --- 2. Builder dex perp margins ---
        breakdown: Dict[str, Any] = {"perp_native": round(perp_native, 2)}
        total_perp = perp_native

        for bdex in builder_dexes:
            time.sleep(0.3)
            try:
                bst = post_info(
                    {"type": "clearinghouseState", "user": self.address}, dex=bdex
                )
                bms = (bst or {}).get("marginSummary") or {}
                bval = _to_float(bms.get("accountValue")) or 0.0
            except Exception:
                bval = 0.0
            breakdown[f"perp_{bdex}"] = round(bval, 2)
            total_perp += bval

        # --- 3. Spot balances ---
        time.sleep(0.3)
        spot_state = post_info(
            {"type": "spotClearinghouseState", "user": self.address}, dex=""
        )
        balances = (spot_state or {}).get("balances") or []

        time.sleep(0.3)
        web_data = post_info({"type": "webData2", "user": self.address}, dex="")
        spot_asset_ctxs = (web_data or {}).get("spotAssetCtxs") or []

        time.sleep(0.3)
        spot_meta = post_info({"type": "spotMeta"}, dex="")

        # Build ctx price map: "@107" -> midPx
        ctx_prices: Dict[str, float] = {}
        for ctx in spot_asset_ctxs:
            coin = ctx.get("coin", "")
            mid = ctx.get("midPx")
            if mid and mid != "N/A":
                try:
                    ctx_prices[coin] = float(mid)
                except (ValueError, TypeError):
                    pass

        # Build token_index -> best universe.index (prefer USDC quote)
        token_names: Dict[int, str] = {}
        for t in (spot_meta or {}).get("tokens", []):
            token_names[t["index"]] = t["name"]

        universe = (spot_meta or {}).get("universe", [])
        token_to_uni_index: Dict[int, int] = {}
        for uni in universe:
            tok_ids = uni.get("tokens", [])
            uni_idx = uni.get("index")
            if len(tok_ids) >= 2 and uni_idx is not None:
                base_token_idx = tok_ids[0]
                quote_name = token_names.get(tok_ids[1], "")
                if base_token_idx not in token_to_uni_index or quote_name == "USDC":
                    token_to_uni_index[base_token_idx] = uni_idx

        # Value each balance
        exclude_set = set(exclude_spot_tokens or [])
        spot_tokens: Dict[str, float] = {}
        spot_equity = 0.0
        spot_excluded = 0.0

        for b in balances:
            coin = b.get("coin", "")
            qty = _to_float(b.get("total")) or 0.0
            token_idx = b.get("token")
            if abs(qty) < 1e-12:
                continue

            if coin in ("USDC", "USDE", "USDH"):
                px = 1.0
            else:
                uni_idx = token_to_uni_index.get(token_idx)
                ref = f"@{uni_idx}" if uni_idx is not None else None
                px = ctx_prices.get(ref, 0) if ref else 0

            val = qty * px
            spot_tokens[coin] = round(val, 2)

            if coin in exclude_set:
                spot_excluded += val
            else:
                spot_equity += val

        breakdown["spot_equity"] = round(spot_equity, 2)
        breakdown["spot_excluded"] = round(spot_excluded, 2)
        breakdown["spot_tokens"] = spot_tokens

        total_balance = total_perp + spot_equity

        return {
            "account_id": self.address,
            "dex": use_dex,
            "total_balance": round(total_balance, 2),
            "available_balance": free,
            "margin_balance": round(total_perp, 2),
            "unrealized_pnl": None,
            "position_value": _to_float(ms.get("totalNtlPos")),
            "raw_json": breakdown,
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
