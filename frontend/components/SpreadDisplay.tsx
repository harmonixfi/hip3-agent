import { formatBps, pnlColor } from "@/lib/format";
import type { SubPair, Leg } from "@/lib/types";

interface Props {
  subPairs: SubPair[];
  legs: Leg[];
}

export default function SpreadDisplay({ subPairs, legs }: Props) {
  if (subPairs.length === 0) {
    return null;
  }

  function getLegLabel(legId: string): string {
    const leg = legs.find((l) => l.leg_id === legId);
    return leg ? `${leg.venue} ${leg.inst_id}` : legId;
  }

  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
        Sub-Pair Spreads
      </div>
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Long Leg</th>
              <th>Short Leg</th>
              <th className="text-right">Entry Spread</th>
              <th className="text-right">Exit Spread</th>
              <th className="text-right">Spread P&L</th>
              <th className="text-right">Direction</th>
            </tr>
          </thead>
          <tbody>
            {subPairs.map((sp, i) => {
              const pnl = sp.spread_pnl_bps;
              const direction =
                pnl == null
                  ? { label: "\u2014", className: "text-gray-500" }
                  : pnl > 0
                    ? { label: "Favorable", className: "text-green-400" }
                    : pnl < 0
                      ? { label: "Unfavorable", className: "text-red-400" }
                      : { label: "Flat", className: "text-gray-400" };
              return (
                <tr key={i}>
                  <td className="text-gray-400 text-xs">
                    {getLegLabel(sp.long_leg_id)}
                  </td>
                  <td className="text-gray-400 text-xs">
                    {getLegLabel(sp.short_leg_id)}
                  </td>
                  <td className="text-right tabular-nums">
                    {formatBps(sp.entry_spread_bps)}
                  </td>
                  <td className="text-right tabular-nums">
                    {formatBps(sp.exit_spread_bps)}
                  </td>
                  <td className={`text-right tabular-nums font-medium ${pnlColor(sp.spread_pnl_bps)}`}>
                    {formatBps(sp.spread_pnl_bps)}
                  </td>
                  <td className="text-right">
                    <span className={`text-xs ${direction.className}`}>
                      {direction.label}
                    </span>
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
