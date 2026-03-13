#!/usr/bin/env python3
"""Focused tests for Harmonix report helpers."""

from __future__ import annotations

import csv
import contextlib
import importlib.util
import io
import json
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def _load_report_module():
    path = ROOT / "scripts" / "report_daily_funding_with_portfolio.py"
    spec = importlib.util.spec_from_file_location("harmonix_report", path)
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
        CREATE TABLE funding_v3(
          venue TEXT,
          inst_id TEXT,
          ts INTEGER,
          funding_rate REAL,
          interval_hours REAL
        );
        """
    )
    return con


def _create_portfolio_only_db(path: Path) -> sqlite3.Connection:
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


def _create_rotation_only_db(path: Path) -> sqlite3.Connection:
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
        """
    )
    return con


def _write_loris_csv(path: Path) -> None:
    now = datetime.now(timezone.utc)
    rows = []
    for exchange, symbol, base_rate in [
        ("hyperliquid", "ETH", 0.00030),
        ("tradexyz", "SOL", 0.00026),
        ("felix", "DOGE", 0.00024),
        ("kinetiq", "ADA", 0.00022),
        ("hyena", "XRP", 0.00021),
        ("hyperliquid", "BTC", 0.00035),
        ("hyperliquid", "WEAK", 0.00002),
    ]:
        for day in range(15):
            ts = now - timedelta(hours=12 * day)
            rows.append(
                {
                    "timestamp_utc": ts.isoformat().replace("+00:00", "Z"),
                    "exchange": exchange,
                    "symbol": symbol,
                    "oi_rank": 50,
                    "funding_8h_scaled": "",
                    "funding_8h_rate": base_rate,
                }
            )
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["timestamp_utc", "exchange", "symbol", "oi_rank", "funding_8h_scaled", "funding_8h_rate"],
        )
        writer.writeheader()
        writer.writerows(rows)


def _run_cli_capture(report, argv: list[str]) -> tuple[str, str, int]:
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = report.main_for_test(argv)
    return out.getvalue(), err.getvalue(), rc


def _extract_ranked_candidates(section_text: str) -> set[str]:
    symbols: set[str] = set()
    for line in section_text.splitlines():
        if not line.startswith("- ") or ". " not in line:
            continue
        if line.startswith("- ("):
            continue
        if " | APR14 " not in line:
            continue
        parts = line.split(" | ")
        left = parts[0]
        _, ranked = left.split("- ", 1)
        _rank, symbol = ranked.split(". ", 1)
        venue = ""
        for part in parts[1:]:
            if part.startswith("venue "):
                venue = part.removeprefix("venue ").strip()
                break
        symbols.add(f"{symbol.strip()}@{venue}" if venue else symbol.strip())
    return symbols


