import Link from "next/link";
import {
  fetchVaultOverview,
  fetchVaultSnapshots,
} from "@/lib/api";
import VaultSummary from "@/components/VaultSummary";
import StrategyTable from "@/components/StrategyTable";
import AllocationBar from "@/components/AllocationBar";
import { formatUSD, formatPct } from "@/lib/format";

export const revalidate = 60;

export default async function VaultPage() {
  let overview = null;
  let snapshots = null;
  let error: string | null = null;

  try {
    [overview, snapshots] = await Promise.all([
      fetchVaultOverview(),
      fetchVaultSnapshots(60),
    ]);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load vault";
  }

  if (error || !overview) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-white">Vault</h1>
        <div className="card border-red-900">
          <p className="text-red-400">{error ?? "No data"}</p>
        </div>
        <Link href="/" className="text-emerald-400 text-sm">
          ← Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-white">Vault</h1>

      <VaultSummary data={overview} />
      <AllocationBar strategies={overview.strategies} />
      <StrategyTable strategies={overview.strategies} />

      <section>
        <h2 className="text-sm font-medium text-gray-400 mb-3">Recent vault snapshots</h2>
        <div className="overflow-x-auto rounded-lg border border-gray-800">
          <table className="w-full text-sm">
            <thead className="bg-gray-900/80 text-gray-400 text-xs uppercase">
              <tr>
                <th className="px-3 py-2 text-left">Date</th>
                <th className="px-3 py-2 text-right">NAV</th>
                <th className="px-3 py-2 text-right">APR</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {(snapshots ?? []).slice(0, 14).map((s) => (
                <tr key={s.ts}>
                  <td className="px-3 py-2 text-gray-300">
                    {new Date(s.ts).toLocaleDateString()}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-white">
                    {formatUSD(s.total_equity_usd)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {s.total_apr != null ? formatPct(s.total_apr, 2) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
