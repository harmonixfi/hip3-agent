"""Tests for puller multi-wallet support."""
import json
import sqlite3
import unittest
from pathlib import Path


class TestPullerMultiWallet(unittest.TestCase):
    def _create_db(self):
        con = sqlite3.connect(":memory:")
        con.execute("PRAGMA foreign_keys = ON")
        schema_path = Path(__file__).resolve().parent.parent / "tracking" / "sql" / "schema_pm_v3.sql"
        con.executescript(schema_path.read_text())
        from tracking.position_manager.db_sync import ensure_multi_wallet_columns
        ensure_multi_wallet_columns(con)
        return con

    def test_load_positions_from_db_reads_wallet_label(self):
        from tracking.position_manager.puller import load_positions_from_db
        con = self._create_db()
        con.execute("INSERT INTO pm_positions(position_id, venue, status, created_at_ms, updated_at_ms) VALUES ('p1','hyperliquid','OPEN',0,0)")
        con.execute("INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id, meta_json) VALUES ('l1','p1','hyperliquid','BTC','LONG',1.0,'OPEN',0,'0xabc','{\"wallet_label\":\"alt\"}')")
        con.commit()
        positions = load_positions_from_db(con)
        leg = positions[0]["legs"][0]
        self.assertEqual(leg["wallet_label"], "alt")
        self.assertEqual(leg["account_id"], "0xabc")

    def test_load_positions_from_db_default_wallet_label(self):
        from tracking.position_manager.puller import load_positions_from_db
        con = self._create_db()
        con.execute("INSERT INTO pm_positions(position_id, venue, status, created_at_ms, updated_at_ms) VALUES ('p1','hyperliquid','OPEN',0,0)")
        con.execute("INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms) VALUES ('l1','p1','hyperliquid','BTC','LONG',1.0,'OPEN',0)")
        con.commit()
        positions = load_positions_from_db(con)
        leg = positions[0]["legs"][0]
        self.assertEqual(leg.get("wallet_label"), "main")

    def test_write_leg_snapshots_includes_account_id(self):
        from tracking.position_manager.puller import write_leg_snapshots
        con = self._create_db()
        con.execute("INSERT INTO pm_positions(position_id, venue, status, created_at_ms, updated_at_ms) VALUES ('p1','h','OPEN',0,0)")
        con.execute("INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id) VALUES ('l1','p1','h','BTC','LONG',1.0,'OPEN',0,'0xabc')")
        con.commit()
        positions = [{"leg_id":"l1","position_id":"p1","inst_id":"BTC","side":"LONG","size":1.0,"entry_price":50000.0,"current_price":51000.0,"unrealized_pnl":1000.0,"realized_pnl":0.0,"raw_json":{},"account_id":"0xabc"}]
        write_leg_snapshots(con, "h", positions, 1000)
        con.commit()
        row = con.execute("SELECT account_id FROM pm_leg_snapshots WHERE leg_id='l1'").fetchone()
        self.assertEqual(row[0], "0xabc")

    def test_load_positions_from_registry_includes_wallet_label(self):
        import tempfile, os
        from tracking.position_manager.puller import load_positions_from_registry
        data = json.dumps([{
            "position_id":"p1","strategy_type":"SPOT_PERP","base":"BTC","status":"OPEN",
            "legs":[{"leg_id":"l1","venue":"hyperliquid","inst_id":"BTC","side":"LONG","qty":1.0,"wallet_label":"alt"}]
        }])
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            os.write(fd, data.encode()); os.close(fd)
            positions = load_positions_from_registry(Path(path))
            self.assertEqual(positions[0]["legs"][0]["wallet_label"], "alt")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
