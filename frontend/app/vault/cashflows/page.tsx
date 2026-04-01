import Link from "next/link";
import { fetchVaultCashflows } from "@/lib/api";
import CashflowForm from "@/components/CashflowForm";

export const revalidate = 30;

export default async function VaultCashflowsPage() {
  let rows = null;
  let error: string | null = null;
  try {
    rows = await fetchVaultCashflows(100);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load";
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Vault cashflows</h1>
        <Link href="/vault" className="text-sm text-emerald-400">
          ← Vault overview
        </Link>
      </div>

      <CashflowForm />

      <section>
        <h2 className="text-sm font-medium text-gray-400 mb-3">History</h2>
        {error && <p className="text-red-400 text-sm">{error}</p>}
        {!error && rows && (
          <div className="overflow-x-auto rounded-lg border border-gray-800">
            <table className="w-full text-sm">
              <thead className="bg-gray-900/80 text-gray-400 text-xs uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">Time</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2 text-right">Amount</th>
                  <th className="px-3 py-2 text-left">Strategy / transfer</th>
                  <th className="px-3 py-2 text-left">Note</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {rows.map((r) => (
                  <tr key={r.cashflow_id}>
                    <td className="px-3 py-2 text-gray-400 whitespace-nowrap">
                      {new Date(r.ts).toLocaleString()}
                    </td>
                    <td className="px-3 py-2">{r.cf_type}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-white">
                      {r.amount.toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}{" "}
                      {r.currency}
                    </td>
                    <td className="px-3 py-2 text-gray-300 text-xs">
                      {r.cf_type === "TRANSFER"
                        ? `${r.from_strategy_id ?? "—"} → ${r.to_strategy_id ?? "—"}`
                        : (r.strategy_id ?? "—")}
                    </td>
                    <td className="px-3 py-2 text-gray-500 max-w-xs truncate">
                      {r.description ?? ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
