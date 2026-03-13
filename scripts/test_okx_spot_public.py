#!/usr/bin/env python3
"""Test OKX SPOT public endpoints and DB insertion (quote-aware matching)."""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tracking" / "connectors"))
sys.path.insert(0, str(ROOT / "tracking"))

import sqlite3
from datetime import datetime, timezone
from okx_public import get_spot_instruments, get_spot_tickers
from symbols import normalize_symbol, normalize_instrument_id, parse_okx_inst, get_quote_aware_key

DB_PATH = ROOT / "tracking" / "db" / "arbit.db"


def epoch_ms() -> int:
    """Current UTC timestamp in milliseconds."""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def test_parsing():
    """Test OKX instrument parsing."""
    print("=== Testing OKX Instrument Parsing ===\n")

    test_cases = [
        ('BTC-USDT-SWAP', 'BTC', 'USDT', 'PERP', 'BTC-USDT'),
        ('BTC-USDT', 'BTC', 'USDT', 'SPOT', 'BTC-USDT'),
        ('ETH-USD-SWAP', 'ETH', 'USD', 'PERP', 'ETH-USD'),
        ('ETH-USDT', 'ETH', 'USDT', 'SPOT', 'ETH-USDT'),
        ('SOL-USDT-SWAP', 'SOL', 'USDT', 'PERP', 'SOL-USDT'),
        ('SOL-USD', 'SOL', 'USD', 'SPOT', 'SOL-USD'),
    ]

    all_passed = True
    for inst_id, exp_base, exp_quote, exp_kind, exp_key in test_cases:
        base, quote, kind = parse_okx_inst(inst_id)
        key = get_quote_aware_key('okx', inst_id)

        passed = (base == exp_base and quote == exp_quote and kind == exp_kind and key == exp_key)
        status = "✓" if passed else "✗"

        print(f"{status} {inst_id}")
        print(f"   Expected: base={exp_base}, quote={exp_quote}, kind={exp_kind}, key={exp_key}")
        print(f"   Got:      base={base}, quote={quote}, kind={kind}, key={key}")
        if not passed:
            all_passed = False

    return all_passed


def test_spot_endpoints():
    """Test OKX SPOT public API endpoints."""
    print("\n=== Testing OKX SPOT Public Endpoints ===\n")

    # Test 1: Get SPOT instruments
    print("1. Testing get_spot_instruments()...")
    spot_insts = get_spot_instruments()
    print(f"   ✓ Retrieved {len(spot_insts)} SPOT instruments")
    if spot_insts:
        sample = spot_insts[0]
        print(f"   Sample: {sample['instId']}")
        print(f"   - Base: {sample['base']}, Quote: {sample['quote']}")

    # Test 2: Get SPOT tickers
    print("\n2. Testing get_spot_tickers()...")
    tickers = get_spot_tickers()
    print(f"   ✓ Retrieved {len(tickers)} SPOT tickers")
    if tickers:
        sample_inst = list(tickers.keys())[0]
        sample = tickers[sample_inst]
        print(f"   Sample: {sample_inst}")
        print(f"   - Last: {sample['lastPrice']}, Bid: {sample['bid']}, Ask: {sample['ask']}, Mid: {sample['mid']}")

    # Test 3: Check for major pairs
    print("\n3. Checking major pairs (USDT only)...")
    major_pairs = ["BTC", "ETH", "SOL"]
    found_pairs = {}
    for base in major_pairs:
        found = False
        for inst in spot_insts:
            if inst["base"] == base and inst["quote"] == "USDT":
                inst_id = inst["instId"]
                ticker = tickers.get(inst_id, {})
                if ticker and ticker["mid"] > 0:
                    print(f"   ✓ {base}/USDT: mid = {ticker['mid']}")
                    found_pairs[inst_id] = ticker
                    found = True
                    break
        if not found:
            print(f"   ✗ {base}/USDT not found or no price")

    return spot_insts, tickers, found_pairs


