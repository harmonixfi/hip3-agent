"use client";

import { useState } from "react";
import { formatUSD, formatPct, formatBps, pnlColor } from "@/lib/format";
import type { ClosedPosition } from "@/lib/types";

type SortKey = "base" | "duration_days" | "amount_usd" | "net_pnl" | "net_apr";

/** API may omit or null numeric fields; coalesce before arithmetic (avoids NaN in totals/sort). */
function num(v: number | null | undefined): number {
  return v ?? 0;
}

interface Props {
  closedPositions: ClosedPosition[];
}

export default function ClosedPositionsClient({ closedPositions }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("net_apr");
  const [sortAsc, setSortAsc] = useState(false);

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(key === "base");
    }
  }

  const sorted = [...closedPositions].sort((a, b) => {
    if (sortKey === "base") {
      const cmp = a.base.localeCompare(b.base);
      return sortAsc ? cmp : -cmp;
    }
    const va = num(a[sortKey] as number | null | undefined);
    const vb = num(b[sortKey] as number | null | undefined);
    const cmp = va - vb;
    return sortAsc ? cmp : -cmp;
  });

  const totals = closedPositions.reduce(
    (acc, p) => ({
      spread: acc.spread + num(p.realized_spread_pnl),
      funding: acc.funding + num(p.total_funding_earned),
      fees: acc.fees + num(p.total_fees_paid),
      net: acc.net + num(p.net_pnl),
    }),
    { spread: 0, funding: 0, fees: 0, net: 0 },
  );

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
      {/* Summary row */}
      <div className="grid grid-cols-4 gap-4 mb-4 pb-4 border-b border-gray-800">
        <div>
          <div className="text-xs text-gray-500">Total Spread P&L</div>
          <div className={`text-lg font-semibold tabular-nums ${pnlColor(totals.spread)}`}>
            {formatUSD(totals.spread)}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500">Total Funding</div>
          <div className={`text-lg font-semibold tabular-nums ${pnlColor(totals.funding)}`}>
            {formatUSD(totals.funding)}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500">Total Fees</div>
          <div className={`text-lg font-semibold tabular-nums ${pnlColor(totals.fees)}`}>
            {formatUSD(totals.fees)}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500">Total Net P&L</div>
          <div className={`text-lg font-semibold tabular-nums ${pnlColor(totals.net)}`}>
            {formatUSD(totals.net)}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <SortHeader label="Base" sortId="base" />
              <SortHeader label="Duration" sortId="duration_days" />
              <SortHeader label="Amount" sortId="amount_usd" />
              <th className="text-right">Entry Spread</th>
              <th className="text-right">Exit Spread</th>
              <th className="text-right">Spread P&L</th>
              <th className="text-right">Funding</th>
              <th className="text-right">Fees</th>
              <SortHeader label="Net P&L" sortId="net_pnl" />
              <SortHeader label="Net APR" sortId="net_apr" />
            </tr>
          </thead>
          <tbody>
            {sorted.map((p) => (
              <tr
                key={p.position_id}
                className={`hover:bg-gray-800/50 transition-colors ${
                  num(p.net_pnl) >= 0
                    ? "border-l-2 border-l-green-500/30"
                    : "border-l-2 border-l-red-500/30"
                }`}
              >
                <td className="font-medium text-white">{p.base}</td>
                <td className="tabular-nums">{p.duration_days}d</td>
                <td className="text-right tabular-nums">{formatUSD(p.amount_usd)}</td>
                <td className="text-right tabular-nums">
                  {formatBps(p.entry_spread_bps)}
                </td>
                <td className="text-right tabular-nums">
                  {formatBps(p.exit_spread_bps)}
                </td>
                <td className={`text-right tabular-nums ${pnlColor(p.realized_spread_pnl)}`}>
                  {formatUSD(p.realized_spread_pnl)}
                </td>
                <td className={`text-right tabular-nums ${pnlColor(p.total_funding_earned)}`}>
                  {formatUSD(p.total_funding_earned)}
                </td>
                <td className={`text-right tabular-nums ${pnlColor(p.total_fees_paid)}`}>
                  {formatUSD(p.total_fees_paid)}
                </td>
                <td className={`text-right tabular-nums font-medium ${pnlColor(p.net_pnl)}`}>
                  {formatUSD(p.net_pnl)}
                </td>
                <td className={`text-right tabular-nums font-medium ${pnlColor(p.net_apr)}`}>
                  {formatPct(p.net_apr, 1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
