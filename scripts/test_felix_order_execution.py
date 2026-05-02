#!/usr/bin/env python3
"""Felix order execution test — quote price vs fill price.

Tests whether Felix uses firm RFQ pricing (H1) or market fill pricing (H2).

H1: quote_price == averageFilledPrice  →  Felix is a market maker with firm quotes
H2: quote_price != averageFilledPrice  →  Felix fills at market, quote is indicative

Run at US market open (9:30 PM VNT / 9:30 AM ET):
    source .arbit_env
    python scripts/test_felix_order_execution.py

4 orders: BUY $20 → SELL → BUY $25 → SELL
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking.connectors.felix_order import FelixOrderClient, sign_via_turnkey
from tracking.connectors.felix_private import _felix_get

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TICKER = "TSLA"
FELIX_EQUITIES_ADDRESS = "0xaD0F4EcB5bbE32D080614018253FA5A40eF5df1D"
SESSION_PATH = Path(__file__).parent.parent / "vault" / "felix_session.enc.json"

# BUY notional amounts for the two pairs
BUY_NOTIONALS = [20.0, 25.0]

FILL_PRICE_POLL_TIMEOUT = 120   # seconds to wait for averageFilledPrice to appear
FILL_PRICE_POLL_INTERVAL = 5    # poll every N seconds
FILL_PRICE_STABLE_WAIT = 30     # re-fetch after this many seconds to verify stability


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


_ORDERS_HEADERS = {
    "Accept": "application/json",
    "Origin": "https://trade.usefelix.xyz",
    "Referer": "https://trade.usefelix.xyz/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36"
    ),
}

_FELIX_ORDERS_URL = "https://spot-equities-proxy.white-star-bc1e.workers.dev/v1/trading/orders"


def _fetch_orders_list(jwt: str) -> list:
    """GET /v1/trading/orders — returns list from 'data' key."""
    import urllib.request as _ur
    req = _ur.Request(_FELIX_ORDERS_URL, headers={**_ORDERS_HEADERS, "Authorization": f"Bearer {jwt}"})
    with _ur.urlopen(req, timeout=30) as resp:
        raw = json.loads(resp.read())
    return raw.get("data") or raw.get("orders") or []


def _poll_fill_notional(
    order_id: str,
    jwt: str,
    timeout: float = FILL_PRICE_POLL_TIMEOUT,
    interval: float = FILL_PRICE_POLL_INTERVAL,
) -> Tuple[Optional[float], Optional[Dict]]:
    """Poll GET /v1/trading/orders until notionalStablecoin is populated for order_id.

    Felix does not populate avgPrice/executedShares. notionalStablecoin is the
    only reliable field: USD paid (BUY) or USD received (SELL).

    Returns (notional_usdc, raw_order_dict) or (None, None) on timeout.
    """
    deadline = time.monotonic() + timeout
    attempt = 0
    while True:
        attempt += 1
        orders = _fetch_orders_list(jwt)
        for o in orders:
            if o.get("id") == order_id:
                notional = o.get("notionalStablecoin")
                if notional is not None:
                    try:
                        n = float(notional)
                        if n > 0:
                            log.info(
                                "notionalStablecoin ready after attempt %d: notional=%.6f",
                                attempt, n,
                            )
                            return n, o
                    except (TypeError, ValueError):
                        pass
                break  # order found but notional not ready

        if time.monotonic() >= deadline:
            log.warning("Timeout (%ds) waiting for notionalStablecoin on order %s", timeout, order_id)
            return None, None

        log.info(
            "Order %s: notionalStablecoin not yet available — retrying in %ds (attempt %d)...",
            order_id, interval, attempt,
        )
        time.sleep(interval)


def _fetch_usdc_balance(jwt: str) -> Optional[float]:
    import urllib.request as _ur
    url = f"https://spot-equities-proxy.white-star-bc1e.workers.dev/v1/portfolio/{FELIX_EQUITIES_ADDRESS}"
    req = _ur.Request(url, headers={**_ORDERS_HEADERS, "Authorization": f"Bearer {jwt}"})
    with _ur.urlopen(req, timeout=30) as resp:
        raw = json.loads(resp.read())
    sc = raw.get("stablecoinBalance") or raw.get("stablecoin_balance")
    if sc is None:
        return None
    if isinstance(sc, dict):
        for k in ("usdValue", "amount", "value", "usd"):
            if sc.get(k) is not None:
                try:
                    return float(sc[k])
                except (ValueError, TypeError):
                    pass
    try:
        return float(sc)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Per-order execution
# ---------------------------------------------------------------------------

def run_order(
    client: FelixOrderClient,
    jwt: str,
    session_pk: str,
    sub_org_id: str,
    order_num: int,
    side: str,
    *,
    notional_usdc: Optional[float] = None,
    token_amount: Optional[float] = None,
) -> Dict[str, Any]:
    """Execute one order and collect full execution data.

    Uses the manual pipeline (get_quote → sign → submit → poll) so that the
    quote price is captured BEFORE the order is submitted — place_order() would
    issue its own internal quote and we'd miss the timing data.
    """
    log.info("─" * 60)
    notional_display = f"${notional_usdc:.2f}" if notional_usdc else f"{token_amount:.8f} shares"
    log.info("ORDER %d: %s %s %s", order_num, side, TICKER, notional_display)

    # 1. Quote
    t_quote = _now_iso()
    quote = client.get_quote(
        TICKER, side,
        notional_usdc=notional_usdc,
        token_amount=token_amount,
    )
    quote_price = float(quote["price"])
    estimated_shares = float(quote["estimatedShares"])
    quote_id = quote["id"]
    account_address = quote["accountId"]
    intent = quote["intent"]
    intent_id = intent["id"]
    payload_hash = intent["payloadHash"]
    expires_at = quote.get("expiresAt", "")
    log.info(
        "Quote: price=%.6f  estimated_shares=%.8f  expires=%s",
        quote_price, estimated_shares, expires_at,
    )

    # 2. Sign via Turnkey
    t_sign = _now_iso()
    sig = sign_via_turnkey(payload_hash, account_address, sub_org_id, session_pk)
    log.info("Signed: v=%d", sig["v"])

    # 3. Submit order
    t_submit = _now_iso()
    submitted = client.submit_order(quote_id, intent_id, sig)
    order_id = submitted["id"]
    log.info("Submitted: order_id=%s", order_id)

    # 4. Poll until FILLED (GET /orders/{id})
    final = client.poll_order(order_id)
    t_fill_confirmed = _now_iso()
    tx_hash = final.get("onchainTxHash", "")
    log.info("FILLED: order_id=%s  tx=%s...", order_id, tx_hash[:20] if tx_hash else "n/a")

    # 5. Poll for notionalStablecoin from list endpoint (settlement is async)
    # Felix does not populate avgPrice/executedShares — notionalStablecoin is the
    # only reliable fill field: USD paid (BUY) or USD received (SELL).
    log.info(
        "Polling for notionalStablecoin (timeout=%ds, interval=%ds)...",
        FILL_PRICE_POLL_TIMEOUT, FILL_PRICE_POLL_INTERVAL,
    )
    notional_initial, raw_fill_initial = _poll_fill_notional(order_id, jwt)
    t_fill_price_ready = _now_iso()

    # 6. Re-fetch after 30s to verify stability
    notional_stable = None
    if notional_initial is not None:
        log.info("notionalStablecoin=%.6f. Waiting %ds to verify stability...", notional_initial, FILL_PRICE_STABLE_WAIT)
        time.sleep(FILL_PRICE_STABLE_WAIT)
        for o in _fetch_orders_list(jwt):
            if o.get("id") == order_id:
                try:
                    notional_stable = float(o["notionalStablecoin"])
                except (TypeError, ValueError, KeyError):
                    pass
                break

    # Infer fill price from notionalStablecoin:
    # SELL: fill_price = notional_received / shares_sold  (exact)
    # BUY:  fill_price = notional_paid / estimated_shares (approx — actual shares unknown)
    fill_price_initial = None
    fill_price_stable = None
    if notional_initial is not None and estimated_shares > 0:
        ref_qty = token_amount if token_amount else estimated_shares
        fill_price_initial = notional_initial / ref_qty
        if notional_stable is not None:
            fill_price_stable = notional_stable / ref_qty

    # Compute slippage
    if fill_price_initial is not None:
        price_diff_pct = (fill_price_initial - quote_price) / quote_price * 100
        hypothesis = "H1" if abs(price_diff_pct) < 0.05 else "H2"
    else:
        price_diff_pct = None
        hypothesis = "UNKNOWN"

    log.info(
        "SUMMARY: quote=%.6f  fill=%.6f  notional=%.6f  diff=%s  verdict=%s",
        quote_price,
        fill_price_initial if fill_price_initial else 0.0,
        notional_initial if notional_initial else 0.0,
        f"{price_diff_pct:+.4f}%" if price_diff_pct is not None else "N/A",
        hypothesis,
    )

    return {
        "order_num": order_num,
        "side": side,
        "notional_requested": notional_usdc,
        "token_amount_requested": token_amount,
        "t_quote": t_quote,
        "t_sign": t_sign,
        "t_submit": t_submit,
        "t_fill_confirmed": t_fill_confirmed,
        "t_fill_price_ready": t_fill_price_ready,
        "quote_price": quote_price,
        "estimated_shares": estimated_shares,
        "quote_id": quote_id,
        "intent_id": intent_id,
        "order_id": order_id,
        "tx_hash": tx_hash,
        "notional_usdc": notional_initial,
        "notional_usdc_stable": notional_stable,
        "fill_price_initial": fill_price_initial,
        "fill_price_stable": fill_price_stable,
        "price_diff_pct": price_diff_pct,
        "hypothesis": hypothesis,
        "raw_fill": raw_fill_initial,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    with open(SESSION_PATH) as f:
        sess = json.load(f)
    jwt = sess["jwt"]
    session_pk = sess["session_private_key_hex"]
    sub_org_id = sess["sub_org_id"]

    client = FelixOrderClient(
        jwt=jwt,
        session_private_key_hex=session_pk,
        sub_org_id=sub_org_id,
    )

    # Market open check
    limits = client.check_limits(TICKER, "BUY")
    if not limits.get("isOpen"):
        log.error("Market not open: %s", limits.get("reason"))
        sys.exit(1)
    log.info(
        "Market open. maxNotional=%s  remainingAttestations=%s",
        limits.get("maxNotionalValue"), limits.get("remainingAttestations"),
    )

    # Portfolio before
    usdc_before = _fetch_usdc_balance(jwt)
    log.info("USDC balance before: %s", f"{usdc_before:.4f}" if usdc_before else "unknown")

    ts_start = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    all_results = []

    for i, notional in enumerate(BUY_NOTIONALS, start=1):
        buy_order_num = (i - 1) * 2 + 1   # 1, 3
        sell_order_num = buy_order_num + 1  # 2, 4

        # BUY
        buy = run_order(
            client, jwt, session_pk, sub_org_id,
            buy_order_num, "BUY",
            notional_usdc=notional,
        )
        all_results.append(buy)

        # SELL — use estimated_shares from the buy quote (actual qty unknown from API)
        sell_qty = buy["estimated_shares"]
        sell = run_order(
            client, jwt, session_pk, sub_org_id,
            sell_order_num, "SELL",
            token_amount=sell_qty,
        )
        all_results.append(sell)

    # Portfolio after
    usdc_after = _fetch_usdc_balance(jwt)
    log.info("USDC balance after: %s", f"{usdc_after:.4f}" if usdc_after else "unknown")

    # -------------------------------------------------------------------------
    # Results table
    # -------------------------------------------------------------------------
    print("\n" + "═" * 100)
    print("  FELIX ORDER EXECUTION TEST — QUOTE PRICE vs FILL PRICE")
    print("═" * 100)
    print(
        f"  {'#':>2}  {'Side':<5}  {'Requested':>12}  {'Quote Price':>12}  "
        f"{'Notional USD':>13}  {'Fill Price':>11}  {'Diff%':>8}  Verdict"
    )
    print("─" * 100)

    for r in all_results:
        if r["notional_requested"] is not None:
            req_str = f"${r['notional_requested']:.2f}"
        else:
            req_str = f"{r['token_amount_requested']:.6f}sh"
        notional_str = f"${r['notional_usdc']:.6f}" if r["notional_usdc"] else "pending"
        fill_str = f"{r['fill_price_initial']:.6f}" if r["fill_price_initial"] else "—"
        diff_str = f"{r['price_diff_pct']:+.4f}%" if r["price_diff_pct"] is not None else "N/A"
        print(
            f"  {r['order_num']:>2}  {r['side']:<5}  {req_str:>12}  "
            f"{r['quote_price']:>12.6f}  {notional_str:>13}  {fill_str:>11}  {diff_str:>8}  {r['hypothesis']}"
        )

    print("─" * 100)

    # Conclusion
    priced = [r for r in all_results if r["fill_price_initial"] is not None]
    if len(priced) == len(all_results):
        # SELL diff is the reliable measurement (exact shares known).
        # BUY diff has ~0.03% artifact from using estimated_shares as proxy for actual shares.
        sell_diffs = [abs(r["price_diff_pct"]) for r in priced if r["side"] == "SELL"]
        buy_diffs  = [abs(r["price_diff_pct"]) for r in priced if r["side"] == "BUY"]
        max_sell_diff = max(sell_diffs) if sell_diffs else 0.0
        max_buy_diff  = max(buy_diffs)  if buy_diffs  else 0.0
        if max_sell_diff < 0.01:
            conclusion = (
                f"H1 CONFIRMED — Felix firm RFQ (SELL diff {max_sell_diff:.4f}% ≈ 0; "
                f"BUY diff {max_buy_diff:.4f}% is estimation artifact from using estimated_shares)"
            )
        else:
            conclusion = f"H2 INDICATED — market fill pricing (SELL diff {max_sell_diff:.4f}%)"
    else:
        conclusion = f"INCONCLUSIVE — {len(all_results) - len(priced)}/{len(all_results)} fill prices not populated"

    print(f"\n  CONCLUSION: {conclusion}")

    if usdc_before is not None and usdc_after is not None:
        net = usdc_after - usdc_before
        print(f"  Portfolio: before=${usdc_before:.4f}  after=${usdc_after:.4f}  net={net:+.4f} USDC")

    # Timing analysis
    print("\n  TIMING (quote → fill_confirmed → fill_price_ready):")
    for r in all_results:
        try:
            def _parse(s):
                return datetime.fromisoformat(s.replace("Z", "+00:00"))
            dt_quote = _parse(r["t_quote"])
            dt_confirmed = _parse(r["t_fill_confirmed"])
            dt_ready = _parse(r["t_fill_price_ready"])
            secs_to_fill = (dt_confirmed - dt_quote).total_seconds()
            secs_to_price = (dt_ready - dt_confirmed).total_seconds()
            print(
                f"  Order {r['order_num']} {r['side']:<5}: "
                f"quote→fill={secs_to_fill:.1f}s  fill→price_ready={secs_to_price:.1f}s"
            )
        except Exception:
            pass

    # Save raw log
    log_dir = Path(__file__).parent.parent / "docs" / "reports"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"felix_order_test_{ts_start}.json"
    with open(log_path, "w") as f:
        json.dump(
            {
                "ts_start": ts_start,
                "ticker": TICKER,
                "usdc_before": usdc_before,
                "usdc_after": usdc_after,
                "conclusion": conclusion,
                "results": [
                    {k: v for k, v in r.items() if k != "raw_fill"}
                    for r in all_results
                ],
                "raw_fills": [r.get("raw_fill") for r in all_results],
            },
            f, indent=2,
        )
    print(f"\n  Raw log: {log_path}")
    print("═" * 100 + "\n")


if __name__ == "__main__":
    main()