def test_db_insertion(spot_insts, tickers):
    """Test inserting SPOT data into DB."""
    print("\n=== Testing DB Insertion ===\n")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    ts = epoch_ms()

    # Test 4: Insert SPOT instruments
    print("4. Inserting SPOT instruments into DB...")
    n_inst = 0
    for inst in spot_insts:
        # Only insert USDT pairs to avoid ambiguity
        if inst["quote"] != "USDT":
            continue

        try:
            canonical_symbol = normalize_symbol("okx", inst["instId"])
            inst_id = normalize_instrument_id("okx", inst["instId"])

            cursor.execute(
                """
                INSERT OR REPLACE INTO instruments
                (venue, symbol, inst_id, contract_type, tick_size, contract_size, quote_currency, base_currency, funding_interval_hours, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "okx",
                    canonical_symbol,
                    inst_id,
                    "SPOT",
                    inst["tickSize"],
                    inst["contractSize"],
                    inst["quote"],
                    inst["base"],
                    0,  # No funding for spot
                    ts,
                ),
            )
            n_inst += 1
        except Exception as e:
            print(f"   ✗ ERROR inserting {inst.get('instId')}: {e}")

    conn.commit()
    print(f"   ✓ Inserted {n_inst} SPOT instruments (USDT only)")

    # Test 5: Insert SPOT prices
    print("\n5. Inserting SPOT prices into DB...")
    n_prices = 0
    for inst_id, price_info in tickers.items():
        # Only insert USDT pairs
        base, quote, kind = parse_okx_inst(inst_id)
        if kind != 'SPOT' or quote != 'USDT':
            continue

        try:
            canonical_symbol = normalize_symbol("okx", inst_id)

            last = price_info.get("lastPrice", 0.0)
            bid = price_info.get("bid", 0.0)
            ask = price_info.get("ask", 0.0)
            mid = price_info.get("mid", 0.0)

            cursor.execute(
                """
                INSERT OR REPLACE INTO prices
                (venue, symbol, mark_price, index_price, last_price, bid, ask, mid, ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("okx", canonical_symbol, last, None, last, bid, ask, mid, ts),
            )
            n_prices += 1
        except Exception as e:
            print(f"   ✗ ERROR inserting price {inst_id}: {e}")

    conn.commit()
    print(f"   ✓ Inserted {n_prices} SPOT prices (USDT only)")

    conn.close()

    return n_inst, n_prices


def verify_db_quote_aware():
    """Verify DB has correct spot-perp matching using quote-aware keys."""
    print("\n=== Verifying Quote-Aware Spot-Perp Matching ===\n")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Show sample spot/perp pairs with quote-aware matching
    print("6. Sample spot↔perp pairs (quote-aware matching):")

    test_bases = ["BTC", "ETH", "SOL"]
    test_quotes = ["USDT"]

    for base in test_bases:
        for quote in test_quotes:
            # Get SPOT inst_id and price
            spot_inst_id = f"{base}-{quote}"
            perp_inst_id = f"{base}-{quote}-SWAP"

            # Get latest SPOT price
            cursor.execute(
                """
                SELECT mid FROM prices
                WHERE venue='okx' AND symbol=?
                ORDER BY ts DESC LIMIT 1
                """,
                (base,),
            )
            spot_row = cursor.fetchone()
            spot_mid = spot_row[0] if spot_row else None

            # Get latest PERP price (should be separate entry if PERP exists)
            cursor.execute(
                """
                SELECT mid FROM prices
                WHERE venue='okx' AND symbol=?
                ORDER BY ts DESC LIMIT 1
                """,
                (base,),
            )
            perp_row = cursor.fetchone()
            perp_mid = perp_row[0] if perp_row else None

            # For proper quote-aware matching, we need to check inst_id in instruments table
            cursor.execute(
                """
                SELECT contract_type, quote_currency
                FROM instruments
                WHERE venue='okx' AND inst_id IN (?, ?)
                """,
                (spot_inst_id, perp_inst_id),
            )
            inst_rows = cursor.fetchall()

            spot_found = False
            perp_found = False
            for row in inst_rows:
                if row[0] == 'SPOT' and row[1] == quote:
                    spot_found = True
                elif row[0] == 'PERP' and row[1] == quote:
                    perp_found = True

            if spot_found and perp_found:
                # Note: Both spot and perp have the same canonical symbol (base-only)
                # But they have different inst_ids which allows us to distinguish them
                print(f"   {base}-{quote}: SPOT inst_id={spot_inst_id}, PERP inst_id={perp_inst_id}")
                print(f"     SPOT found={spot_found}, PERP found={perp_found}")
                if spot_mid and perp_mid:
                    basis = perp_mid - spot_mid
                    basis_pct = (basis / spot_mid) * 100 if spot_mid else 0
                    print(f"     SPOT mid={spot_mid:.2f}, PERP mid={perp_mid:.2f}, basis={basis:+.4f} ({basis_pct:+.2f}%)")
                    if abs(basis) < 0.01:
                        print(f"     ⚠ WARNING: Basis is near zero - may be matching incorrectly")
                    else:
                        print(f"     ✓ Basis is non-zero (expected)")
                else:
                    print(f"     Prices: SPOT={spot_mid}, PERP={perp_mid}")
            else:
                print(f"   {base}-{quote}: SPOT found={spot_found}, PERP found={perp_found}")

    conn.close()


def main() -> int:
    print("OKX SPOT Public API Test (Quote-Aware Matching)")
    print("=" * 60)
    print()

    try:
        # Test parsing first
        parsing_ok = test_parsing()
        if not parsing_ok:
            print("\n✗ Parsing tests failed!")
            return 1

        spot_insts, tickers, found_pairs = test_spot_endpoints()
        test_db_insertion(spot_insts, tickers)
        verify_db_quote_aware()

        print("\n" + "=" * 60)
        print("✓ All tests completed!")
        return 0
    except Exception as e:
        print(f"\n✗ Test failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
