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
          meta_json TEXT,
          account_id TEXT
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
            "INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, raw_json, meta_json, account_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("gold_spot", "pos_xyz_GOLD", "hyperliquid", "XAUT0/USDC", "LONG", 2.0, "OPEN", now_ms, "{}", "{}", "acct1"),
                ("gold_perp", "pos_xyz_GOLD", "hyperliquid", "xyz:GOLD", "SHORT", 2.0, "OPEN", now_ms, "{}", "{}", "acct1"),
                ("hype_spot", "pos_hyna_HYPE", "hyperliquid", "HYPE/USDC", "LONG", 10.0, "OPEN", now_ms, "{}", "{}", "acct1"),
                ("hype_perp", "pos_hyna_HYPE", "hyperliquid", "hyna:HYPE", "SHORT", 10.0, "OPEN", now_ms, "{}", "{}", "acct1"),
            ],
        )
        con.commit()

        targets = mod._load_hyperliquid_targets(con)
        assert "acct1" in targets
        assert targets["acct1"]["xyz"]["GOLD"]["leg_id"] == "gold_perp"
        assert targets["acct1"]["hyna"]["HYPE"]["leg_id"] == "hype_perp"
        assert targets["acct1"][""]["HYPE/USDC"]["leg_id"] == "hype_spot"
        assert targets["acct1"][""]["XAUT0/USDC"]["leg_id"] == "gold_spot"

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
                return [{"time": event_ts, "delta": {"coin": "xyz:GOLD", "usdc": "67.67"}}]
            if payload["type"] == "userFunding" and dex == "hyna":
                return [{"time": event_ts, "delta": {"coin": "hyna:HYPE", "usdc": "3.25"}}]
            if payload["type"] == "userFillsByTime" and dex == "xyz":
                return [{"time": event_ts, "coin": "xyz:GOLD", "fee": "0.55"}]
            if payload["type"] == "userFillsByTime" and dex == "hyna":
                return [{"time": event_ts, "coin": "hyna:HYPE", "fee": "0.25"}]
            if payload["type"] == "userFillsByTime" and dex == "":
                return [{"time": event_ts, "coin": "@107", "fee": "0.10"}]
            return []

        class FakeConnector:
            address = "0xabc"

        mod._hl_post = fake_post  # type: ignore[attr-defined]
        mod.HyperliquidPrivateConnector = lambda: FakeConnector()  # type: ignore[assignment]

        spot_map = {107: "HYPE/USDC"}
        inserted = mod.ingest_hyperliquid(con, since_hours=24 * 15, spot_index_map=spot_map)
        assert inserted == 5

        rows = con.execute(
            "SELECT position_id, leg_id, cf_type, amount, description FROM pm_cashflows"
        ).fetchall()
        by_leg_type = {(r[1], r[2]): r for r in rows}
        assert by_leg_type[("gold_perp", "FUNDING")][3] == 67.67
        assert by_leg_type[("gold_perp", "FEE")][3] == -0.55
        assert by_leg_type[("hype_perp", "FUNDING")][3] == 3.25
        assert by_leg_type[("hype_perp", "FEE")][3] == -0.25
        assert by_leg_type[("hype_spot", "FEE")][3] == -0.10

        funding_calls = [call for call in calls if call[0] == "userFunding"]
        fill_calls = [call for call in calls if call[0] == "userFillsByTime"]
        assert funding_calls and fill_calls
        assert all(call[3] is not None for call in funding_calls)
        assert {call[1] for call in funding_calls} == {"", "xyz", "hyna"}
        assert {call[1] for call in fill_calls} == {"", "xyz", "hyna"}

    print("hyperliquid cashflow tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
