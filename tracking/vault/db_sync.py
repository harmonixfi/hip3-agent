"""Database synchronization for vault strategy registry.

Syncs StrategyConfig objects to vault_strategies table.
Pattern follows tracking/position_manager/db_sync.py.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Dict, List

from .registry import StrategyConfig


def _merge_config_with_vault_name(
    config: Dict[str, Any] | None, vault_name: str
) -> Dict[str, Any]:
    base: Dict[str, Any] = dict(config) if config else {}
    base["vault_name"] = vault_name
    return base


def sync_registry(
    con: sqlite3.Connection, vault_name: str, strategies: List[StrategyConfig]
) -> int:
    """Sync strategy configs to vault_strategies table.

    Merges vault_name into each row's config_json for API consumers.
    """
    now_ms = int(time.time() * 1000)

    for s in strategies:
        row = con.execute(
            "SELECT created_at_ms FROM vault_strategies WHERE strategy_id = ?",
            (s.strategy_id,),
        ).fetchone()
        created_at_ms = row[0] if row else now_ms

        merged_config = _merge_config_with_vault_name(s.config, vault_name)
        config_json = json.dumps(merged_config, separators=(",", ":"))

        con.execute(
            """
            INSERT INTO vault_strategies(
                strategy_id, name, type, status,
                wallets_json, target_weight_pct, config_json,
                created_at_ms, updated_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(strategy_id) DO UPDATE SET
                name = excluded.name,
                type = excluded.type,
                status = excluded.status,
                wallets_json = excluded.wallets_json,
                target_weight_pct = excluded.target_weight_pct,
                config_json = excluded.config_json,
                updated_at_ms = excluded.updated_at_ms
            """,
            (
                s.strategy_id,
                s.name,
                s.type,
                s.status,
                json.dumps(s.wallets, separators=(",", ":")),
                s.target_weight_pct,
                config_json,
                created_at_ms,
                now_ms,
            ),
        )

    con.commit()
    return len(strategies)


def list_strategies(con: sqlite3.Connection) -> List[dict]:
    """List all strategies with latest snapshot data."""
    cursor = con.execute(
        """
        SELECT s.strategy_id, s.name, s.type, s.status,
               s.target_weight_pct, s.wallets_json, s.updated_at_ms,
               snap.equity_usd, snap.apr_since_inception, snap.apr_7d, snap.apr_30d, snap.ts
        FROM vault_strategies s
        LEFT JOIN vault_strategy_snapshots snap ON snap.strategy_id = s.strategy_id
            AND snap.ts = (
                SELECT MAX(ts) FROM vault_strategy_snapshots WHERE strategy_id = s.strategy_id
            )
        ORDER BY s.target_weight_pct DESC
        """
    )
    results = []
    for row in cursor.fetchall():
        results.append(
            {
                "strategy_id": row[0],
                "name": row[1],
                "type": row[2],
                "status": row[3],
                "target_weight_pct": row[4],
                "wallets": json.loads(row[5]) if row[5] else [],
                "updated_at_ms": row[6],
                "equity_usd": row[7],
                "apr_since_inception": row[8],
                "apr_7d": row[9],
                "apr_30d": row[10],
                "last_snapshot_ts": row[11],
            }
        )
    return results
