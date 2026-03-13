#!/usr/bin/env python3
"""Cron Task Runner (every 15 minutes)

Purpose
- Execute the next highest-priority task step-by-step.
- Be safe to run frequently: uses a TTL lock to avoid overlap.
- Persist progress + failures so we can resume next run.

This is intentionally simple: it does NOT try to be a full task scheduler.
It maintains a small state file with the current task id and last status.

Outputs
- Writes progress to: tracking/cron_progress.md
- Writes state to: tracking/cron_state.json

Exit codes
- 0: ok / no-op
- 1: failed (state updated)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Tuple
import re

ROOT = Path(__file__).parent.parent
STATE_PATH = ROOT / "tracking" / "cron_state.json"
LOCK_PATH = ROOT / "tracking" / "cron_lock.json"
LOG_PATH = ROOT / "tracking" / "cron_progress.md"
TASKS_PATH = ROOT / "tracking" / "TASKS_v3.md"

LOCK_TTL_SECONDS = 15 * 60  # 15 minutes


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def append_log(line: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def acquire_lock() -> bool:
    """Return True if lock acquired; False if another run is within TTL."""
    now = int(time.time())
    lock = load_json(LOCK_PATH, {})
    started = int(lock.get("startedAt", 0) or 0)
    if started and (now - started) < LOCK_TTL_SECONDS:
        return False
    save_json(LOCK_PATH, {"startedAt": now, "at": utc_now_iso()})
    return True


def release_lock() -> None:
    try:
        LOCK_PATH.unlink(missing_ok=True)
    except Exception:
        pass


def run(cmd: List[str], timeout: int = 600) -> Tuple[int, str]:
    """Run a command and capture combined output."""
    p = subprocess.run(
        cmd,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
    )
    return p.returncode, p.stdout


def parse_prioritized_tasks(tasks_md: str) -> List[str]:
    """Extract ordered task ids from TASKS_v3.md.

    Supports bullets like:
    - **V3-001** — ...
    - **T-016** — ... (legacy)
    """
    out: List[str] = []
    for line in tasks_md.splitlines():
        line = line.strip()
        if not line.startswith("**"):
            continue
        # capture the first bold token
        m = re.match(r"^\*\*(?P<tid>(?:V3|T)-\d{3})\*\*", line)
        if m:
            out.append(m.group("tid"))
    # keep order, unique
    seen = set()
    ordered = []
    for t in out:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered


def task_file_for(tid: str) -> Optional[Path]:
    """Return the canonical task file path if it exists.

    Conventions supported:
    - tracking/tasks/<tid>_*.md   (legacy)
    - tracking/tasks/<tid>-*.md   (v3)
    """
    tdir = ROOT / "tracking" / "tasks"
    if not tdir.exists():
        return None
    candidates = sorted(list(tdir.glob(f"{tid}_*.md")) + list(tdir.glob(f"{tid}-*.md")))
    return candidates[0] if candidates else None


def is_done_marker(text: str) -> bool:
    lowered = text.lower()
    return (
        "status: done" in lowered
        or "## status: done" in lowered
        or "done ✅" in lowered
        or ("## completion" in lowered and "done" in lowered)
    )


def mark_task_done(tid: str, note: str) -> None:
    tf = task_file_for(tid)
    if not tf or not tf.exists():
        return
    txt = tf.read_text(encoding="utf-8")
    if is_done_marker(txt):
        return
    # Prefer inserting a simple status header near the top.
    lines = txt.splitlines()
    out = []
    inserted = False
    for i, line in enumerate(lines):
        out.append(line)
        if not inserted and line.strip().startswith(f"# {tid}"):
            out.append("")
            out.append("## Status: done")
            out.append("")
            inserted = True
    if not inserted:
        out.append("")
        out.append("## Status: done")
        out.append("")
    out.append(f"CompletedAt: {utc_now_iso()}")
    out.append(f"CompletionNote: {note}")
    tf.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def pick_next_task(completed: List[str] = None) -> Optional[str]:
    """Pick the next incomplete task.

    Args:
        completed: List of task IDs that are already completed (for V3 tasks without files)
    """
    if completed is None:
        completed = []

    if not TASKS_PATH.exists():
        return None
    tids = parse_prioritized_tasks(TASKS_PATH.read_text(encoding="utf-8"))
    for tid in tids:
        # Skip if in completed list (for V3 tasks without files)
        if tid in completed:
            continue

        tf = task_file_for(tid)
        if not tf:
            # if no task file, still allow it as next (will be handled by state)
            return tid
        txt = tf.read_text(encoding="utf-8")
        if not is_done_marker(txt):
            return tid
    return None


def main() -> int:
    if not acquire_lock():
        return 0

    state = load_json(STATE_PATH, {
        "current": None,
        "completed": [],
        "last": {"status": None, "task": None, "at": None, "note": None},
    })

    try:
        current = state.get("current")
        # Resume failed task if exists
        if not current:
            current = pick_next_task(state.get("completed", []))
            state["current"] = current

        if not current:
            return 0

        append_log(f"[{utc_now_iso()}] RUN start task={current}")

        def ok_fail(note: str, rc: int, out: str) -> int:
            append_log(f"[{utc_now_iso()}] FAIL task={current} rc={rc} note={note}\n{out}")
            state["last"] = {"status": "fail", "task": current, "at": utc_now_iso(), "note": note}
            save_json(STATE_PATH, state)
            print(f"FAIL {current}: {note} (rc={rc})")
            return 1

        def ok_done(note: str) -> int:
            append_log(f"[{utc_now_iso()}] OK {current}: {note}")
            # Auto-mark done in the task file so the board advances without manual intervention
            try:
                mark_task_done(current, note)
            except Exception as e:
                append_log(f"[{utc_now_iso()}] WARN could not mark done for {current}: {e}")

            state["last"] = {"status": "ok", "task": current, "at": utc_now_iso(), "note": note}
            # Mark task as completed if it's not already
            completed = state.get("completed", [])
            if current not in completed:
                completed.append(current)
            state["completed"] = completed
            state["current"] = None
            save_json(STATE_PATH, state)
            print(f"OK {current}: {note}")
            return 0

        # --- Task wiring ---
        # V3 wiring (explicit: we do NOT skip tasks silently)
        if current == "V3-001":
            # Ensure schema exists + init DB
            if not (ROOT / "tracking" / "sql" / "schema_v3.sql").exists():
                return ok_fail("schema_v3.sql missing", 2, "expected tracking/sql/schema_v3.sql")
            rc, out = run(["python3", "scripts/db_v3_init.py"], timeout=120)
            if rc != 0:
                return ok_fail("db_v3_init failed", rc, out)
            return ok_done("schema_v3.sql ready + db_v3_init ok")

        if current == "V3-002":
            # Reset+backup should be safe idempotently.
            rc, out = run(["python3", "scripts/db_v3_reset_backup.py"], timeout=120)
            if rc != 0:
                return ok_fail("db_v3_reset_backup failed", rc, out)
            return ok_done("db_v3_reset_backup ok")

        if current == "V3-003":
            rc, out = run(["python3", "scripts/verify_db_v3.py"], timeout=120)
            if rc != 0:
                return ok_fail("verify_db_v3 failed", rc, out)
            return ok_done("verify_db_v3 ok")

        if current == "V3-010":
            # Normalization + unit tests
            rc, out = run(["python3", "scripts/test_okx_v3_normalize.py"], timeout=120)
            if rc != 0:
                return ok_fail("test_okx_v3_normalize failed", rc, out)
            return ok_done("okx normalization tests pass")

        if current == "V3-011":
            # Minimal OKX -> v3 ingestion + verify
            rc0, out0 = run(["python3", "scripts/db_v3_init.py"], timeout=120)
            if rc0 != 0:
                return ok_fail("db_v3_init failed", rc0, out0)
            rc1, out1 = run(["python3", "scripts/pull_okx_v3.py", "--funding-limit", "50"], timeout=900)
            if rc1 != 0:
                return ok_fail("pull_okx_v3 failed", rc1, out1)
            rc2, out2 = run(["python3", "scripts/verify_db_v3.py"], timeout=120)
            if rc2 != 0:
                return ok_fail("verify_db_v3 failed", rc2, out2)
            return ok_done("okx v3 ingestion+verify ok")

        if current == "V3-012":
            # OKX backfill from Loris (minimal: 14 days)
            rc, out = run(["python3", "scripts/backfill_okx_funding_v3.py", "--days", "14"], timeout=1800)
            if rc != 0:
                return ok_fail("backfill_okx_funding_v3 failed", rc, out)
            return ok_done("okx backfill from loris ok")

        if current == "V3-020":
            # Cost model v3: fee lookup + spread cost estimation
            rc, out = run(["python3", "tracking/analytics/cost_model_v3.py"], timeout=120)
            if rc != 0:
                return ok_fail("cost_model_v3 failed", rc, out)
            return ok_done("cost_model_v3 ok")

        if current == "V3-021":
            # SPOT↔PERP Carry screener (OKX)
            rc, out = run(["python3", "tracking/analytics/spot_perp_screener_v3.py"], timeout=180)
            if rc != 0:
                return ok_fail("spot_perp_screener_v3 failed", rc, out)
            return ok_done("spot_perp_screener_v3 ok")

        if current == "V3-022":
            # PERP↔PERP Extreme screener (cross-venue)
            rc, out = run(["python3", "tracking/analytics/perp_perp_screener_v3.py"], timeout=180)
            if rc != 0:
                return ok_fail("perp_perp_screener_v3 failed", rc, out)
            return ok_done("perp_perp_screener_v3 ok")

        if current == "V3-040":
            # Screener pipeline v3: run analytics and report
            rc1, out1 = run(["python3", "scripts/run_screeners_v3.py"], timeout=300)
            if rc1 != 0:
                return ok_fail("run_screeners_v3 failed", rc1, out1)
            return ok_done("screeners v3 ok")

        # Legacy wiring (kept only if TASKS_v3.md still lists T-XXX)
        if current in ("T-016", "T-017"):
            # idempotently run migration + verify
            rc, out = run(["python3", "scripts/migrate_db_v2.py"], timeout=900)
            if rc != 0:
                return ok_fail("migrate_db_v2 failed", rc, out)
            rc2, out2 = run(["python3", "scripts/verify_db_v2.py"], timeout=300)
            if rc2 != 0:
                return ok_fail("verify_db_v2 failed", rc2, out2)
            return ok_done("migrate+verify complete")

        if current == "T-018":
            # OKX pull (v1) + v2 migration verify as a temporary bridge.
            # NOTE: until ingestion writes directly to v2, we re-run migrate to bring v1 rows into v2.
            rc0, out0 = run(["python3", "scripts/pull_okx_market.py"], timeout=900)
            if rc0 != 0:
                return ok_fail("pull_okx_market failed", rc0, out0)
            rc, out = run(["python3", "scripts/migrate_db_v2.py"], timeout=900)
            if rc != 0:
                return ok_fail("migrate_db_v2 failed", rc, out)
            rc2, out2 = run(["python3", "scripts/verify_db_v2.py"], timeout=300)
            if rc2 != 0:
                return ok_fail("verify_db_v2 failed", rc2, out2)
            return ok_done("okx pull + v2 migrate+verify complete")

        if current == "T-019":
            # Smoke tests for analytics (still v1-backed in places):
            # - compute basis
            # - opportunity report perp_perp (db)
            rc, out = run(["python3", "scripts/compute_basis.py"], timeout=300)
            if rc != 0:
                return ok_fail("compute_basis failed", rc, out)
            rc2, out2 = run(["python3", "scripts/opportunity_report_public.py", "--strategy", "perp_perp", "--top", "5"], timeout=300)
            if rc2 != 0:
                return ok_fail("opportunity_report_public failed", rc2, out2)
            return ok_done("analytics smoke tests complete")

        if current == "T-020":
            # Pull other venues (v1) then migrate+verify.
            cmds = [
                ["python3", "scripts/pull_hyperliquid_market.py"],
                ["python3", "scripts/pull_paradex_market.py"],
                ["python3", "scripts/pull_lighter_market.py"],
                ["python3", "scripts/pull_ethereal_market.py"],
            ]
            for c in cmds:
                rcx, outx = run(c, timeout=900)
                if rcx != 0:
                    return ok_fail(f"pull failed: {' '.join(c)}", rcx, outx)
            rc, out = run(["python3", "scripts/migrate_db_v2.py"], timeout=900)
            if rc != 0:
                return ok_fail("migrate_db_v2 failed", rc, out)
            rc2, out2 = run(["python3", "scripts/verify_db_v2.py"], timeout=300)
            if rc2 != 0:
                return ok_fail("verify_db_v2 failed", rc2, out2)
            return ok_done("other venue pulls + v2 migrate+verify complete")

        # Default: unknown task id -> no-op but keep state so next run retries.
        append_log(f"[{utc_now_iso()}] NOTE task={current} not wired")
        state["last"] = {"status": "noop", "task": current, "at": utc_now_iso(), "note": "not wired"}
        save_json(STATE_PATH, state)
        return 0

    finally:
        release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
