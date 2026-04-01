import { formatUSD, formatPct } from "@/lib/format";
import type { StrategySummary } from "@/lib/types";
import Link from "next/link";

interface Props {
  strategies: StrategySummary[];
}

export default function StrategyTable({ strategies }: Props) {
  if (!strategies.length) {
    return (
      <p className="text-sm text-gray-500">No strategies loaded. Run sync-registry and snapshot.</p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-800">
      <table className="w-full text-sm text-left">
        <thead className="bg-gray-900/80 text-gray-400 text-xs uppercase">
          <tr>
            <th className="px-3 py-2">Strategy</th>
            <th className="px-3 py-2">Equity</th>
            <th className="px-3 py-2">Weight</th>
            <th className="px-3 py-2">Target</th>
            <th className="px-3 py-2">APR (since inception)</th>
            <th className="px-3 py-2">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800">
          {strategies.map((s) => (
            <tr key={s.strategy_id} className="hover:bg-gray-900/40">
              <td className="px-3 py-2">
                <Link
                  href={`/vault/strategies/${encodeURIComponent(s.strategy_id)}`}
                  className="text-emerald-400 hover:underline"
                >
                  {s.name}
                </Link>
                <span className="block text-xs text-gray-600">{s.type}</span>
              </td>
              <td className="px-3 py-2 tabular-nums text-white">
                {s.equity_usd != null ? formatUSD(s.equity_usd) : "—"}
              </td>
              <td className="px-3 py-2 tabular-nums">
                {s.weight_pct != null ? `${s.weight_pct.toFixed(1)}%` : "—"}
              </td>
              <td className="px-3 py-2 tabular-nums text-gray-400">
                {s.target_weight_pct != null ? `${s.target_weight_pct}%` : "—"}
              </td>
              <td className="px-3 py-2 tabular-nums">
                {s.apr_since_inception != null ? formatPct(s.apr_since_inception, 2) : "—"}
              </td>
              <td className="px-3 py-2">
                <span
                  className={
                    s.status === "ACTIVE"
                      ? "text-emerald-400"
                      : s.status === "PAUSED"
                        ? "text-amber-400"
                        : "text-gray-500"
                  }
                >
                  {s.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
