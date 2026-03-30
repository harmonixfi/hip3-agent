import { formatUSD, formatDate, pnlColor } from "@/lib/format";
import type { Cashflow } from "@/lib/types";

interface Props {
  cashflows: Cashflow[];
}

export default function CashflowTable({ cashflows }: Props) {
  if (cashflows.length === 0) {
    return (
      <div className="card">
        <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
          Cashflows
        </div>
        <p className="text-sm text-gray-500">No cashflow events recorded.</p>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
        Cashflows ({cashflows.length})
      </div>
      <div className="overflow-x-auto max-h-96 overflow-y-auto">
        <table className="data-table">
          <thead className="sticky top-0 bg-gray-900">
            <tr>
              <th>Time</th>
              <th>Type</th>
              <th className="text-right">Amount</th>
              <th>Currency</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {cashflows.map((cf) => (
              <tr key={cf.cashflow_id}>
                <td className="text-gray-400 text-xs tabular-nums">
                  {formatDate(cf.ts)}
                </td>
                <td>
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded ${
                      cf.cf_type.includes("FUND")
                        ? "bg-blue-900/30 text-blue-400"
                        : cf.cf_type.includes("FEE")
                          ? "bg-yellow-900/30 text-yellow-400"
                          : cf.cf_type.includes("DEPOSIT")
                            ? "bg-green-900/30 text-green-400"
                            : cf.cf_type.includes("WITHDRAW")
                              ? "bg-red-900/30 text-red-400"
                              : "bg-gray-800 text-gray-400"
                    }`}
                  >
                    {cf.cf_type}
                  </span>
                </td>
                <td className={`text-right tabular-nums ${pnlColor(cf.amount)}`}>
                  {formatUSD(cf.amount)}
                </td>
                <td className="text-gray-400">{cf.currency}</td>
                <td className="text-gray-500 text-xs max-w-[200px] truncate">
                  {cf.description ?? "\u2014"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
