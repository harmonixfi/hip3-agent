"""Manual cashflow + APR: scenarios with explicit numbers.

Formula (same as ``tracking.vault.apr.cashflow_adjusted_apr``)::

    organic_change = (current_equity - prior_equity) - net_external_cashflows
    apr = (organic_change / prior_equity) / period_days * 365

``apr`` is in “percent points” style (e.g. 18.25 means ~18.25% annualized) for a 1-day window.

POST /api/cashflows/manual dual-writes then calls ``recalc_snapshots`` when the cashflow ``ts`` is
strictly before ``MAX(vault_strategy_snapshots.ts)``.

----------------------------------------------------------------------------
Test setup (what this file builds)
----------------------------------------------------------------------------

**Database**

- Fresh **SQLite** file per test (``tempfile``, deleted in ``finally``).
- **Schemas applied in order**: ``tracking/sql/schema_pm_v3.sql`` (portfolio / ``pm_cashflows`` for
  the manual POST dual-write), then ``tracking/sql/schema_vault.sql`` (strategies, snapshots,
  ``vault_cashflows``). Both are required so ``insert_manual_deposit_withdraw_dual`` and APR
  recalc see the same tables as production.

**Timeline (all tests use the same shape)**

- ``DAY_MS = 86400000`` (one calendar day in ms).
- ``ts_y`` (“yesterday” bar): ``now - 2 * DAY_MS``
- ``ts_t`` (“today” bar): ``now - 1 * DAY_MS``
- So the span from first snapshot to second is **exactly one day** → ``period_days == 1.0`` in the
  APR math for the *second* bar (the “today” row we assert on).
- ``ts_cf`` (mid-period cashflow time): ``ts_y + DAY_MS // 2`` → strictly **after** ``ts_y`` and
  **before** ``ts_t``. That places the manual deposit/withdraw in the window
  ``[prior_ts, snapshot_ts]`` used for the **today** snapshot, so it affects ``apr_since_inception``
  at ``ts_t`` (and matches how we explain “in-period” flows).

**Fixtures**

- ``_setup_single_strategy_db(eq_y, eq_t)``: one ACTIVE strategy ``solo`` at 100% weight; two
  ``vault_strategy_snapshots`` rows (eq_y, eq_t); two ``vault_snapshots`` rows with the same total
  equity and ``strategy_weights_json`` ``{"solo":100}``. Use this for closed-form checks where
  strategy APR and vault ``total_apr`` should match.
- ``_setup_two_equal_strategies_db(leg_y, leg_t)``: two strategies ``strat_a`` / ``strat_b`` at 50%
  each; each leg has the same two timestamps; vault totals are ``2 * leg`` and weights JSON
  ``{"strat_a":50,"strat_b":50}``. Use this to show **per-strategy** APR vs **vault** APR when only
  one leg gets the manual flow.
- ``_setup_two_strategies_constant_total_realloc_db()``: prior **500 + 500 = 1000**, current **450 +
  550 = 1000** — vault total unchanged; only redistribution between A and B. Pair with a TRANSFER
  A→B equal to the snapshot shift so **organic APR is 0** everywhere (no external flow, no net
  performance).

**Seeded APR columns**

- Snapshots start with ``apr_* = 0``. Meaningful ``apr_since_inception`` / ``total_apr`` appear only
  after ``recalc_snapshots`` runs (either called directly in tests or via the API after a manual
  post).

**Two ways we recalc**

1. **Direct** ``_run_recalc_from(db_path, ts_y)``: calls ``tracking.vault.recalc.recalc_snapshots``
   from ``ts_y`` onward. Used when there are **no** manual rows yet (e.g. “no cashflow” scenario) or
   to establish a baseline before comparing behavior.
2. **Via HTTP** ``POST /api/cashflows/manual``: after dual-write + commit, the router calls
   ``recalc_snapshots`` when ``ts < MAX(vault_strategy_snapshots.ts)``. Our ``ts_cf`` is always
   before ``ts_t``, so recalc runs and the “today” row picks up the new ``vault_cashflows`` sums.

**Environment**

- ``HARMONIX_API_KEY`` / ``HARMONIX_DB_PATH`` set so ``TestClient`` hits the temp DB and auth passes.
- ``get_settings.cache_clear()`` before importing ``app`` so each test picks up the current DB path.

**Assertions**

- ``expected_apr(...)`` wraps ``cashflow_adjusted_apr`` so expected numbers stay aligned with
  production code.
- We read ``vault_strategy_snapshots.apr_since_inception`` at ``ts_t`` and ``vault_snapshots.total_apr``
  at ``ts_t`` and compare with ``pytest.approx``.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

SCHEMA_PM = ROOT / "tracking" / "sql" / "schema_pm_v3.sql"
SCHEMA_VAULT = ROOT / "tracking" / "sql" / "schema_vault.sql"

TEST_API_KEY = "test-key-12345"

DAY_MS = 86400000


def _headers() -> dict:
    return {"X-API-Key": TEST_API_KEY}


def expected_apr(
    prior_equity: float,
    current_equity: float,
    net_cashflows: float,
    period_days: float = 1.0,
) -> float:
    """Closed-form expectation for ``apr_since_inception`` / ``total_apr`` over one period."""
    from tracking.vault.apr import cashflow_adjusted_apr

    return cashflow_adjusted_apr(current_equity, prior_equity, net_cashflows, period_days)


def _setup_single_strategy_db(
    equity_yesterday: float,
    equity_today: float,
) -> tuple[Path, int, int, int]:
    """One ACTIVE strategy; two daily snapshots; cashflow ts between them.

    Returns (db_path, ts_yesterday, ts_today, ts_cashflow_mid).
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = Path(tmp.name)
    tmp.close()

    now_ms = int(time.time() * 1000)
    ts_y = now_ms - 2 * DAY_MS
    ts_t = now_ms - 1 * DAY_MS
    ts_cf = ts_y + DAY_MS // 2

    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA_PM.read_text())
    con.executescript(SCHEMA_VAULT.read_text())

    con.execute(
        """
        INSERT INTO vault_strategies(
            strategy_id, name, type, status, wallets_json, target_weight_pct,
            config_json, created_at_ms, updated_at_ms
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            "solo",
            "Solo",
            "DELTA_NEUTRAL",
            "ACTIVE",
            None,
            100.0,
            None,
            now_ms,
            now_ms,
        ),
    )
    con.execute(
        """
        INSERT INTO vault_strategy_snapshots(
            strategy_id, ts, equity_usd, apr_since_inception, apr_30d, apr_7d
        ) VALUES (?,?,?,?,?,?)
        """,
        ("solo", ts_y, equity_yesterday, 0.0, 0.0, 0.0),
    )
    con.execute(
        """
        INSERT INTO vault_strategy_snapshots(
            strategy_id, ts, equity_usd, apr_since_inception, apr_30d, apr_7d
        ) VALUES (?,?,?,?,?,?)
        """,
        ("solo", ts_t, equity_today, 0.0, 0.0, 0.0),
    )
    con.execute(
        """
        INSERT INTO vault_snapshots(
            ts, total_equity_usd, strategy_weights_json, total_apr, apr_30d, apr_7d,
            net_deposits_alltime
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (
            ts_y,
            equity_yesterday,
            '{"solo":100}',
            0.0,
            0.0,
            0.0,
            0.0,
        ),
    )
    con.execute(
        """
        INSERT INTO vault_snapshots(
            ts, total_equity_usd, strategy_weights_json, total_apr, apr_30d, apr_7d,
            net_deposits_alltime
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (
            ts_t,
            equity_today,
            '{"solo":100}',
            0.0,
            0.0,
            0.0,
            0.0,
        ),
    )
    con.commit()
    con.close()
    return db_path, ts_y, ts_t, ts_cf


def _setup_two_equal_strategies_db(
    leg_yesterday: float,
    leg_today: float,
) -> tuple[Path, int, int, int]:
    """Two strategies 50/50; total = 2*leg; same timeline as single-strategy helper."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = Path(tmp.name)
    tmp.close()

    now_ms = int(time.time() * 1000)
    ts_y = now_ms - 2 * DAY_MS
    ts_t = now_ms - 1 * DAY_MS
    ts_cf = ts_y + DAY_MS // 2
    total_y = 2 * leg_yesterday
    total_t = 2 * leg_today

    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA_PM.read_text())
    con.executescript(SCHEMA_VAULT.read_text())

    for sid, name in (("strat_a", "A"), ("strat_b", "B")):
        con.execute(
            """
            INSERT INTO vault_strategies(
                strategy_id, name, type, status, wallets_json, target_weight_pct,
                config_json, created_at_ms, updated_at_ms
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (sid, name, "DELTA_NEUTRAL", "ACTIVE", None, 50.0, None, now_ms, now_ms),
        )
        con.execute(
            """
            INSERT INTO vault_strategy_snapshots(
                strategy_id, ts, equity_usd, apr_since_inception, apr_30d, apr_7d
            ) VALUES (?,?,?,?,?,?)
            """,
            (sid, ts_y, leg_yesterday, 0.0, 0.0, 0.0),
        )
        con.execute(
            """
            INSERT INTO vault_strategy_snapshots(
                strategy_id, ts, equity_usd, apr_since_inception, apr_30d, apr_7d
            ) VALUES (?,?,?,?,?,?)
            """,
            (sid, ts_t, leg_today, 0.0, 0.0, 0.0),
        )

    con.execute(
        """
        INSERT INTO vault_snapshots(
            ts, total_equity_usd, strategy_weights_json, total_apr, apr_30d, apr_7d,
            net_deposits_alltime
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (ts_y, total_y, '{"strat_a":50,"strat_b":50}', 0.0, 0.0, 0.0, 0.0),
    )
    con.execute(
        """
        INSERT INTO vault_snapshots(
            ts, total_equity_usd, strategy_weights_json, total_apr, apr_30d, apr_7d,
            net_deposits_alltime
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (ts_t, total_t, '{"strat_a":50,"strat_b":50}', 0.0, 0.0, 0.0, 0.0),
    )
    con.commit()
    con.close()
    return db_path, ts_y, ts_t, ts_cf


def _setup_two_strategies_constant_total_realloc_db() -> tuple[Path, int, int, int]:
    """Prior A=500 B=500 (1000); current A=450 B=550 (1000). Same timeline as other helpers.

    Interprets as pure reallocation: +50 on B matches −50 on A. Use with TRANSFER 50 from A→B.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = Path(tmp.name)
    tmp.close()

    now_ms = int(time.time() * 1000)
    ts_y = now_ms - 2 * DAY_MS
    ts_t = now_ms - 1 * DAY_MS
    ts_cf = ts_y + DAY_MS // 2
    total = 1000.0

    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA_PM.read_text())
    con.executescript(SCHEMA_VAULT.read_text())

    legs = (("strat_a", "A", 500.0, 450.0), ("strat_b", "B", 500.0, 550.0))
    for sid, name, eq_y, eq_t in legs:
        con.execute(
            """
            INSERT INTO vault_strategies(
                strategy_id, name, type, status, wallets_json, target_weight_pct,
                config_json, created_at_ms, updated_at_ms
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (sid, name, "DELTA_NEUTRAL", "ACTIVE", None, 50.0, None, now_ms, now_ms),
        )
        con.execute(
            """
            INSERT INTO vault_strategy_snapshots(
                strategy_id, ts, equity_usd, apr_since_inception, apr_30d, apr_7d
            ) VALUES (?,?,?,?,?,?)
            """,
            (sid, ts_y, eq_y, 0.0, 0.0, 0.0),
        )
        con.execute(
            """
            INSERT INTO vault_strategy_snapshots(
                strategy_id, ts, equity_usd, apr_since_inception, apr_30d, apr_7d
            ) VALUES (?,?,?,?,?,?)
            """,
            (sid, ts_t, eq_t, 0.0, 0.0, 0.0),
        )

    con.execute(
        """
        INSERT INTO vault_snapshots(
            ts, total_equity_usd, strategy_weights_json, total_apr, apr_30d, apr_7d,
            net_deposits_alltime
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (ts_y, total, '{"strat_a":50,"strat_b":50}', 0.0, 0.0, 0.0, 0.0),
    )
    con.execute(
        """
        INSERT INTO vault_snapshots(
            ts, total_equity_usd, strategy_weights_json, total_apr, apr_30d, apr_7d,
            net_deposits_alltime
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (ts_t, total, '{"strat_a":45,"strat_b":55}', 0.0, 0.0, 0.0, 0.0),
    )
    con.commit()
    con.close()
    return db_path, ts_y, ts_t, ts_cf


def _run_recalc_from(db_path: Path, since_ms: int) -> None:
    from tracking.vault.recalc import recalc_snapshots

    con = sqlite3.connect(str(db_path))
    try:
        recalc_snapshots(con, since_ms)
    finally:
        con.close()


def _read_strategy_apr(con: sqlite3.Connection, strategy_id: str, ts: int) -> float:
    row = con.execute(
        """
        SELECT apr_since_inception FROM vault_strategy_snapshots
        WHERE strategy_id = ? AND ts = ?
        """,
        (strategy_id, ts),
    ).fetchone()
    assert row is not None
    return float(row[0])


def _read_vault_total_apr(con: sqlite3.Connection, ts: int) -> float:
    row = con.execute(
        "SELECT total_apr FROM vault_snapshots WHERE ts = ?",
        (ts,),
    ).fetchone()
    assert row is not None
    return float(row[0])


def _clear_app_settings() -> None:
    from api.config import get_settings

    get_settings.cache_clear()


def test_scenario_1000_to_1100_no_cashflow_organic_apr_36_5_percent():
    """Yesterday 1000, today 1100, no external flows: organic +100 on 1000 for 1 day.

    Expected APR = (100/1000)/1*365 = 36.5 (percent points).
    """
    db_path, ts_y, ts_t, _ = _setup_single_strategy_db(1000.0, 1100.0)
    try:
        _run_recalc_from(db_path, ts_y)
        con = sqlite3.connect(str(db_path))
        try:
            apr_s = _read_strategy_apr(con, "solo", ts_t)
            apr_v = _read_vault_total_apr(con, ts_t)
        finally:
            con.close()

        want = expected_apr(1000.0, 1100.0, 0.0, 1.0)
        assert want == pytest.approx(36.5)
        assert apr_s == pytest.approx(want)
        assert apr_v == pytest.approx(want)
    finally:
        db_path.unlink(missing_ok=True)


def test_scenario_1000_to_1100_with_deposit_50_apr_18_25_percent_strategy_and_vault():
    """Same marks as above, but we record a +50 deposit in-period (attributed to the strategy).

    Organic change = (1100 - 1000) - 50 = 50  →  APR = (50/1000)/1*365 = 18.25.

    After POST /manual + implicit recalc, strategy ``apr_since_inception`` and vault ``total_apr``
    at ``today`` should match that number.
    """
    os.environ["HARMONIX_API_KEY"] = TEST_API_KEY
    db_path, ts_y, ts_t, ts_cf = _setup_single_strategy_db(1000.0, 1100.0)
    os.environ["HARMONIX_DB_PATH"] = str(db_path)

    try:
        _run_recalc_from(db_path, ts_y)

        _clear_app_settings()
        from api.main import app

        client = TestClient(app)
        resp = client.post(
            "/api/cashflows/manual",
            json={
                "strategy_id": "solo",
                "account_id": "0xsolo",
                "cf_type": "DEPOSIT",
                "amount": 50.0,
                "currency": "USDC",
                "ts": ts_cf,
                "description": "deposit 50",
            },
            headers=_headers(),
        )
        assert resp.status_code == 201, resp.text

        want = expected_apr(1000.0, 1100.0, 50.0, 1.0)
        assert want == pytest.approx(18.25)

        con = sqlite3.connect(str(db_path))
        try:
            apr_s = _read_strategy_apr(con, "solo", ts_t)
            apr_v = _read_vault_total_apr(con, ts_t)
        finally:
            con.close()

        assert apr_s == pytest.approx(want)
        assert apr_v == pytest.approx(want)
    finally:
        db_path.unlink(missing_ok=True)


def test_scenario_two_legs_deposit_50_on_strat_a_only_split_apr():
    """Two equal strategies: each leg 500 → 550 (total 1000 → 1100). Record +50 deposit on A only.

    Strat A: organic = (550-500)-50 = 0  →  APR_A = 0.
    Strat B: organic = (550-500)-0 = 50  →  APR_B = (50/500)*365 = 36.5.
    Vault (all flows): organic = (1100-1000)-50 = 50  →  total APR = (50/1000)*365 = 18.25.
    """
    os.environ["HARMONIX_API_KEY"] = TEST_API_KEY
    db_path, ts_y, ts_t, ts_cf = _setup_two_equal_strategies_db(500.0, 550.0)
    os.environ["HARMONIX_DB_PATH"] = str(db_path)

    try:
        _run_recalc_from(db_path, ts_y)

        _clear_app_settings()
        from api.main import app

        client = TestClient(app)
        resp = client.post(
            "/api/cashflows/manual",
            json={
                "strategy_id": "strat_a",
                "account_id": "0xspl",
                "cf_type": "DEPOSIT",
                "amount": 50.0,
                "currency": "USDC",
                "ts": ts_cf,
                "description": "50 on A",
            },
            headers=_headers(),
        )
        assert resp.status_code == 201, resp.text

        want_a = expected_apr(500.0, 550.0, 50.0, 1.0)
        want_b = expected_apr(500.0, 550.0, 0.0, 1.0)
        want_v = expected_apr(1000.0, 1100.0, 50.0, 1.0)
        assert want_a == pytest.approx(0.0)
        assert want_b == pytest.approx(36.5)
        assert want_v == pytest.approx(18.25)

        con = sqlite3.connect(str(db_path))
        try:
            apr_a = _read_strategy_apr(con, "strat_a", ts_t)
            apr_b = _read_strategy_apr(con, "strat_b", ts_t)
            apr_v = _read_vault_total_apr(con, ts_t)
        finally:
            con.close()

        assert apr_a == pytest.approx(want_a)
        assert apr_b == pytest.approx(want_b)
        assert apr_v == pytest.approx(want_v)
    finally:
        db_path.unlink(missing_ok=True)


def test_scenario_withdraw_25_reduces_organic_vs_raw_move_single_strategy():
    """1000 → 1100 with a 25 withdraw (outflow) recorded: net flows = -25.

    Organic = 100 - (-25) = 125  →  APR = (125/1000)*365 = 45.625.
    """
    os.environ["HARMONIX_API_KEY"] = TEST_API_KEY
    db_path, ts_y, ts_t, ts_cf = _setup_single_strategy_db(1000.0, 1100.0)
    os.environ["HARMONIX_DB_PATH"] = str(db_path)

    try:
        _run_recalc_from(db_path, ts_y)

        _clear_app_settings()
        from api.main import app

        client = TestClient(app)
        resp = client.post(
            "/api/cashflows/manual",
            json={
                "strategy_id": "solo",
                "account_id": "0xwd",
                "cf_type": "WITHDRAW",
                "amount": 25.0,
                "currency": "USDC",
                "ts": ts_cf,
                "description": "withdraw 25",
            },
            headers=_headers(),
        )
        assert resp.status_code == 201, resp.text

        want = expected_apr(1000.0, 1100.0, -25.0, 1.0)
        assert want == pytest.approx(45.625)

        con = sqlite3.connect(str(db_path))
        try:
            apr_s = _read_strategy_apr(con, "solo", ts_t)
            apr_v = _read_vault_total_apr(con, ts_t)
        finally:
            con.close()

        assert apr_s == pytest.approx(want)
        assert apr_v == pytest.approx(want)
    finally:
        db_path.unlink(missing_ok=True)


def test_scenario_internal_transfer_a_to_b_constant_vault_total_zero_apr():
    """TRANSFER A→B when snapshots show only a reallocation (vault total unchanged).

    **Story that matches the numbers:** Start $500 + $500 = $1,000. End $450 + $550 = $1,000 — no gain or
    loss at vault level, only a $50 shift from A to B. Record TRANSFER $50 from A→B in the window.

    **Expected cashflow-adjusted APR:** Organic change for each strategy removes the attributed transfer:
    - A: (450−500) − (−50) = 0 → APR_A = 0.
    - B: (550−500) − 50 = 0 → APR_B = 0.
    - Vault: (1000−1000) − 0 external = 0 → APR_vault = 0.

    This is the scenario for the internal-transfer feature: the transfer explains the snapshot split, not
    an extra +$100 that would contradict “internal only.”
    """
    os.environ["HARMONIX_API_KEY"] = TEST_API_KEY
    db_path, ts_y, ts_t, ts_cf = _setup_two_strategies_constant_total_realloc_db()
    os.environ["HARMONIX_DB_PATH"] = str(db_path)

    try:
        _run_recalc_from(db_path, ts_y)

        _clear_app_settings()
        from api.main import app

        client = TestClient(app)
        resp = client.post(
            "/api/cashflows/manual",
            json={
                "cf_type": "TRANSFER",
                "amount": 50.0,
                "currency": "USDC",
                "ts": ts_cf,
                "from_strategy_id": "strat_a",
                "to_strategy_id": "strat_b",
                "description": "internal move",
            },
            headers=_headers(),
        )
        assert resp.status_code == 201, resp.text

        want_a = expected_apr(500.0, 450.0, -50.0, 1.0)
        want_b = expected_apr(500.0, 550.0, 50.0, 1.0)
        want_v = expected_apr(1000.0, 1000.0, 0.0, 1.0)
        assert want_a == pytest.approx(0.0)
        assert want_b == pytest.approx(0.0)
        assert want_v == pytest.approx(0.0)

        con = sqlite3.connect(str(db_path))
        try:
            apr_a = _read_strategy_apr(con, "strat_a", ts_t)
            apr_b = _read_strategy_apr(con, "strat_b", ts_t)
            apr_v = _read_vault_total_apr(con, ts_t)
        finally:
            con.close()

        assert apr_a == pytest.approx(want_a)
        assert apr_b == pytest.approx(want_b)
        assert apr_v == pytest.approx(want_v)
    finally:
        db_path.unlink(missing_ok=True)


def test_cashflow_on_or_after_latest_snapshot_does_not_recalc_stored_apr():
    """If ``ts`` is not before ``MAX(snapshot ts)``, APR columns stay at the pre-post recalc values."""
    os.environ["HARMONIX_API_KEY"] = TEST_API_KEY
    db_path, ts_y, ts_t, _ = _setup_single_strategy_db(1000.0, 1100.0)
    os.environ["HARMONIX_DB_PATH"] = str(db_path)

    try:
        _run_recalc_from(db_path, ts_y)
        con = sqlite3.connect(str(db_path))
        try:
            before_s = _read_strategy_apr(con, "solo", ts_t)
            before_v = _read_vault_total_apr(con, ts_t)
        finally:
            con.close()

        _clear_app_settings()
        from api.main import app

        client = TestClient(app)
        resp = client.post(
            "/api/cashflows/manual",
            json={
                "strategy_id": "solo",
                "account_id": "0xlate",
                "cf_type": "DEPOSIT",
                "amount": 50.0,
                "currency": "USDC",
                "ts": ts_t + 3600 * 1000,
                "description": "after latest snap",
            },
            headers=_headers(),
        )
        assert resp.status_code == 201, resp.text

        con = sqlite3.connect(str(db_path))
        try:
            after_s = _read_strategy_apr(con, "solo", ts_t)
            after_v = _read_vault_total_apr(con, ts_t)
        finally:
            con.close()

        assert after_s == pytest.approx(before_s)
        assert after_v == pytest.approx(before_v)
    finally:
        db_path.unlink(missing_ok=True)