def main() -> int:
    report = _load_report_module()
    import scripts.report_daily_funding_sections as report_sections
    from tracking.position_manager.carry import (
        _get_funding_from_csv,
        _get_historical_funding_from_csv,
        _loris_net_series_for_position,
        _resolve_loris_market,
        compute_position_carry,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "report.db"
        con = _create_db(db_path)

        for argv in [
            ["--db", str(db_path)],
            ["--db", str(db_path), "--equities"],
            ["--db", str(db_path), "--section", "unknown"],
            ["--db", str(db_path), "--section", "rotation-general", "--rotate-from", "BTC", "--rotate-to", "ETH"],
            ["--db", str(db_path), "--rotate-from", "BTC"],
            ["--db", str(db_path), "--rotate-to", "BTC"],
            ["--db", str(db_path), "--section", "rotation-general", "--top", "0"],
        ]:
            try:
                report.main_for_test(argv)
            except SystemExit as exc:
                assert exc.code != 0
            else:
                raise AssertionError(f"expected non-zero exit for argv={argv}")

        parsed = report.parse_args(["--db", str(db_path), "--section", "portfolio-summary"])
        assert parsed.db == db_path
        assert parsed.section == "portfolio-summary"
        assert parsed.top == 5

        _, direct_status = report.render_portfolio_summary_section(
            position_rows=[
                {
                    "ticker": "WARN",
                    "perp_venue": "hyperliquid",
                    "amount_usd": 1000.0,
                    "start_time": "2026-03-11 00:00Z",
                    "avg_15d_funding_usd_per_day": 1.0,
                    "funding_1d_usd": 1.0,
                    "funding_2d_usd": 2.0,
                    "funding_3d_usd": 3.0,
                    "open_fees_usd": None,
                    "breakeven_days": None,
                    "advisory": "KEEP",
                    "reason": "steady carry",
                }
            ],
            flagged_positions=[{"symbol": "WARN", "issue": "open fees unresolved", "mode": "rendered with fallback values"}],
            snapshot_ts="2026-03-11T00:00:00+00:00",
            warnings=[],
            fmt_money=report._fmt_money,
            fmt_days=report._fmt_days,
        )
        assert direct_status.state == "DEGRADED"
        assert report_sections.normalize_symbol(" flx:doge/usdc ") == "DOGE"
        assert report_sections.normalize_symbol("BTC-PERP") == "BTC"
        assert report._position_advisory({"apr_cur": 25.0, "apr_14d": report_sections.APR14_MIN_THRESHOLD}, 5.0, 1.0) == (
            "MONITOR",
            "APR14 below threshold",
        )
        threshold_candidate = report.CandidateRow(
            symbol="EDGE20",
            exchange="hyperliquid",
            oi_rank=1,
            latest_ts=datetime.now(timezone.utc),
            apr_latest=25.0,
            apr_1d=25.0,
            apr_2d=25.0,
            apr_3d=25.0,
            apr_7d=25.0,
            apr_14d=report_sections.APR14_MIN_THRESHOLD,
            avg_15d_rate_8h=0.0002,
            stability_score=22.0,
            flags=[],
        )
        assert report_sections._candidate_reason(threshold_candidate, set()) == (
            f"APR14 {report_sections.APR14_MIN_THRESHOLD:.2f}% <= {report_sections.APR14_MIN_THRESHOLD:.1f}% threshold"
        )
        assert report_sections._is_candidate_eligible(threshold_candidate) is False

        stdout, stderr, rc = _run_cli_capture(
            report,
            ["--db", str(db_path), "--section", "portfolio-summary"],
        )
        assert rc == 0
        assert stdout.splitlines()[0] == "## Portfolio Summary"
        assert stdout.splitlines()[1] == "(no open positions tracked)"
        assert "### Flagged Positions" in stdout
        assert len(stderr.splitlines()) == 1
        metadata = json.loads(stderr.splitlines()[0])
        assert metadata["section"] == "portfolio-summary"
        assert metadata["state"] in {"NORMAL", "DEGRADED"}
        assert metadata["hard_fail"] is False
        assert metadata["snapshot_ts"]

        empty_db_path = tmp / "empty_report.db"
        empty_con = _create_db(empty_db_path)
        empty_con.commit()
        empty_con.close()

        stdout_empty, stderr_empty, rc_empty = _run_cli_capture(
            report,
            ["--db", str(empty_db_path), "--section", "portfolio-summary"],
        )
        assert rc_empty == 0
        assert stdout_empty.splitlines()[0] == "## Portfolio Summary"
        assert stdout_empty.splitlines()[1] == "(no open positions tracked)"
        assert "### Flagged Positions" in stdout_empty
        assert len(stderr_empty.splitlines()) == 1
        metadata_empty = json.loads(stderr_empty.splitlines()[0])
        assert metadata_empty["section"] == "portfolio-summary"
        assert metadata_empty["hard_fail"] is False
        assert metadata_empty["snapshot_ts"]

        no_carry_db_path = tmp / "no_carry_report.db"
        no_carry_con = _create_portfolio_only_db(no_carry_db_path)
        no_carry_start_ms = 1_700_000_000_000
        no_carry_con.execute(
            "INSERT INTO pm_positions(position_id, venue, strategy, status, created_at_ms, updated_at_ms, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("ETH_SPOT_PERP", "hyperliquid", "SPOT_PERP", "OPEN", no_carry_start_ms, no_carry_start_ms, json.dumps({"base": "ETH", "amount_usd": 5000})),
        )
        no_carry_con.executemany(
            "INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, entry_price, current_price, unrealized_pnl, realized_pnl, status, opened_at_ms, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("ETH_SPOT", "ETH_SPOT_PERP", "hyperliquid", "ETH", "LONG", 1.0, 2500, 2550, 0, 0, "OPEN", no_carry_start_ms, json.dumps({})),
                ("ETH_PERP", "ETH_SPOT_PERP", "hyperliquid", "ETH", "SHORT", 1.0, 2500, 2550, 0, 0, "OPEN", no_carry_start_ms, json.dumps({})),
            ],
        )
        no_carry_con.commit()
        no_carry_con.close()

        stdout_no_carry, stderr_no_carry, rc_no_carry = _run_cli_capture(
            report,
            ["--db", str(no_carry_db_path), "--section", "portfolio-summary"],
        )
        assert rc_no_carry == 0
        assert stdout_no_carry.splitlines()[0] == "## Portfolio Summary"
        assert "- ETH |" in stdout_no_carry
        assert "**INVESTIGATE** (carry inputs degraded)" in stdout_no_carry
        assert "### Flagged Positions" in stdout_no_carry
        assert "- ETH | carry inputs degraded | rendered with degraded advisory" in stdout_no_carry
        assert len(stderr_no_carry.splitlines()) == 1
        metadata_no_carry = json.loads(stderr_no_carry.splitlines()[0])
        assert metadata_no_carry["section"] == "portfolio-summary"
        assert metadata_no_carry["state"] == "DEGRADED"
        assert metadata_no_carry["hard_fail"] is False
        assert metadata_no_carry["warnings"]
        assert metadata_no_carry["warnings"][0].startswith("carry inputs degraded:")
        assert metadata_no_carry["snapshot_ts"]

        malformed_db_path = tmp / "malformed_report.db"
        malformed_con = sqlite3.connect(str(malformed_db_path))
        malformed_con.executescript(
            """
            CREATE TABLE pm_positions(position_id TEXT PRIMARY KEY);
            CREATE TABLE pm_legs(leg_id TEXT PRIMARY KEY);
            CREATE TABLE pm_cashflows(cashflow_id INTEGER PRIMARY KEY AUTOINCREMENT);
            """
        )
        malformed_con.commit()
        malformed_con.close()

        stdout_malformed, stderr_malformed, rc_malformed = _run_cli_capture(
            report,
            ["--db", str(malformed_db_path), "--section", "portfolio-summary"],
        )
        assert rc_malformed == 1
        assert stdout_malformed == ""
        assert len(stderr_malformed.splitlines()) == 1
        metadata_malformed = json.loads(stderr_malformed.splitlines()[0])
        assert metadata_malformed["section"] == "portfolio-summary"
        assert metadata_malformed["state"] == "HARD_FAIL"
        assert metadata_malformed["hard_fail"] is True
        assert metadata_malformed["warnings"]
        assert metadata_malformed["warnings"][0].startswith("malformed required schema:")
        assert metadata_malformed["snapshot_ts"]

        bad_db_path = tmp / "bad_report.db"
        bad_con = sqlite3.connect(str(bad_db_path))
        bad_con.execute("CREATE TABLE pm_positions(position_id TEXT PRIMARY KEY)")
        bad_con.commit()
        bad_con.close()

        stdout_bad, stderr_bad, rc_bad = _run_cli_capture(
            report,
            ["--db", str(bad_db_path), "--section", "portfolio-summary"],
        )
        assert rc_bad == 1
        assert stdout_bad == ""
        assert len(stderr_bad.splitlines()) == 1
        metadata_bad = json.loads(stderr_bad.splitlines()[0])
        assert metadata_bad["section"] == "portfolio-summary"
        assert metadata_bad["state"] == "HARD_FAIL"
        assert metadata_bad["hard_fail"] is True
        assert metadata_bad["warnings"][0].startswith("missing required tables:")
        assert metadata_bad["snapshot_ts"] is None

        stdout_unimplemented, stderr_unimplemented, rc_unimplemented = _run_cli_capture(
            report,
            ["--db", str(bad_db_path), "--section", "rotation-general"],
        )
        assert rc_unimplemented == 1
        assert stdout_unimplemented == ""
        metadata_unimplemented = json.loads(stderr_unimplemented.strip())
        assert metadata_unimplemented["section"] == "rotation-general"
        assert metadata_unimplemented["state"] == "HARD_FAIL"
        assert metadata_unimplemented["hard_fail"] is True
        assert metadata_unimplemented["warnings"][0].startswith("malformed required schema:")

        carry_schema_db_path = tmp / "carry_schema_report.db"
        carry_schema_con = sqlite3.connect(str(carry_schema_db_path))
        carry_schema_con.executescript(
            """
            CREATE TABLE pm_positions(
              position_id TEXT PRIMARY KEY,
              venue TEXT,
              strategy TEXT,
              status TEXT,
              created_at_ms INTEGER,
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
        carry_schema_start_ms = 1_700_000_000_000
        carry_schema_con.execute(
            "INSERT INTO pm_positions(position_id, venue, strategy, status, created_at_ms, meta_json) VALUES (?, ?, ?, ?, ?, ?)",
            ("SOL_SPOT_PERP", "hyperliquid", "SPOT_PERP", "OPEN", carry_schema_start_ms, json.dumps({"base": "SOL", "amount_usd": 2500})),
        )
        carry_schema_con.executemany(
            "INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, entry_price, current_price, unrealized_pnl, realized_pnl, status, opened_at_ms, closed_at_ms, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("SOL_SPOT", "SOL_SPOT_PERP", "hyperliquid", "SOL", "LONG", 10.0, 100, 105, 0, 0, "OPEN", carry_schema_start_ms, None, json.dumps({})),
                ("SOL_PERP", "SOL_SPOT_PERP", "hyperliquid", "SOL", "SHORT", 10.0, 100, 105, 0, 0, "OPEN", carry_schema_start_ms, None, json.dumps({})),
            ],
        )
        carry_schema_con.commit()
        carry_schema_con.close()

        stdout_carry_schema, stderr_carry_schema, rc_carry_schema = _run_cli_capture(
            report,
            ["--db", str(carry_schema_db_path), "--section", "portfolio-summary"],
        )
        assert rc_carry_schema == 1
        assert stdout_carry_schema == ""
        assert len(stderr_carry_schema.splitlines()) == 1
        metadata_carry_schema = json.loads(stderr_carry_schema.splitlines()[0])
        assert metadata_carry_schema["section"] == "portfolio-summary"
        assert metadata_carry_schema["state"] == "HARD_FAIL"
        assert metadata_carry_schema["hard_fail"] is True
        assert metadata_carry_schema["warnings"]
        assert metadata_carry_schema["warnings"][0].startswith("malformed required schema:")
        assert "updated_at_ms" in metadata_carry_schema["warnings"][0] or "closed_at_ms" in metadata_carry_schema["warnings"][0]
        assert metadata_carry_schema["snapshot_ts"]

        fresh_felix_cache = tmp / "felix_fresh.json"
        fresh_felix_cache.write_text(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "symbols": ["DOGE", " doge "],
                }
            ),
            encoding="utf-8",
        )
        stale_felix_cache = tmp / "felix_stale.json"
        stale_felix_cache.write_text(
            json.dumps(
                {
                    "timestamp": (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat(),
                    "symbols": ["DOGE"],
                }
            ),
            encoding="utf-8",
        )

        original_cache = report.FELIX_EQUITIES_CACHE
        original_loader = report.load_rotation_candidates
        report.FELIX_EQUITIES_CACHE = fresh_felix_cache

        rotation_db_path = tmp / "rotation_report.db"
        rotation_con = _create_rotation_only_db(rotation_db_path)
        rotation_con.execute(
            "INSERT INTO pm_positions(position_id, venue, strategy, status, created_at_ms, updated_at_ms, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "BTC_HOLD_ROTATION",
                "hyperliquid",
                "SPOT_PERP",
                "OPEN",
                1_700_000_000_000,
                1_700_000_000_000,
                json.dumps({"base": "BTC", "amount_usd": 1000}),
            ),
        )
        rotation_con.commit()
        rotation_con.close()

        fixture_now = datetime.now(timezone.utc)

        def candidate(symbol: str, apr_14d: float, apr_7d: float, apr_latest: float, flags: list[str], exchange: str = "hyperliquid") -> object:
            return report.CandidateRow(
                symbol=symbol,
                exchange=exchange,
                oi_rank=25,
                latest_ts=fixture_now,
                apr_latest=apr_latest,
                apr_1d=apr_latest,
                apr_2d=apr_7d,
                apr_3d=apr_7d,
                apr_7d=apr_7d,
                apr_14d=apr_14d,
                avg_15d_rate_8h=0.0003,
                stability_score=0.55 * apr_14d + 0.30 * apr_7d + 0.15 * apr_latest,
                flags=flags,
            )

        fixture_candidates = [
            candidate("ATOM", 42.0, 39.0, 37.0, []),
            candidate(" flx:doge/usdc ", 41.0, 38.0, 36.0, []),
            candidate(" xyz:btc/usdc ", 40.0, 37.0, 35.0, []),
            candidate("PUMP", 29.0, 27.0, 25.0, [], exchange="hyperliquid"),
            candidate("PUMP", 31.0, 29.0, 28.0, [], exchange="hyena"),
            candidate("WEAKAPR", 0.5, 0.4, 0.3, []),
            candidate("STALECOIN", 44.0, 40.0, 39.0, ["STALE"]),
            candidate("LOWSAMPLE", 43.0, 40.0, 38.0, ["LOW_14D_SAMPLE", "LOW_3D_SAMPLE"]),
            candidate("BROKEN", 45.0, 40.0, 37.0, ["BROKEN_PERSISTENCE"]),
            candidate("STRUCT", 46.0, 42.0, 39.0, ["SEVERE_STRUCTURE"]),
        ]

        def fixture_loader(*_args, **_kwargs):
            return fixture_candidates, {"latest_ts": fixture_now.isoformat(), "degraded": False, "reason": None}

        report.load_rotation_candidates = fixture_loader

        stdout_general, stderr_general, rc_general = _run_cli_capture(
            report,
            ["--db", str(rotation_db_path), "--section", "rotation-general", "--top", "10"],
        )
        stdout_equities, stderr_equities, rc_equities = _run_cli_capture(
            report,
            ["--db", str(rotation_db_path), "--section", "rotation-equities", "--top", "10"],
        )
        assert rc_general == 0
        assert rc_equities == 0
        assert "## Top 10 Rotation Candidates - General" in stdout_general
        assert "## Top 10 Rotation Candidates - Equities" in stdout_equities
        assert _extract_ranked_candidates(stdout_general) == {"ATOM@hyperliquid", "PUMP@hyperliquid", "PUMP@hyena"}
        assert _extract_ranked_candidates(stdout_equities) == {"DOGE@hyperliquid"}
        assert _extract_ranked_candidates(stdout_general).isdisjoint(_extract_ranked_candidates(stdout_equities))
        assert "DOGE" not in stdout_general
        assert "BTC" not in stdout_general
        assert "BTC" not in stdout_equities
        assert "venue hyperliquid" in stdout_general
        assert "venue hyena" in stdout_general
        assert "### Flagged Candidates" in stdout_general
        assert "### Flagged Candidates" in stdout_equities
        assert "WEAKAPR" in stdout_general
        assert "STALECOIN" in stdout_general
        assert "LOWSAMPLE" in stdout_general
        assert "BROKEN" in stdout_general
        assert "STRUCT" in stdout_general
        meta_general = json.loads(stderr_general.strip())
        meta_equities = json.loads(stderr_equities.strip())
        assert meta_general["section"] == "rotation-general"
        assert meta_general["state"] == "NORMAL"
        assert meta_general["hard_fail"] is False
        assert meta_equities["section"] == "rotation-equities"
        assert meta_equities["state"] == "NORMAL"
        assert meta_equities["hard_fail"] is False
        assert "flx:DOGE" not in stdout_equities
        assert "xyz:BTC" not in stdout_general
        assert "xyz:BTC" not in stdout_equities

        stdout_general_15, stderr_general_15, rc_general_15 = _run_cli_capture(
            report,
            ["--db", str(rotation_db_path), "--section", "rotation-general", "--top", "15"],
        )
        assert rc_general_15 == 0
        assert "## Top 15 Rotation Candidates - General" in stdout_general_15
        assert json.loads(stderr_general_15.strip())["state"] == "NORMAL"

        def missing_loris_loader(*_args, **_kwargs):
            return [], {"latest_ts": None, "degraded": True, "reason": "missing loris csv"}

        report.load_rotation_candidates = missing_loris_loader
        stdout_missing_loris, stderr_missing_loris, rc_missing_loris = _run_cli_capture(
            report,
            ["--db", str(rotation_db_path), "--section", "rotation-general", "--top", "10"],
        )
        assert rc_missing_loris == 0
        assert "(no eligible general candidates)" in stdout_missing_loris
        assert "### Flagged Candidates" in stdout_missing_loris
        assert json.loads(stderr_missing_loris.strip())["state"] == "DEGRADED"

        def stale_loris_loader(*_args, **_kwargs):
            return fixture_candidates, {"latest_ts": fixture_now.isoformat(), "degraded": True, "reason": "stale candidate funding"}

        report.load_rotation_candidates = stale_loris_loader
        stdout_global_stale, stderr_global_stale, rc_global_stale = _run_cli_capture(
            report,
            ["--db", str(rotation_db_path), "--section", "rotation-general", "--top", "10"],
        )
        assert rc_global_stale == 0
        assert "(no eligible general candidates)" in stdout_global_stale
        assert "### Flagged Candidates" in stdout_global_stale
        assert "ATOM" in stdout_global_stale
        meta_global_stale = json.loads(stderr_global_stale.strip())
        assert meta_global_stale["state"] == "DEGRADED"
        assert meta_global_stale["hard_fail"] is False

        report.load_rotation_candidates = fixture_loader
        report.FELIX_EQUITIES_CACHE = stale_felix_cache
        stdout_stale_felix, stderr_stale_felix, rc_stale_felix = _run_cli_capture(
            report,
            ["--db", str(rotation_db_path), "--section", "rotation-general", "--top", "10"],
        )
        assert rc_stale_felix == 0
        assert "ATOM" in stdout_stale_felix
        assert "PUMP" in stdout_stale_felix
        assert "Felix classification stale" in stdout_stale_felix
        assert "### Flagged Candidates" in stdout_stale_felix
        meta_stale_felix = json.loads(stderr_stale_felix.strip())
        assert meta_stale_felix["state"] == "DEGRADED"
        assert meta_stale_felix["hard_fail"] is False

        report.FELIX_EQUITIES_CACHE = tmp / "missing_felix.json"
        stdout_missing_felix, stderr_missing_felix, rc_missing_felix = _run_cli_capture(
            report,
            ["--db", str(rotation_db_path), "--section", "rotation-general", "--top", "10"],
        )
        assert rc_missing_felix == 0
        assert "(no eligible general candidates)" in stdout_missing_felix
        assert "ranked split omitted" in stdout_missing_felix
        assert "flagged candidates could not be partitioned reliably" in stdout_missing_felix
        meta_missing_felix = json.loads(stderr_missing_felix.strip())
        assert meta_missing_felix["state"] == "DEGRADED"
        assert meta_missing_felix["hard_fail"] is False

        report.FELIX_EQUITIES_CACHE = original_cache
        report.load_rotation_candidates = original_loader

        mixed_symbol_csv = tmp / "loris_mixed_symbols.csv"
        now = datetime.now(timezone.utc)
        mixed_rows = []
        for idx in range(18):
            ts = now - timedelta(hours=8 * idx)
            mixed_rows.append(
                {
                    "timestamp_utc": ts.isoformat().replace("+00:00", "Z"),
                    "exchange": "hyena",
                    "symbol": "PUMP" if idx % 2 == 0 else "hyna:pump/usdc",
                    "oi_rank": 23,
                    "funding_8h_scaled": "",
                    "funding_8h_rate": 0.00005,
                }
            )
        with mixed_symbol_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["timestamp_utc", "exchange", "symbol", "oi_rank", "funding_8h_scaled", "funding_8h_rate"],
            )
            writer.writeheader()
            writer.writerows(mixed_rows)

        mixed_candidates, mixed_meta = report.load_rotation_candidates(
            mixed_symbol_csv,
            held_symbols=[],
            top=20,
            oi_max=120,
        )
        pump_candidates = [row for row in mixed_candidates if row.symbol == "PUMP" and row.exchange == "hyena"]
        assert len(pump_candidates) == 1
        assert pump_candidates[0].apr_14d is not None
        assert pump_candidates[0].apr_14d > 5.0
        assert "LOW_14D_SAMPLE" not in pump_candidates[0].flags
        assert mixed_meta["degraded"] is False

        start_ms = 1_700_000_000_000
        meta = {"base": "BTC", "amount_usd": 10000}
        con.execute(
            "INSERT INTO pm_positions(position_id, venue, strategy, status, created_at_ms, updated_at_ms, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("BTC_SPOT_PERP", "hyperliquid", "SPOT_PERP", "OPEN", start_ms, start_ms, json.dumps(meta)),
        )
        con.executemany(
            "INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, entry_price, current_price, unrealized_pnl, realized_pnl, status, opened_at_ms, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("BTC_SPOT", "BTC_SPOT_PERP", "hyperliquid", "BTC", "LONG", 0.1, 50000, 52000, 0, 0, "OPEN", start_ms, json.dumps({})),
                ("BTC_PERP", "BTC_SPOT_PERP", "hyperliquid", "BTC", "SHORT", 0.1, 50000, 52000, 0, 0, "OPEN", start_ms, json.dumps({"margin_mode": "isolated"})),
            ],
        )

        now_ms = start_ms + 16 * 24 * 3600 * 1000
        # open fee near start
        con.execute(
            "INSERT INTO pm_cashflows(position_id, leg_id, venue, account_id, ts, cf_type, amount, currency, description, raw_json, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("BTC_SPOT_PERP", "BTC_SPOT", "hyperliquid", "acct", start_ms + 60_000, "FEE", -4.0, "USD", "open fee", "{}", "{}"),
        )
        # funding history
        for days_back, amount in [
            (1, 18.0),
            (2, 16.0),
            (3, 15.0),
            (5, 14.0),
            (10, 13.0),
            (14, 12.0),
        ]:
            con.execute(
                "INSERT INTO pm_cashflows(position_id, leg_id, venue, account_id, ts, cf_type, amount, currency, description, raw_json, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "BTC_SPOT_PERP",
                    "BTC_PERP",
                    "hyperliquid",
                    "acct",
                    now_ms - days_back * 24 * 3600 * 1000,
                    "FUNDING",
                    amount,
                    "USD",
                    "funding",
                    "{}",
                    "{}",
                ),
            )
        con.commit()

        positions = report._position_rows(con)
        assert len(positions) == 1
        pos_rows = report.build_position_rows(
            con,
            positions,
            {"BTC_SPOT_PERP": {"apr_cur": 28.0, "apr_14d": 24.0, "missing_funding_data": False}},
            now_ms,
        )
        row = pos_rows[0]
        assert row["ticker"] == "BTC"
        assert row["perp_venue"] == "hyperliquid"
        assert row["amount_usd"] == 10000
        assert row["open_fees_usd"] == 4.0
        assert row["funding_1d_usd"] == 18.0
        assert row["funding_2d_usd"] == 34.0
        assert row["funding_3d_usd"] == 49.0
        assert row["avg_15d_funding_usd_per_day"] > 0
        assert row["breakeven_days"] is not None

        stdout_populated, stderr_populated, rc_populated = _run_cli_capture(
            report,
            ["--db", str(db_path), "--section", "portfolio-summary"],
        )
        assert rc_populated == 0
        assert stdout_populated.splitlines()[0] == "## Portfolio Summary"
        assert "- BTC |" in stdout_populated
        assert "### Flagged Positions" in stdout_populated
        assert len(stderr_populated.splitlines()) == 1
        metadata_populated = json.loads(stderr_populated.splitlines()[0])
        assert metadata_populated["section"] == "portfolio-summary"
        assert metadata_populated["hard_fail"] is False
        assert metadata_populated["snapshot_ts"]

        loris_csv = tmp / "loris.csv"
        _write_loris_csv(loris_csv)
        candidates, meta = report.load_rotation_candidates(
            loris_csv,
            held_symbols=["BTC"],
            top=10,
            oi_max=200,
            stale_warn_hours=999,
        )
        assert len(candidates) >= 5
        assert not any(c.symbol == "BTC" for c in candidates)
        assert any(c.symbol == "WEAK" for c in candidates)
        assert {c.exchange for c in candidates} >= {"hyperliquid", "tradexyz", "felix", "kinetiq", "hyena"}
        scores = [c.stability_score for c in candidates]
        assert scores == sorted(scores, reverse=True)

        rotation = report.build_rotation_analysis(pos_rows, candidates, "BTC", candidates[0].symbol)
        assert rotation["close_fees_usd"] is not None
        assert rotation["open_fees_usd"] is not None
        assert rotation["total_switch_cost_usd"] == rotation["close_fees_usd"] + rotation["open_fees_usd"]
        assert rotation["expected_daily_funding_usd"] is not None

        original_loris_csv = report.LORIS_CSV
        report.LORIS_CSV = loris_csv
        stdout_rotation, stderr_rotation, rc_rotation = _run_cli_capture(
            report,
            ["--db", str(db_path), "--rotate-from", "BTC", "--rotate-to", candidates[0].symbol],
        )
        assert rc_rotation == 0
        assert "# Rotation Cost Analysis" in stdout_rotation
        assert stderr_rotation == ""
        report.LORIS_CSV = original_loris_csv

        header = report_sections.build_global_header(
            [
                report_sections.SectionStatus("portfolio-summary", "NORMAL", "2026-03-11T01:00:00Z", [], False),
                report_sections.SectionStatus("rotation-general", "DEGRADED", "2026-03-11T01:05:00Z", ["stale candidate funding"], False),
            ],
            failed_sections=["rotation-equities"],
        )
        assert "State: DEGRADED" in header
        assert "rotation-equities" in header
        assert "2026-03-11T01:05:00Z" in header
        assert "Timezone: UTC" in header

        from tracking.position_manager.registry import load_registry

        reg_path = tmp / "positions.json"
        reg_path.write_text(
            json.dumps(
                [
                    {
                        "position_id": "EXAMPLE",
                        "strategy_type": "SPOT_PERP",
                        "base": "ETH",
                        "status": "OPEN",
                        "amount_usd": 5000,
                        "open_fees_usd": 2.5,
                        "legs": [
                            {"leg_id": "A", "venue": "hyperliquid", "inst_id": "ETH", "side": "LONG", "qty": 1},
                            {"leg_id": "B", "venue": "hyperliquid", "inst_id": "ETH", "side": "SHORT", "qty": 1},
                        ],
                    }
                ]
            ),
            encoding="utf-8",
        )
        registry = load_registry(reg_path)
        assert registry[0].amount_usd == 5000
        assert registry[0].open_fees_usd == 2.5

        assert _resolve_loris_market("hyperliquid", "BTC") == ("hyperliquid", "BTC")
        assert _resolve_loris_market("hyperliquid", "xyz:GOLD") == ("tradexyz", "GOLD")
        assert _resolve_loris_market("hyperliquid", "flx:BTC") == ("felix", "BTC")
        assert _resolve_loris_market("hyperliquid", "km:ETH") == ("kinetiq", "ETH")
        assert _resolve_loris_market("hyperliquid", "hyna:HYPE") == ("hyena", "HYPE")

        gold_position = {
            "position_id": "pos_xyz_GOLD",
            "venue": "hyperliquid",
            "strategy": "SPOT_PERP",
            "status": "OPEN",
            "meta": {"amount_usd": 19950},
            "legs": [
                {"leg_id": "gold_spot", "venue": "hyperliquid", "inst_id": "XAUT0/USDC", "side": "LONG"},
                {"leg_id": "gold_perp", "venue": "hyperliquid", "inst_id": "xyz:GOLD", "side": "SHORT"},
            ],
        }
        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        for days_back, amount in [(1, -1.01), (2, -0.27), (3, -0.70), (7, 12.0), (10, 18.0), (14, 28.0)]:
            con.execute(
                "INSERT INTO pm_cashflows(position_id, leg_id, venue, account_id, ts, cf_type, amount, currency, description, raw_json, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "pos_xyz_GOLD",
                    "gold_perp",
                    "hyperliquid",
                    "acct",
                    int((now - __import__('datetime').timedelta(days=days_back)).timestamp() * 1000),
                    "FUNDING",
                    amount,
                    "USD",
                    "funding",
                    "{}",
                    "{}",
                ),
            )
        con.commit()

        gold_loris = tmp / "gold_loris.csv"
        with gold_loris.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["timestamp_utc", "exchange", "symbol", "oi_rank", "funding_8h_scaled", "funding_8h_rate"],
            )
            writer.writeheader()

        gold_carry = compute_position_carry(gold_position, con, gold_loris)
        assert gold_carry["missing_funding_data"] is False
        assert gold_carry["legs"][0]["data_source"] == "spot"
        assert gold_carry["legs"][1]["inst_id"] == "xyz:GOLD"
        assert gold_carry["legs"][1]["data_source"] == "pm_cashflows"
        assert gold_carry["apr_14d"] is not None and gold_carry["apr_14d"] > 0

        mapped_loris = tmp / "mapped_loris.csv"
        with mapped_loris.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["timestamp_utc", "exchange", "symbol", "oi_rank", "funding_8h_scaled", "funding_8h_rate"],
            )
            writer.writeheader()
            for half_hour in range(96):
                ts = now - __import__("datetime").timedelta(minutes=30 * half_hour)
                writer.writerow(
                    {
                        "timestamp_utc": ts.isoformat().replace("+00:00", "Z"),
                        "exchange": "tradexyz",
                        "symbol": "GOLD",
                        "oi_rank": 25,
                        "funding_8h_scaled": 8.0,
                        "funding_8h_rate": 0.0008,
                    }
                )
            for day in range(14):
                ts = now - __import__("datetime").timedelta(days=day)
                writer.writerow(
                    {
                        "timestamp_utc": ts.isoformat().replace("+00:00", "Z"),
                        "exchange": "hyena",
                        "symbol": "HYPE",
                        "oi_rank": 10,
                        "funding_8h_scaled": 7.0,
                        "funding_8h_rate": 0.0007,
                    }
                )

        latest_xyz = _get_funding_from_csv(mapped_loris, "hyperliquid", "xyz:GOLD")
        assert latest_xyz is not None
        assert latest_xyz["funding_8h_rate"] == 0.0008

        hist_xyz = _get_historical_funding_from_csv(mapped_loris, "hyperliquid", "xyz:GOLD", days=14)
        assert hist_xyz is not None and len(hist_xyz) >= 14

        mapped_gold_position = {
            "position_id": "pos_xyz_GOLD_csv",
            "venue": "hyperliquid",
            "strategy": "SPOT_PERP",
            "status": "OPEN",
            "meta": {"amount_usd": 19950},
            "legs": [
                {"leg_id": "gold_spot_csv", "venue": "hyperliquid", "inst_id": "XAUT0/USDC", "side": "LONG"},
                {"leg_id": "gold_perp_csv", "venue": "hyperliquid", "inst_id": "xyz:GOLD", "side": "SHORT"},
            ],
        }

        net_series, missing = _loris_net_series_for_position(mapped_gold_position, mapped_loris, window_hours=12)
        assert missing is False
        assert len(net_series) >= 12

        mapped_gold_carry = compute_position_carry(mapped_gold_position, con, mapped_loris)
        assert mapped_gold_carry["missing_funding_data"] is False
        assert mapped_gold_carry["legs"][1]["data_source"] == "loris_csv"
        assert mapped_gold_carry["legs"][1]["funding_8h_cur"] == 0.0008

        fee_position = {
            "strategy": "SPOT_PERP",
            "legs": [
                {"leg_id": "fee_spot", "venue": "hyperliquid", "inst_id": "GOLD", "side": "LONG"},
                {"leg_id": "fee_perp", "venue": "hyperliquid", "inst_id": "xyz:GOLD", "side": "SHORT"},
            ],
        }
        est_fee = report._estimate_fees_from_notional(fee_position, 1000, is_open=True)
        assert est_fee is not None and est_fee > 0

        synthetic_target = next(c for c in candidates if c.exchange == "tradexyz")
        rotation_multi = report.build_rotation_analysis(pos_rows, candidates, "BTC", synthetic_target.symbol)
        assert rotation_multi["open_fees_usd"] is not None

        hype_position = {
            "position_id": "pos_hyna_HYPE",
            "venue": "hyperliquid",
            "strategy": "SPOT_PERP",
            "status": "OPEN",
            "meta": {"amount_usd": 1000},
            "legs": [
                {"leg_id": "hype_spot", "venue": "hyperliquid", "inst_id": "HYPE/USDC", "side": "LONG"},
                {"leg_id": "hype_perp", "venue": "hyperliquid", "inst_id": "hyna:HYPE", "side": "SHORT"},
            ],
        }
        latest_hype = _get_funding_from_csv(mapped_loris, "hyperliquid", "hyna:HYPE")
        assert latest_hype is not None
        assert latest_hype["funding_8h_rate"] == 0.0007

        print("harmonix report tests passed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
