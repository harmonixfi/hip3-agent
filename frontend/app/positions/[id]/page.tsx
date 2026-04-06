import Link from "next/link";
import { getPositionDetail, getPositionFills } from "@/lib/api";
import { formatUSD, formatPct, formatDate, pnlColor } from "@/lib/format";
import LegDetail from "@/components/LegDetail";
import SpreadDisplay from "@/components/SpreadDisplay";
import CashflowTable from "@/components/CashflowTable";
import FillsTable from "@/components/FillsTable";

export const revalidate = 60;

interface Props {
  params: Promise<{ id: string }>;
}

export default async function PositionDetailPage({ params }: Props) {
  const { id } = await params;

  let position;
  let fills;
  let error: string | null = null;

  try {
    [position, fills] = await Promise.all([
      getPositionDetail(id),
      getPositionFills(id),
    ]);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to fetch position data";
  }

  if (error || !position || !fills) {
    return (
      <div className="space-y-6">
        <Link href="/" className="text-sm text-gray-400 hover:text-white">
          &larr; Back to Dashboard
        </Link>
        <div className="card border-red-900">
          <p className="text-red-400">Failed to load position</p>
          <p className="text-sm text-gray-500 mt-1">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <Link href="/" className="text-sm text-gray-400 hover:text-white">
        &larr; Back to Dashboard
      </Link>

      {/* Header card */}
      <div className="card">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">{position.base}</h1>
            <p className="text-sm text-gray-400 mt-1">
              {position.position_id} | {position.strategy}
            </p>
          </div>
          <div className="text-right">
            <span
              className={`text-sm px-2 py-1 rounded ${
                position.status === "OPEN"
                  ? "bg-green-900/30 text-green-400"
                  : position.status === "PAUSED"
                    ? "bg-yellow-900/30 text-yellow-400"
                    : position.status === "EXITING"
                      ? "bg-orange-900/30 text-orange-400"
                      : "bg-gray-800 text-gray-400"
              }`}
            >
              {position.status}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-4">
          <div>
            <div className="text-xs text-gray-500">Amount</div>
            <div className="text-lg font-semibold text-white tabular-nums">
              {formatUSD(position.amount_usd)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">uPnL</div>
            <div className={`text-lg font-semibold tabular-nums ${pnlColor(position.unrealized_pnl)}`}>
              {formatUSD(position.unrealized_pnl)}
              {position.unrealized_pnl_pct != null && (
                <span className="text-sm ml-1">
                  ({formatPct(position.unrealized_pnl_pct)})
                </span>
              )}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Funding</div>
            <div className={`text-lg font-semibold tabular-nums ${pnlColor(position.funding_earned)}`}>
              {formatUSD(position.funding_earned)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Carry APR</div>
            <div className={`text-lg font-semibold tabular-nums ${pnlColor(position.carry_apr)}`}>
              {position.carry_apr != null ? formatPct(position.carry_apr, 1) : "\u2014"}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Opened</div>
            <div className="text-sm text-gray-300">
              {formatDate(position.opened_at)}
            </div>
          </div>
        </div>

        {/* Daily funding mini bar chart */}
        {position.daily_funding_series && position.daily_funding_series.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-800">
            <div className="text-xs text-gray-500 mb-2">
              Daily Funding (last {position.daily_funding_series.length} days)
            </div>
            <FundingBarChart series={position.daily_funding_series} />
          </div>
        )}
      </div>

      {/* Legs */}
      <LegDetail legs={position.legs} />

      {/* Spreads */}
      <SpreadDisplay subPairs={position.sub_pairs} legs={position.legs} />

      {/* Cashflows */}
      <CashflowTable cashflows={position.cashflows} />

      {/* Fills */}
      <FillsTable fills={fills.fills} total={fills.total} />
    </div>
  );
}

// Simple bar chart using divs — no charting library needed
function FundingBarChart({
  series,
}: {
  series: { date: string; amount: number }[];
}) {
  const maxAbs = Math.max(...series.map((s) => Math.abs(s.amount)), 0.01);

  return (
    <div className="flex items-end gap-1 h-16">
      {series.map((s) => {
        const heightPct = Math.abs(s.amount / maxAbs) * 100;
        const isPositive = s.amount >= 0;

        return (
          <div
            key={s.date}
            className="flex-1 flex flex-col items-center justify-end h-full"
            title={`${s.date}: $${s.amount.toFixed(2)}`}
          >
            <div
              className={`w-full rounded-sm ${
                isPositive ? "bg-green-500/60" : "bg-red-500/60"
              }`}
              style={{ height: `${Math.max(heightPct, 2)}%` }}
            />
          </div>
        );
      })}
    </div>
  );
}
