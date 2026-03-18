"""Tests for DB migration helper."""
import sqlite3
import unittest


class TestMigrationHelper(unittest.TestCase):
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
            closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT)""")
        con.execute("""CREATE TABLE pm_leg_snapshots (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            leg_id TEXT REFERENCES pm_legs(leg_id), position_id TEXT REFERENCES pm_positions(position_id),
            venue TEXT, inst_id TEXT, ts INTEGER, side TEXT, size REAL, entry_price REAL,
            current_price REAL, unrealized_pnl REAL, realized_pnl REAL, raw_json TEXT, meta_json TEXT)""")
        return con

    def test_migration_adds_columns(self):
        from tracking.position_manager.db_sync import ensure_multi_wallet_columns
        con = self._create_db()
        ensure_multi_wallet_columns(con)
        con.execute("INSERT INTO pm_positions(position_id, venue, status, created_at_ms, updated_at_ms) VALUES ('p1','h','OPEN',0,0)")
        con.execute("INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, account_id) VALUES ('l1','p1','h','BTC','LONG',1.0,'0xabc')")
        con.execute("INSERT INTO pm_leg_snapshots(leg_id, position_id, venue, inst_id, ts, side, size, account_id) VALUES ('l1','p1','h','BTC',1000,'LONG',1.0,'0xabc')")
        con.commit()

    def test_migration_idempotent(self):
        from tracking.position_manager.db_sync import ensure_multi_wallet_columns
        con = self._create_db()
        ensure_multi_wallet_columns(con)
        ensure_multi_wallet_columns(con)  # Should not raise


if __name__ == "__main__":
    unittest.main()
