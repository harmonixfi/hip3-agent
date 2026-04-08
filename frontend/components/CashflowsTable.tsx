"use client";

import { useEffect, useState } from "react";
import { ApiError, fetchVaultCashflows } from "@/lib/api";
import type { VaultCashflow } from "@/lib/types";

interface Props {
  refreshKey: number;
}

function strategyCell(cf: VaultCashflow): string {
  if (cf.cf_type === "TRANSFER") {
    const a = cf.from_strategy_id ?? "—";
    const b = cf.to_strategy_id ?? "—";
    return `${a} → ${b}`;
  }
  return cf.strategy_id ?? "—";
}

export default function CashflowsTable({ refreshKey }: Props) {
  const [rows, setRows] = useState<VaultCashflow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchVaultCashflows(50)
      .then((res) => {
        if (!cancelled) {
          setRows(res);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          const msg =
            e instanceof ApiError
              ? e.message
              : e instanceof Error
                ? e.message
                : "Failed to load";
          setError(msg);
          setRows(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-4">
        Cashflows
      </div>
      <p className="text-xs text-gray-500 mb-3">
        Read-only history of deposits, withdrawals, and strategy transfers used
        for strategy APR (newest first).
      </p>

      {loading && (
        <p className="text-sm text-gray-500 py-4">Loading…</p>
      )}
      {error && !loading && (
        <p className="text-red-400 text-sm py-2">{error}</p>
      )}
      {!loading && !error && rows && rows.length === 0 && (
        <p className="text-gray-500 text-sm py-4">No cashflows yet.</p>
      )}
      {!loading && !error && rows && rows.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-800">
          <table className="w-full text-sm">
            <thead className="bg-gray-900/80 text-gray-400 text-xs uppercase">
              <tr>
                <th className="px-3 py-2 text-left">Time</th>
                <th className="px-3 py-2 text-left">Type</th>
                <th className="px-3 py-2 text-right">Amount</th>
                <th className="px-3 py-2 text-left">Currency</th>
                <th className="px-3 py-2 text-left">Strategy</th>
                <th className="px-3 py-2 text-left max-w-[12rem]">Description</th>
                <th className="px-3 py-2 text-right">ID</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {rows.map((r) => (
                <tr key={r.cashflow_id} className="hover:bg-gray-800/30">
                  <td className="px-3 py-2 text-gray-300 whitespace-nowrap">
                    {new Date(r.ts).toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-gray-300">{r.cf_type}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-white">
                    {r.amount.toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </td>
                  <td className="px-3 py-2 text-gray-400">{r.currency}</td>
                  <td
                    className="px-3 py-2 text-gray-300 font-mono text-xs max-w-[14rem] truncate"
                    title={strategyCell(r)}
                  >
                    {strategyCell(r)}
                  </td>
                  <td className="px-3 py-2 text-gray-500 max-w-[12rem] truncate">
                    {r.description ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right text-gray-500 tabular-nums">
                    {r.cashflow_id}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
