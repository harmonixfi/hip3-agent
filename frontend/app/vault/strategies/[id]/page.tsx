import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiError, fetchVaultStrategyDetail } from "@/lib/api";
import { formatUSD, formatPct } from "@/lib/format";

export const dynamic = "force-dynamic";

interface Props {
  params: { id: string };
}

export default async function VaultStrategyDetailPage({ params }: Props) {
  const id = decodeURIComponent(params.id);

  let detail = null;
  try {
    detail = await fetchVaultStrategyDetail(id);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      notFound();
    }
    throw e;
  }

  if (!detail) {
    notFound();
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">{detail.name}</h1>
          <p className="text-sm text-gray-500 mt-1">
            {detail.strategy_id} · {detail.type}
          </p>
        </div>
        <Link href="/vault" className="text-sm text-emerald-400">
          ← Vault
        </Link>
      </div>

      <div className="card grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        <div>
          <div className="text-gray-500 text-xs uppercase">Equity</div>
          <div className="text-lg font-semibold text-white tabular-nums">
            {detail.equity_usd != null ? formatUSD(detail.equity_usd) : "—"}
          </div>
        </div>
        <div>
          <div className="text-gray-500 text-xs uppercase">APR (inception)</div>
          <div className="text-lg text-emerald-400 tabular-nums">
            {detail.apr_since_inception != null
              ? formatPct(detail.apr_since_inception, 2)
              : "—"}
          </div>
        </div>
        <div>
          <div className="text-gray-500 text-xs uppercase">30d / 7d APR</div>
          <div className="text-gray-200 tabular-nums">
            {detail.apr_30d != null ? formatPct(detail.apr_30d, 2) : "—"} /{" "}
            {detail.apr_7d != null ? formatPct(detail.apr_7d, 2) : "—"}
          </div>
        </div>
        <div>
          <div className="text-gray-500 text-xs uppercase">Target weight</div>
          <div className="text-gray-200">
            {detail.target_weight_pct != null ? `${detail.target_weight_pct}%` : "—"}
          </div>
        </div>
      </div>

      {detail.wallets && detail.wallets.length > 0 && (
        <div className="card">
          <h2 className="text-sm font-medium text-gray-400 mb-2">Wallets</h2>
          <ul className="text-sm text-gray-300 space-y-1">
            {detail.wallets.map((w) => (
              <li key={`${w.wallet_label}-${w.venue}`}>
                {w.wallet_label} @ {w.venue}
              </li>
            ))}
          </ul>
        </div>
      )}

      {detail.equity_breakdown && Object.keys(detail.equity_breakdown).length > 0 && (
        <div className="card">
          <h2 className="text-sm font-medium text-gray-400 mb-2">Breakdown</h2>
          <pre className="text-xs text-gray-400 overflow-x-auto">
            {JSON.stringify(detail.equity_breakdown, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
