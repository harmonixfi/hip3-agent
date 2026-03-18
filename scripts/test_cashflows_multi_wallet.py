"""Tests for cashflows multi-wallet support."""
import sqlite3
import unittest
from pathlib import Path


class TestCashflowsMultiWallet(unittest.TestCase):
    def _create_db(self):
        con = sqlite3.connect(":memory:")
        con.execute("PRAGMA foreign_keys = ON")
        schema_path = Path(__file__).resolve().parent.parent / "tracking" / "sql" / "schema_pm_v3.sql"
        con.executescript(schema_path.read_text())
        from tracking.position_manager.db_sync import ensure_multi_wallet_columns
        ensure_multi_wallet_columns(con)
        return con

    def test_index_includes_account_id(self):
        from tracking.position_manager.cashflows import load_managed_leg_index
        con = self._create_db()
        con.execute("INSERT INTO pm_positions(position_id, venue, status, created_at_ms, updated_at_ms) VALUES ('p1','h','OPEN',0,0)")
        con.execute("INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id) VALUES ('l1','p1','h','BTC','LONG',1.0,'OPEN',0,'0xabc')")
        con.execute("INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id) VALUES ('l2','p1','h','BTC','LONG',2.0,'OPEN',0,'0xdef')")
        con.commit()
        idx = load_managed_leg_index(con)
        self.assertEqual(idx[("h", "0xabc", "BTC", "LONG")], ("p1", "l1"))
        self.assertEqual(idx[("h", "0xdef", "BTC", "LONG")], ("p1", "l2"))

    def test_index_null_account_id(self):
        from tracking.position_manager.cashflows import load_managed_leg_index
        con = self._create_db()
        con.execute("INSERT INTO pm_positions(position_id, venue, status, created_at_ms, updated_at_ms) VALUES ('p1','h','OPEN',0,0)")
        con.execute("INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms) VALUES ('l1','p1','h','BTC','LONG',1.0,'OPEN',0)")
        con.commit()
        idx = load_managed_leg_index(con)
        self.assertEqual(idx[("h", "", "BTC", "LONG")], ("p1", "l1"))


if __name__ == "__main__":
    unittest.main()
