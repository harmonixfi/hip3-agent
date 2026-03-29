import { formatUSD, formatPrice, formatNumber, formatDate } from "@/lib/format";
import type { Fill } from "@/lib/types";

interface Props {
  fills: Fill[];
  total: number;
}

export default function FillsTable({ fills, total }: Props) {
  if (fills.length === 0) {
    return (
      <div className="card">
        <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
          Fills
        </div>
        <p className="text-sm text-gray-500">No fills recorded.</p>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs text-gray-500 uppercase tracking-wide">
          Fills ({total})
        </div>
      </div>
      <div className="overflow-x-auto max-h-96 overflow-y-auto">
        <table className="data-table">
          <thead className="sticky top-0 bg-gray-900">
            <tr>
              <th>Time</th>
              <th>Instrument</th>
              <th>Side</th>
              <th>Direction</th>
              <th className="text-right">Price</th>
              <th className="text-right">Size</th>
              <th className="text-right">Notional</th>
              <th className="text-right">Fee</th>
            </tr>
          </thead>
          <tbody>
            {fills.map((fill) => (
              <tr key={fill.fill_id}>
                <td className="text-gray-400 text-xs tabular-nums">
                  {formatDate(fill.ts)}
                </td>
                <td className="font-mono text-white text-xs">{fill.inst_id}</td>
                <td>
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded ${
                      fill.side === "BUY"
                        ? "bg-green-900/30 text-green-400"
                        : "bg-red-900/30 text-red-400"
                    }`}
                  >
                    {fill.side}
                  </span>
                </td>
                <td className="text-gray-400 text-xs">{fill.dir ?? "\u2014"}</td>
                <td className="text-right tabular-nums">
                  {formatPrice(fill.px)}
                </td>
                <td className="text-right tabular-nums">
                  {formatNumber(fill.sz, 4)}
                </td>
                <td className="text-right tabular-nums">
                  {formatUSD(fill.px * fill.sz)}
                </td>
                <td className="text-right tabular-nums text-yellow-400">
                  {fill.fee != null ? formatUSD(fill.fee) : "\u2014"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
