import { formatUSD, formatPct, pnlColor } from "@/lib/format";
import type { PortfolioOverview } from "@/lib/types";

interface Props {
  data: PortfolioOverview;
}

export default function EquityCard({ data }: Props) {
  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">
        Total Equity
      </div>
      <div className="text-3xl font-bold text-white tabular-nums">
        {formatUSD(data.total_equity_usd)}
      </div>
      <div className="flex items-center gap-3 mt-2">
        <span className={`text-sm font-medium ${pnlColor(data.daily_change_usd)}`}>
          {formatUSD(data.daily_change_usd)} ({formatPct(data.daily_change_pct)})
        </span>
        <span className="text-xs text-gray-500">24h</span>
      </div>
      <div className="flex items-center gap-3 mt-1">
        <span className={`text-sm ${pnlColor(data.cashflow_adjusted_apr)}`}>
          {formatPct(data.cashflow_adjusted_apr, 1)} APR
        </span>
        <span className="text-xs text-gray-500">cashflow-adjusted</span>
      </div>
      <div className="mt-3 flex items-center gap-2">
        <span className="text-xs text-gray-500">
          {data.open_positions_count} open positions
        </span>
        <span className="text-xs text-gray-600">|</span>
        <span className={`text-xs ${pnlColor(data.total_unrealized_pnl)}`}>
          uPnL {formatUSD(data.total_unrealized_pnl)}
        </span>
      </div>
    </div>
  );
}
