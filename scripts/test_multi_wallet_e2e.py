"""End-to-end test for multi-wallet partition-then-match."""
import json
import sqlite3
import unittest
from pathlib import Path


class TestMultiWalletEndToEnd(unittest.TestCase):
    def _create_db(self):
        con = sqlite3.connect(":memory:")
        con.execute("PRAGMA foreign_keys = ON")
        schema_path = Path(__file__).resolve().parent.parent / "tracking" / "sql" / "schema_pm_v3.sql"
        con.executescript(schema_path.read_text())
        from tracking.position_manager.db_sync import ensure_multi_wallet_columns
        ensure_multi_wallet_columns(con)
        return con

    def test_two_wallets_same_instrument_no_collision(self):
        """Two wallets both have BTC SHORT — each maps to correct managed leg."""
        from tracking.position_manager.puller import write_leg_snapshots, load_positions_from_db

        con = self._create_db()

        # Setup: position with 2 legs on different wallets, same inst_id+side
        con.execute("""
            INSERT INTO pm_positions(position_id, venue, status, created_at_ms, updated_at_ms)
            VALUES ('p1', 'hyperliquid', 'OPEN', 0, 0)
        """)
        con.execute("""
            INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status,
                                opened_at_ms, account_id, meta_json)
            VALUES ('l_main', 'p1', 'hyperliquid', 'xyz:BTC', 'SHORT', 1.0, 'OPEN',
                    0, '0xaaa', '{"wallet_label":"main"}')
        """)
        con.execute("""
            INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status,
                                opened_at_ms, account_id, meta_json)
            VALUES ('l_alt', 'p1', 'hyperliquid', 'xyz:BTC', 'SHORT', 2.0, 'OPEN',
                    0, '0xbbb', '{"wallet_label":"alt"}')
        """)
        con.commit()

        positions = load_positions_from_db(con)

        # Verify partition works
        main_legs = [leg for pos in positions for leg in pos["legs"] if leg.get("wallet_label") == "main"]
        alt_legs = [leg for pos in positions for leg in pos["legs"] if leg.get("wallet_label") == "alt"]
        self.assertEqual(len(main_legs), 1)
        self.assertEqual(main_legs[0]["leg_id"], "l_main")
        self.assertEqual(len(alt_legs), 1)
        self.assertEqual(alt_legs[0]["leg_id"], "l_alt")

        # Simulate match for main wallet
        venue_pos = {"inst_id": "xyz:BTC", "side": "SHORT", "size": 1.5,
                     "entry_price": 50000, "current_price": 51000,
                     "unrealized_pnl": -1000, "realized_pnl": 0, "raw_json": {}}
        idx = {("xyz:BTC", "SHORT"): venue_pos}
        mapped_main = []
        for ml in main_legs:
            key = (ml["inst_id"], ml["side"])
            vp = idx.get(key)
            if vp:
                mapped_main.append({**vp, "leg_id": ml["leg_id"], "position_id": "p1", "account_id": "0xaaa"})

        self.assertEqual(len(mapped_main), 1)
        self.assertEqual(mapped_main[0]["leg_id"], "l_main")
        self.assertEqual(mapped_main[0]["account_id"], "0xaaa")

        # Write snapshots and verify attribution
        write_leg_snapshots(con, "hyperliquid", mapped_main, 1000)
        con.commit()

        rows = con.execute("SELECT leg_id, account_id FROM pm_leg_snapshots ORDER BY leg_id").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "l_main")
        self.assertEqual(rows[0][1], "0xaaa")


if __name__ == "__main__":
    unittest.main()
