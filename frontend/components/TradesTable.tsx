"use client";

import Link from "next/link";
import type { Trade } from "@/lib/trades";
import { formatUSD, formatBps } from "@/lib/format";

interface Props {
  trades: Trade[];
  showPosition?: boolean; // false when embedded in position detail
}

function formatWindow(start: number, end: number): string {
  const s = new Date(start).toISOString().slice(0, 16).replace("T", " ");
  const e = new Date(end).toISOString().slice(0, 16).replace("T", " ");
  return `${s} → ${e}`;
}

export default function TradesTable({ trades, showPosition = true }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-left">
          <tr>
            <th className="p-2">Trade</th>
            {showPosition && <th className="p-2">Position</th>}
            <th className="p-2">Type</th>
            <th className="p-2">State</th>
            <th className="p-2">Window</th>
            <th className="p-2">Long Size</th>
            <th className="p-2">Long Notional</th>
            <th className="p-2">Long Avg Px</th>
            <th className="p-2">Short Size</th>
            <th className="p-2">Short Notional</th>
            <th className="p-2">Short Avg Px</th>
            <th className="p-2">Spread (bps)</th>
            <th className="p-2">Realized P&amp;L (bps)</th>
            <th className="p-2">Fees</th>
            <th className="p-2">Fills</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => (
            <tr key={t.trade_id} className="border-t hover:bg-gray-50">
              <td className="p-2">
                <Link href={`/trades/${t.trade_id}`} className="text-blue-600 hover:underline">
                  {t.trade_id}
                </Link>
                {t.unassigned_fills_count ? (
                  <span className="ml-2 rounded bg-yellow-100 px-1 text-xs text-yellow-800">
                    ⚠ {t.unassigned_fills_count} late
                  </span>
                ) : null}
              </td>
              {showPosition && (
                <td className="p-2">
                  <Link href={`/positions/${t.position_id}`} className="text-blue-600 hover:underline">
                    {t.position_id}
                  </Link>
                </td>
              )}
              <td className="p-2">{t.trade_type}</td>
              <td className="p-2">
                <span
                  className={
                    t.state === "DRAFT"
                      ? "rounded bg-gray-200 px-1 text-xs"
                      : "rounded bg-green-100 px-1 text-xs text-green-800"
                  }
                >
                  {t.state}
                </span>
              </td>
              <td className="p-2 whitespace-nowrap">{formatWindow(t.start_ts, t.end_ts)}</td>
              <td className="p-2">{t.long_size != null ? t.long_size.toFixed(4) : "\u2014"}</td>
              <td className="p-2">{t.long_notional != null ? formatUSD(t.long_notional) : "\u2014"}</td>
              <td className="p-2">{t.long_avg_px != null ? t.long_avg_px.toFixed(4) : "\u2014"}</td>
              <td className="p-2">{t.short_size != null ? t.short_size.toFixed(4) : "\u2014"}</td>
              <td className="p-2">{t.short_notional != null ? formatUSD(t.short_notional) : "\u2014"}</td>
              <td className="p-2">{t.short_avg_px != null ? t.short_avg_px.toFixed(4) : "\u2014"}</td>
              <td className="p-2">{t.spread_bps != null ? formatBps(t.spread_bps) : "\u2014"}</td>
              <td className="p-2">{t.realized_pnl_bps != null ? formatBps(t.realized_pnl_bps) : "\u2014"}</td>
              <td className="p-2">
                {((t.long_fees ?? 0) + (t.short_fees ?? 0)).toFixed(2)}
              </td>
              <td className="p-2">
                {(t.long_fill_count ?? 0) + (t.short_fill_count ?? 0)}
              </td>
            </tr>
          ))}
          {trades.length === 0 && (
            <tr>
              <td colSpan={showPosition ? 15 : 14} className="p-4 text-center text-gray-500">
                No trades.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
