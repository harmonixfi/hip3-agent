import { formatUSD } from "@/lib/format";
import type { FundUtilization } from "@/lib/types";

interface Props {
  data: FundUtilization | null;
}

function leverageColor(leverage: number): string {
  if (leverage < 1) return "text-green-400";
  if (leverage <= 2) return "text-gray-200";
  if (leverage <= 3) return "text-yellow-400";
  return "text-red-400";
}

export default function FundUtilizationCard({ data }: Props) {
  if (!data) {
    return (
      <div className="card">
        <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
          Fund Utilization
        </div>
        <div className="text-gray-600">No data</div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
        Fund Utilization
      </div>

      {/* Summary metrics */}
      <div className="space-y-2 mb-4">
        <div className="flex justify-between items-baseline">
          <span className="text-xs text-gray-500">Leverage</span>
          <span className={`text-lg font-bold tabular-nums ${leverageColor(data.leverage)}`}>
            {data.leverage.toFixed(2)}x
          </span>
        </div>
        <div className="flex justify-between items-baseline">
          <span className="text-xs text-gray-500">Deployed</span>
          <span className="text-sm text-gray-200 tabular-nums">
            {formatUSD(data.total_deployed_usd)}{" "}
            <span className="text-gray-500">{data.deployed_pct.toFixed(0)}%</span>
          </span>
        </div>
        <div className="flex justify-between items-baseline">
          <span className="text-xs text-gray-500">Available</span>
          <span className="text-sm text-gray-200 tabular-nums">
            {formatUSD(data.total_available_usd)}
          </span>
        </div>
      </div>

      {/* Per-account breakdown */}
      {data.accounts.length > 0 && (
        <div className="border-t border-gray-800 pt-3">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500">
                <th className="text-left font-normal pb-1">Account</th>
                <th className="text-right font-normal pb-1">Equity</th>
                <th className="text-right font-normal pb-1">Leverage</th>
              </tr>
            </thead>
            <tbody>
              {data.accounts.map((acct) => (
                <tr key={acct.label} className="text-gray-300">
                  <td className="py-0.5">{acct.label}</td>
                  <td className="text-right tabular-nums">{formatUSD(acct.equity_usd)}</td>
                  <td className={`text-right tabular-nums ${leverageColor(acct.leverage)}`}>
                    {acct.leverage.toFixed(2)}x
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
