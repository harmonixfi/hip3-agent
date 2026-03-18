"""Tests for db_sync wallet_label and account_id support."""
import json
import sqlite3
import unittest


class TestDbSyncWalletLabel(unittest.TestCase):
    def _create_db(self):
        con = sqlite3.connect(":memory:")
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("""CREATE TABLE pm_positions (
            position_id TEXT PRIMARY KEY, venue TEXT NOT NULL, strategy TEXT, status TEXT,
            created_at_ms INTEGER, updated_at_ms INTEGER, closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT)""")
        con.execute("""CREATE TABLE pm_legs (
            leg_id TEXT PRIMARY KEY, position_id TEXT REFERENCES pm_positions(position_id),
            venue TEXT, inst_id TEXT, side TEXT, size REAL, entry_price REAL, current_price REAL,
            unrealized_pnl REAL, realized_pnl REAL, status TEXT, opened_at_ms INTEGER,
            closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT, account_id TEXT)""")
        return con

    def test_upsert_leg_stores_wallet_label_in_meta(self):
        from tracking.position_manager.registry import LegConfig, PositionConfig
        from tracking.position_manager.db_sync import upsert_leg, upsert_position
        con = self._create_db()
        pos = PositionConfig(position_id="p1", strategy_type="SPOT_PERP", base="BTC", status="OPEN", legs=[])
        upsert_position(con, pos, 1000)
        leg = LegConfig(leg_id="l1", venue="hyperliquid", inst_id="BTC", side="LONG", qty=1.0, wallet_label="alt")
        upsert_leg(con, "p1", leg, 1000)
        con.commit()
        row = con.execute("SELECT meta_json FROM pm_legs WHERE leg_id='l1'").fetchone()
        meta = json.loads(row[0])
        self.assertEqual(meta.get("wallet_label"), "alt")

    def test_upsert_leg_no_wallet_label(self):
        from tracking.position_manager.registry import LegConfig, PositionConfig
        from tracking.position_manager.db_sync import upsert_leg, upsert_position
        con = self._create_db()
        pos = PositionConfig(position_id="p1", strategy_type="SPOT_PERP", base="BTC", status="OPEN", legs=[])
        upsert_position(con, pos, 1000)
        leg = LegConfig(leg_id="l1", venue="hyperliquid", inst_id="BTC", side="LONG", qty=1.0)
        upsert_leg(con, "p1", leg, 1000)
        con.commit()
        row = con.execute("SELECT meta_json FROM pm_legs WHERE leg_id='l1'").fetchone()
        if row[0]:
            meta = json.loads(row[0])
            self.assertNotIn("wallet_label", meta)

    def test_list_positions_includes_account_id(self):
        from tracking.position_manager.db_sync import list_positions
        con = self._create_db()
        con.execute("INSERT INTO pm_positions(position_id, venue, status, created_at_ms, updated_at_ms) VALUES ('p1','h','OPEN',0,0)")
        con.execute("INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, account_id, meta_json) VALUES ('l1','p1','h','BTC','LONG',1.0,'0xabc','{\"wallet_label\":\"main\"}')")
        con.commit()
        positions = list_positions(con)
        self.assertEqual(len(positions), 1)
        leg = positions[0]["legs"][0]
        self.assertEqual(leg["account_id"], "0xabc")
        self.assertEqual(leg["meta"].get("wallet_label"), "main")


if __name__ == "__main__":
    unittest.main()
