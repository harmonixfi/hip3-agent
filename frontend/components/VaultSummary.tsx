import Link from "next/link";
import { formatUSD, formatPct } from "@/lib/format";
import type { VaultOverview } from "@/lib/types";

interface Props {
  data: VaultOverview;
}

export default function VaultSummary({ data }: Props) {
  return (
    <div className="card border-emerald-900/50">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">
            Vault — {data.vault_name}
          </div>
          <div className="text-3xl font-bold text-white tabular-nums">
            {formatUSD(data.total_equity_usd)}
          </div>
          <div className="flex flex-wrap gap-4 mt-2 text-sm">
            <span className="text-gray-400">
              Total APR{" "}
              <span className="text-emerald-400 font-medium">
                {data.total_apr != null ? formatPct(data.total_apr, 2) : "—"}
              </span>
            </span>
            <span className="text-gray-400">
              30d{" "}
              <span className="text-gray-200">
                {data.apr_30d != null ? formatPct(data.apr_30d, 2) : "—"}
              </span>
            </span>
            <span className="text-gray-400">
              7d{" "}
              <span className="text-gray-200">
                {data.apr_7d != null ? formatPct(data.apr_7d, 2) : "—"}
              </span>
            </span>
          </div>
        </div>
        <Link
          href="/vault"
          className="text-sm text-emerald-400 hover:text-emerald-300 whitespace-nowrap"
        >
          Vault detail →
        </Link>
      </div>
      {data.as_of && (
        <p className="text-xs text-gray-600 mt-3">
          As of {new Date(data.as_of).toLocaleString()}
        </p>
      )}
    </div>
  );
}
