"use client";

import { useState } from "react";
import Link from "next/link";
import { formatUSD, formatPct, formatBps, pnlColor } from "@/lib/format";
import { avgSubPairBps } from "@/lib/subPairStats";
import type { Position } from "@/lib/types";

interface Props {
  positions: Position[];
}

type SortKey =
  | "base"
  | "amount_usd"
  | "unrealized_pnl"
  | "funding_earned"
  | "carry_apr"
  | "exit_spread";

export default function PositionsTable({ positions }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("base");
  const [sortAsc, setSortAsc] = useState(true);

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(key === "base"); // alpha ascending, numeric descending
    }
  }

  function getSortValue(p: Position, key: SortKey): number | string {
    switch (key) {
      case "base":
        return p.base;
      case "amount_usd":
        return p.amount_usd;
      case "unrealized_pnl":
        return p.unrealized_pnl ?? 0;
      case "funding_earned":
        return p.funding_earned;
      case "carry_apr":
        return p.carry_apr ?? 0;
      case "exit_spread":
        // Average exit spread across sub-pairs (only non-null legs)
        return avgSubPairBps(p.sub_pairs, "exit_spread_bps") ?? 0;
    }
  }

  const sorted = [...positions].sort((a, b) => {
    const va = getSortValue(a, sortKey);
    const vb = getSortValue(b, sortKey);
    const cmp = typeof va === "string" ? va.localeCompare(vb as string) : (va as number) - (vb as number);
    return sortAsc ? cmp : -cmp;
  });

  function SortHeader({ label, sortId }: { label: string; sortId: SortKey }) {
    const isActive = sortKey === sortId;
    return (
      <th
        onClick={() => handleSort(sortId)}
        className="cursor-pointer select-none hover:text-gray-200 transition-colors"
      >
        {label}
        {isActive && (
          <span className="ml-1 text-gray-500">
            {sortAsc ? "\u25B2" : "\u25BC"}
          </span>
        )}
      </th>
    );
  }

  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
        Open Positions
      </div>
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <SortHeader label="Base" sortId="base" />
              <th>Status</th>
              <SortHeader label="Amount" sortId="amount_usd" />
              <SortHeader label="uPnL" sortId="unrealized_pnl" />
              <SortHeader label="Funding" sortId="funding_earned" />
              <SortHeader label="Carry APR" sortId="carry_apr" />
              <SortHeader label="Exit Spread" sortId="exit_spread" />
              <th>Spread P&L</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((p) => {
              const avgExitSpread = avgSubPairBps(p.sub_pairs, "exit_spread_bps");
              const avgSpreadPnl = avgSubPairBps(p.sub_pairs, "spread_pnl_bps");

              return (
                <tr key={p.position_id} className="hover:bg-gray-800/50 transition-colors">
                  <td>
                    <Link
                      href={`/positions/${p.position_id}`}
                      className="text-blue-400 hover:text-blue-300 font-medium"
                    >
                      {p.base}
                    </Link>
                  </td>
                  <td>
                    <span
                      className={`text-xs px-1.5 py-0.5 rounded ${
                        p.status === "OPEN"
                          ? "bg-green-900/30 text-green-400"
                          : p.status === "PAUSED"
                            ? "bg-yellow-900/30 text-yellow-400"
                            : p.status === "EXITING"
                              ? "bg-orange-900/30 text-orange-400"
                              : "bg-gray-800 text-gray-400"
                      }`}
                    >
                      {p.status}
                    </span>
                  </td>
                  <td className="text-right tabular-nums">
                    {formatUSD(p.amount_usd)}
                  </td>
                  <td className={`text-right tabular-nums ${pnlColor(p.unrealized_pnl)}`}>
                    {formatUSD(p.unrealized_pnl)}
                  </td>
                  <td className={`text-right tabular-nums ${pnlColor(p.funding_earned)}`}>
                    {formatUSD(p.funding_earned)}
                  </td>
                  <td className={`text-right tabular-nums ${pnlColor(p.carry_apr)}`}>
                    {p.carry_apr != null ? formatPct(p.carry_apr, 1) : "\u2014"}
                  </td>
                  <td className="text-right tabular-nums">
                    {formatBps(avgExitSpread)}
                  </td>
                  <td className={`text-right tabular-nums ${pnlColor(avgSpreadPnl)}`}>
                    {formatBps(avgSpreadPnl)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}