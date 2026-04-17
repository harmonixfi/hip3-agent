"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getTrade,
  finalizeTrade,
  reopenTrade,
  recomputeTrade,
  deleteTrade,
  type TradeDetail,
} from "@/lib/trades";
import { formatBps } from "@/lib/format";

export default function TradeDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;
  const [trade, setTrade] = useState<TradeDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setError(null);
    try {
      setTrade(await getTrade(id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    load();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function onFinalize() {
    setBusy(true);
    try {
      await finalizeTrade(id);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onReopen() {
    setBusy(true);
    try {
      await reopenTrade(id);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onRecompute() {
    setBusy(true);
    try {
      await recomputeTrade(id);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    if (!confirm("Delete this trade? Linked fills return to unassigned pool.")) return;
    setBusy(true);
    try {
      await deleteTrade(id);
      router.push("/trades");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function downloadCsv() {
    if (!trade) return;
    const header = "fill_id,leg_side,inst_id,side,px,sz,fee,ts\n";
    const rows = trade.fills.map(
      (f) => `${f.fill_id},${f.leg_side},${f.inst_id},${f.side},${f.px},${f.sz},${f.fee ?? ""},${f.ts}`,
    );
    const blob = new Blob([header + rows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${trade.trade_id}_fills.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (error) return <div className="p-6 text-red-600">Error: {error}</div>;
  if (!trade) return <div className="p-6">Loading...</div>;

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">{trade.trade_id}</h1>
        <div className="flex gap-2">
          {trade.state === "DRAFT" && (
            <>
              <button onClick={onRecompute} disabled={busy} className="rounded border px-3 py-1">
                Recompute
              </button>
              <button onClick={onFinalize} disabled={busy} className="rounded bg-blue-600 px-3 py-1 text-white">
                Finalize
              </button>
              <button onClick={onDelete} disabled={busy} className="rounded bg-red-600 px-3 py-1 text-white">
                Delete
              </button>
            </>
          )}
          {trade.state === "FINALIZED" && (
            <>
              <button onClick={onReopen} disabled={busy} className="rounded border px-3 py-1">
                Reopen to edit
              </button>
              <button onClick={onDelete} disabled={busy} className="rounded bg-red-600 px-3 py-1 text-white">
                Delete
              </button>
            </>
          )}
          <button onClick={downloadCsv} className="rounded border px-3 py-1">
            Download CSV
          </button>
        </div>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-6 rounded border p-4 text-sm">
        <div>
          <p><b>Position:</b> {trade.position_id}</p>
          <p><b>Type:</b> {trade.trade_type}</p>
          <p>
            <b>State:</b> {trade.state}
            {trade.unassigned_fills_count ? ` ${trade.unassigned_fills_count} late fills` : ""}
          </p>
          <p>
            <b>Window:</b> {new Date(trade.start_ts).toISOString()} {"->"}{" "}
            {new Date(trade.end_ts).toISOString()}
          </p>
          {trade.note && <p><b>Note:</b> {trade.note}</p>}
        </div>
        <div>
          <p><b>Spread:</b> {trade.spread_bps != null ? formatBps(trade.spread_bps) : "—"}</p>
          <p>
            <b>Realized P&amp;L:</b>{" "}
            {trade.realized_pnl_bps != null ? formatBps(trade.realized_pnl_bps) : "—"}
          </p>
          <p><b>Fees:</b> ${((trade.long_fees ?? 0) + (trade.short_fees ?? 0)).toFixed(2)}</p>
        </div>
      </div>

      <h2 className="mb-2 text-lg font-semibold">Linked Fills ({trade.fills.length})</h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 text-left">
            <th className="p-2">Fill</th>
            <th className="p-2">Leg</th>
            <th className="p-2">Instrument</th>
            <th className="p-2">Side</th>
            <th className="p-2">Px</th>
            <th className="p-2">Sz</th>
            <th className="p-2">Fee</th>
            <th className="p-2">Timestamp</th>
          </tr>
        </thead>
        <tbody>
          {trade.fills.map((f) => (
            <tr key={f.fill_id} className="border-t">
              <td className="p-2">{f.fill_id}</td>
              <td className="p-2">{f.leg_side}</td>
              <td className="p-2">{f.inst_id}</td>
              <td className="p-2">{f.side}</td>
              <td className="p-2">{f.px}</td>
              <td className="p-2">{f.sz}</td>
              <td className="p-2">{f.fee ?? "—"}</td>
              <td className="p-2">{new Date(f.ts).toISOString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
