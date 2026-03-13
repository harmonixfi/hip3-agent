#!/usr/bin/env python3
"""Focused tests for Hyperliquid cashflow ingest helpers."""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def _load_pm_cashflows():
    path = ROOT / "scripts" / "pm_cashflows.py"
    spec = importlib.util.spec_from_file_location("harmonix_pm_cashflows", path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _create_db(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(path))
    con.executescript(
        """
        CREATE TABLE pm_positions(
          position_id TEXT PRIMARY KEY,
          venue TEXT,
          strategy TEXT,
          status TEXT,
          created_at_ms INTEGER,
          updated_at_ms INTEGER,
          closed_at_ms INTEGER,
          meta_json TEXT
        );
        CREATE TABLE pm_legs(
          leg_id TEXT PRIMARY KEY,
          position_id TEXT,
          venue TEXT,
          inst_id TEXT,
          side TEXT,
          size REAL,
          entry_price REAL,
          current_price REAL,
          unrealized_pnl REAL,
          realized_pnl REAL,
          status TEXT,
          opened_at_ms INTEGER,
          closed_at_ms INTEGER,
          raw_json TEXT,
          meta_json TEXT
        );
        CREATE TABLE pm_cashflows(
          cashflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
          position_id TEXT,
          leg_id TEXT,
          venue TEXT,
          account_id TEXT,
          ts INTEGER,
          cf_type TEXT,
          amount REAL,
          currency TEXT,
          description TEXT,
          raw_json TEXT,
          meta_json TEXT
        );
        """
    )
    return con


def main() -> int:
    mod = _load_pm_cashflows()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "cashflows.db"
        con = _create_db(db_path)

        now_ms = mod.now_ms()
        con.executemany(
            "INSERT INTO pm_positions(position_id, venue, strategy, status, created_at_ms, updated_at_ms, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("pos_xyz_GOLD", "hyperliquid", "SPOT_PERP", "OPEN", now_ms, now_ms, "{}"),
                ("pos_hyna_HYPE", "hyperliquid", "SPOT_PERP", "OPEN", now_ms, now_ms, "{}"),
            ],
        )
        con.executemany(
            "INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, raw_json, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("gold_spot", "pos_xyz_GOLD", "hyperliquid", "XAUT0/USDC", "LONG", 2.0, "OPEN", now_ms, "{}", "{}"),
                ("gold_perp", "pos_xyz_GOLD", "hyperliquid", "xyz:GOLD", "SHORT", 2.0, "OPEN", now_ms, "{}", "{}"),
                ("hype_spot", "pos_hyna_HYPE", "hyperliquid", "HYPE", "LONG", 10.0, "OPEN", now_ms, "{}", "{}"),
                ("hype_perp", "pos_hyna_HYPE", "hyperliquid", "hyna:HYPE", "SHORT", 10.0, "OPEN", now_ms, "{}", "{}"),
            ],
        )
        con.commit()

        targets = mod._load_hyperliquid_targets(con)
        assert "xyz" in targets and "GOLD" in targets["xyz"]
        assert targets["xyz"]["GOLD"]["leg_id"] == "gold_perp"
        assert "hyna" in targets and "HYPE" in targets["hyna"]
        assert targets["hyna"]["HYPE"]["leg_id"] == "hype_perp"

        calls = []
        delivered = set()

        def fake_post(payload, *, dex="", timeout=30):
            calls.append((payload["type"], dex, payload.get("startTime"), payload.get("endTime")))
            key = (payload["type"], dex)
            if key in delivered:
                return []
            delivered.add(key)
            event_ts = int(payload["startTime"]) + 1
            if payload["type"] == "userFunding" and dex == "xyz":
                return [{"time": event_ts, "delta": {"coin": "GOLD", "usdc": "67.67"}}]
            if payload["type"] == "userFunding" and dex == "hyna":
                return [{"time": event_ts, "delta": {"coin": "HYPE", "usdc": "3.25"}}]
            if payload["type"] == "userFillsByTime" and dex == "xyz":
                return [{"time": event_ts, "coin": "GOLD", "fee": "0.55"}]
            if payload["type"] == "userFillsByTime" and dex == "hyna":
                return [{"time": event_ts, "coin": "HYPE", "fee": "0.25"}]
            return []

        class FakeConnector:
            address = "0xabc"

        mod._hl_post = fake_post  # type: ignore[attr-defined]
        mod.HyperliquidPrivateConnector = lambda: FakeConnector()  # type: ignore[assignment]

        inserted = mod.ingest_hyperliquid(con, since_hours=24 * 15)
        assert inserted == 4

        rows = con.execute(
            "SELECT position_id, leg_id, cf_type, amount, description FROM pm_cashflows ORDER BY cashflow_id"
        ).fetchall()
        assert rows[0][0] == "pos_xyz_GOLD"
        assert rows[0][1] == "gold_perp"
        assert rows[0][2] == "FUNDING"
        assert round(rows[0][3], 2) == 67.67
        assert rows[1][0] == "pos_xyz_GOLD"
        assert rows[1][2] == "FEE"
        assert round(rows[1][3], 2) == -0.55
        assert rows[2][0] == "pos_hyna_HYPE"
        assert rows[2][1] == "hype_perp"
        assert rows[2][2] == "FUNDING"
        assert round(rows[2][3], 2) == 3.25

        funding_calls = [call for call in calls if call[0] == "userFunding"]
        fill_calls = [call for call in calls if call[0] == "userFillsByTime"]
        assert funding_calls and fill_calls
        assert all(call[3] is not None for call in funding_calls)
        assert {call[1] for call in funding_calls} == {"xyz", "hyna"}

    print("hyperliquid cashflow tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
