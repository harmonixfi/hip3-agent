"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { Candidate, CandidatesResponse } from "@/lib/types";

function fmt(val: number | null, decimals = 1): string {
  if (val === null || val === undefined) return "—";
  return val.toFixed(decimals) + "%";
}

function TradeabilityBadge({ status }: { status: string }) {
  const isExecutable = status === "EXECUTABLE";
  return (
    <span
      className={`inline-block text-xs px-1.5 py-0.5 rounded font-medium ${
        isExecutable
          ? "bg-green-900/50 text-green-400"
          : "bg-gray-700 text-gray-400"
      }`}
    >
      {isExecutable ? "EXE" : "NON"}
    </span>
  );
}

function CandidateTable({ rows }: { rows: Candidate[] }) {
  if (rows.length === 0) {
    return <p className="text-gray-500 text-sm py-4">No candidates meet the filter criteria.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-400 border-b border-gray-800">
            <th className="pb-2 pr-3 font-medium w-8">#</th>
            <th className="pb-2 pr-3 font-medium">Symbol</th>
            <th className="pb-2 pr-3 font-medium">Venue</th>
            <th className="pb-2 pr-3 font-medium text-right">APR14</th>
            <th className="pb-2 pr-3 font-medium text-right">APR7</th>
            <th className="pb-2 pr-3 font-medium text-right">APR1d</th>
            <th className="pb-2 pr-3 font-medium text-right">APR3d</th>
            <th className="pb-2 pr-3 font-medium text-right">Stability</th>
            <th className="pb-2 font-medium">Flags</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/50">
          {rows.map((c) => (
            <tr key={`${c.symbol}-${c.rank}`} className="hover:bg-gray-800/30">
              <td className="py-2 pr-3 text-gray-500">{c.rank}</td>
              <td className="py-2 pr-3">
                <div className="flex items-center gap-2">
                  <span className="text-white font-medium">{c.symbol}</span>
                  <TradeabilityBadge status={c.tradeability_status} />
                </div>
              </td>
              <td className="py-2 pr-3 text-gray-400">{c.venue}</td>
              <td className="py-2 pr-3 text-right text-emerald-400">{fmt(c.apr_14d)}</td>
              <td className="py-2 pr-3 text-right text-emerald-400">{fmt(c.apr_7d)}</td>
              <td className="py-2 pr-3 text-right text-gray-300">{fmt(c.apr_1d)}</td>
              <td className="py-2 pr-3 text-right text-gray-300">{fmt(c.apr_3d)}</td>
              <td className="py-2 pr-3 text-right text-blue-400">{fmt(c.stability_score)}</td>
              <td className="py-2 text-xs text-gray-500 max-w-[200px] truncate">{c.flags || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type Tab = "general" | "equities";

interface Props {
  data: CandidatesResponse;
}

export default function CandidatesClient({ data }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("general");
  const [isPending, startTransition] = useTransition();
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const router = useRouter();

  function handleRefresh() {
    setRefreshError(null);
    startTransition(async () => {
      try {
        const res = await fetch("/api/candidates/refresh", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          setRefreshError(body.detail ?? "Refresh failed");
          return;
        }
        router.refresh();
      } catch {
        setRefreshError("Network error — could not reach API");
      }
    });
  }

  const rows = activeTab === "general" ? data.general : data.equities;

  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1">
          {(["general", "equities"] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                activeTab === tab
                  ? "bg-gray-700 text-white"
                  : "text-gray-400 hover:text-white hover:bg-gray-800/50"
              }`}
            >
              {tab === "general" ? "General" : "Equities"}
              <span className="ml-1.5 text-xs text-gray-500">
                ({tab === "general" ? data.general.length : data.equities.length})
              </span>
            </button>
          ))}
        </div>

        <button
          onClick={handleRefresh}
          disabled={isPending}
          className="flex items-center gap-2 px-3 py-1.5 rounded-md text-sm bg-gray-800 text-gray-300 hover:text-white hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isPending ? (
            <>
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Refreshing…
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Refresh
            </>
          )}
        </button>
      </div>

      {refreshError && (
        <p className="text-sm text-red-400">{refreshError}</p>
      )}

      <CandidateTable rows={rows} />
    </div>
  );
}
