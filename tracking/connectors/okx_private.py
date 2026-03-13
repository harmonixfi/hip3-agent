"""OKX private connector (read-only) for bills/funding/fees.

This module is used by the cashflow ledger to ingest realized funding payments
(and optionally fees) from OKX.

Env vars:
- OKX_API_KEY
- OKX_API_SECRET
- OKX_API_PASSPHRASE
- OKX_BASE_URL (optional; default https://www.okx.com)

Docs:
- REST auth: https://www.okx.com/docs-v5/en/
- Bills endpoint: /api/v5/account/bills

We keep this stdlib-only.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from .private_base import PrivateConnectorBase

API_PREFIX = "/api/v5"
DEFAULT_BASE_URL = "https://www.okx.com"


def _utc_iso_ms() -> str:
    # OKX expects RFC3339 / ISO timestamp with ms and Z.
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _hmac_sha256_base64(secret: str, msg: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(mac).decode("utf-8")


class OKXPrivateConnector(PrivateConnectorBase):
    def __init__(self):
        super().__init__("okx")
        self.api_key = (os.environ.get("OKX_API_KEY") or "").strip()
        self.api_secret = (os.environ.get("OKX_API_SECRET") or "").strip()
        self.passphrase = (os.environ.get("OKX_API_PASSPHRASE") or "").strip()
        self.base_url = (os.environ.get("OKX_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")

        if not (self.api_key and self.api_secret and self.passphrase):
            raise RuntimeError("OKX credentials missing. Set OKX_API_KEY, OKX_API_SECRET, OKX_API_PASSPHRASE")

    def _signed_request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        method = method.upper()
        qs = ""
        if params:
            # OKX wants standard query encoding; keep stable ordering for signature.
            qs = "?" + urllib.parse.urlencode(params, doseq=True)

        request_path = API_PREFIX + path + qs
        url = self.base_url + request_path

        body_str = ""
        data_bytes = None
        if body is not None:
            body_str = json.dumps(body, separators=(",", ":"), sort_keys=True)
            data_bytes = body_str.encode("utf-8")

        ts = _utc_iso_ms()
        prehash = f"{ts}{method}{request_path}{body_str}"
        sign = _hmac_sha256_base64(self.api_secret, prehash)

        req = urllib.request.Request(
            url,
            data=data_bytes,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "OK-ACCESS-KEY": self.api_key,
                "OK-ACCESS-SIGN": sign,
                "OK-ACCESS-TIMESTAMP": ts,
                "OK-ACCESS-PASSPHRASE": self.passphrase,
                "User-Agent": "arbit-okx-private/0.1",
            },
        )

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}

    def fetch_bills(
        self,
        *,
        bill_type: Optional[str] = None,
        begin_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
        limit: int = 100,
        max_pages: int = 20,
    ) -> List[Dict[str, Any]]:
        """Fetch account bills.

        For funding payments, OKX typically uses bill_type=8 (Funding fee).
        The response is newest-first; we paginate backwards using `before` billId.
        """
        out: List[Dict[str, Any]] = []
        before: Optional[str] = None

        for _ in range(max_pages):
            params: Dict[str, Any] = {"limit": str(int(limit))}
            if bill_type is not None:
                params["type"] = str(bill_type)
            if begin_ms is not None:
                params["begin"] = str(int(begin_ms))
            if end_ms is not None:
                params["end"] = str(int(end_ms))
            if before:
                params["before"] = before

            data = self._signed_request("GET", "/account/bills", params=params)
            if str(data.get("code")) not in ("0", "None", "") and data.get("code") is not None:
                raise RuntimeError(f"OKX bills error: code={data.get('code')} msg={data.get('msg')}")

            rows = data.get("data")
            if not isinstance(rows, list) or not rows:
                break

            out.extend([r for r in rows if isinstance(r, dict)])
            before = str(rows[-1].get("billId") or "") or None

            if len(rows) < int(limit):
                break

        return out

    def fetch_account_snapshot(self) -> Dict[str, Any]:
        """Fetch OKX account balance snapshot.

        Endpoint: GET /api/v5/account/balance

        We use `totalEq` (USD equity) when present.
        """
        data = self._signed_request("GET", "/account/balance")
        if str(data.get("code")) not in ("0", "None", "") and data.get("code") is not None:
            raise RuntimeError(f"OKX balance error: code={data.get('code')} msg={data.get('msg')}")

        rows = data.get("data")
        if not isinstance(rows, list) or not rows:
            return {"account_id": "okx", "total_balance": None, "available_balance": None, "margin_balance": None, "unrealized_pnl": None, "position_value": None, "raw_json": data}

        r0 = rows[0] if isinstance(rows[0], dict) else {}
        def _to_float(x):
            try:
                return float(x)
            except Exception:
                return None

        total_eq = _to_float(r0.get("totalEq"))
        avail_eq = _to_float(r0.get("availEq"))

        return {
            "account_id": "okx",
            "total_balance": total_eq,
            "available_balance": avail_eq,
            "margin_balance": total_eq,
            "unrealized_pnl": None,
            "position_value": None,
            "raw_json": data,
        }

    def fetch_open_positions(self) -> List[Dict[str, Any]]:
        """Fetch open positions from OKX.

        Endpoint: GET /api/v5/account/positions

        Notes:
        - We only need SWAP positions for perp carry.
        - OKX returns sizes as strings; `pos` is signed (long>0, short<0).
        """
        data = self._signed_request("GET", "/account/positions", params={"instType": "SWAP"})
        if str(data.get("code")) not in ("0", "None", "") and data.get("code") is not None:
            raise RuntimeError(f"OKX positions error: code={data.get('code')} msg={data.get('msg')}")

        rows = data.get("data")
        if not isinstance(rows, list):
            return []

        def _to_float(x: Any) -> Optional[float]:
            try:
                return float(x)
            except Exception:
                return None

        out: List[Dict[str, Any]] = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            inst_id = str(r.get("instId") or "").strip()
            if not inst_id:
                continue

            pos = _to_float(r.get("pos"))
            if pos is None or abs(pos) == 0:
                continue

            # OKX in hedge-mode often returns positive `pos` with an explicit `posSide`.
            pos_side = str(r.get("posSide") or "").lower().strip()  # long|short|net
            if pos_side in ("long", "short"):
                side = "LONG" if pos_side == "long" else "SHORT"
            else:
                # net-mode: signed position size
                side = "LONG" if pos > 0 else "SHORT"
            size = abs(float(pos))

            entry_px = _to_float(r.get("avgPx"))
            mark_px = _to_float(r.get("markPx"))
            upl = _to_float(r.get("upl"))
            rpl = _to_float(r.get("realizedPnl"))  # may be absent

            out.append(
                {
                    "leg_id": f"okx:swap:{inst_id}:{side}",
                    "position_id": "",
                    "inst_id": inst_id,
                    "side": side,
                    "size": float(size),
                    "entry_price": entry_px,
                    "current_price": mark_px,
                    "unrealized_pnl": upl,
                    "realized_pnl": rpl,
                    "raw_json": r,
                }
            )

        return out
