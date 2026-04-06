import { formatUSD, pnlColor } from "@/lib/format";
import type { PortfolioOverview } from "@/lib/types";

interface Props {
  data: PortfolioOverview;
}

export default function FundingSummary({ data }: Props) {
  const items = [
    { label: "Funding Today", value: data.funding_today_usd },
    { label: "Funding All-Time", value: data.funding_alltime_usd },
    { label: "Fees All-Time", value: data.fees_alltime_usd },
    { label: "Net P&L", value: data.net_pnl_alltime_usd },
  ];

  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
        Funding Summary
      </div>
      <div className="grid grid-cols-2 gap-4">
        {items.map((item) => (
          <div key={item.label}>
            <div className="text-xs text-gray-500">{item.label}</div>
            <div className={`text-lg font-semibold tabular-nums ${pnlColor(item.value)}`}>
              {formatUSD(item.value)}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 text-xs text-gray-600">
        Since {data.tracking_start_date}
      </div>
    </div>
  );
}
