import { formatUSD, formatPrice, formatNumber, pnlColor } from "@/lib/format";
import type { Leg } from "@/lib/types";

interface Props {
  legs: Leg[];
}

export default function LegDetail({ legs }: Props) {
  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
        Legs
      </div>
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Venue</th>
              <th>Instrument</th>
              <th>Side</th>
              <th className="text-right">Size</th>
              <th className="text-right">Avg Entry</th>
              <th className="text-right">Current</th>
              <th className="text-right">uPnL</th>
            </tr>
          </thead>
          <tbody>
            {legs.map((leg) => (
              <tr key={leg.leg_id}>
                <td className="text-gray-400">{leg.venue}</td>
                <td className="font-mono text-white">{leg.inst_id}</td>
                <td>
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded ${
                      leg.side === "LONG"
                        ? "bg-green-900/30 text-green-400"
                        : "bg-red-900/30 text-red-400"
                    }`}
                  >
                    {leg.side}
                  </span>
                </td>
                <td className="text-right tabular-nums">
                  {formatNumber(leg.size, 4)}
                </td>
                <td className="text-right tabular-nums">
                  {formatPrice(leg.avg_entry_price)}
                </td>
                <td className="text-right tabular-nums">
                  {formatPrice(leg.current_price)}
                </td>
                <td className={`text-right tabular-nums ${pnlColor(leg.unrealized_pnl)}`}>
                  {formatUSD(leg.unrealized_pnl)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
