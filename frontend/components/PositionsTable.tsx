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

  function TooltipHeader({ label, tooltip }: { label: string; tooltip: string }) {
    return (
      <th>
        <span className="relative group inline-flex items-center gap-1">
          <span className="border-b border-dotted border-gray-500 cursor-help">{label}</span>
          <svg
            className="w-3 h-3 text-gray-500 group-hover:text-gray-300 transition-colors cursor-help"
            viewBox="0 0 16 16"
            fill="currentColor"
            aria-hidden="true"
          >
            <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 2a1 1 0 1 1 0 2 1 1 0 0 1 0-2zm-.25 3.5h.5a.75.75 0 0 1 .75.75v3.5a.25.25 0 0 0 .25.25h.25v1h-3v-1h.25a.25.25 0 0 0 .25-.25v-2.5a.25.25 0 0 0-.25-.25H6.5v-1h1.25z" />
          </svg>
          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 hidden group-hover:block pointer-events-none">
            <div className="bg-gray-900 border border-gray-700 rounded px-3 py-2 text-xs text-gray-200 whitespace-pre-line w-64 shadow-lg">
              {tooltip}
            </div>
            <div className="w-2 h-2 bg-gray-900 border-r border-b border-gray-700 rotate-45 mx-auto -mt-1" />
          </div>
        </span>
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
              <TooltipHeader
                label="Exit Spread"
                tooltip={`Exit Spread = (spot_bid / perp_ask) - 1\nMeasures the current basis cost to close the position.\nNegative = you'd lose that many bps on the round-trip.`}
              />
              <TooltipHeader
                label="Spread P&L"
                tooltip={`Spread P&L = exit_spread - entry_spread (in bps)\nPositive = spread narrowed since entry (profit).\nNegative = spread widened since entry (loss).`}
              />
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