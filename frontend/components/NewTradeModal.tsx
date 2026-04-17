"use client";

import { useEffect, useState } from "react";
import {
  previewTrade,
  createTrade,
  finalizeTrade,
  type Trade,
  type TradeType,
} from "@/lib/trades";

interface Position {
  position_id: string;
  base?: string | null;
  status: string;
}

interface Props {
  onClose: () => void;
  onSaved: () => void;
  defaultPositionId?: string;
}

function toEpochMs(localStr: string): number {
  return new Date(localStr).getTime();
}

function fromEpochMs(ms: number): string {
  const d = new Date(ms);
  // convert to local-tz ISO slice for <input type="datetime-local">
  const off = d.getTimezoneOffset() * 60000;
  return new Date(ms - off).toISOString().slice(0, 16);
}

async function loadOpenPositions(): Promise<Position[]> {
  const res = await fetch("/api/harmonix/positions");
  if (!res.ok) return [];
  const data = await res.json();
  // Support both shapes: array of positions OR {items: [...]}
  const arr = Array.isArray(data) ? data : (data.items ?? []);
  return arr;
}

export default function NewTradeModal({ onClose, onSaved, defaultPositionId }: Props) {
  const [positions, setPositions] = useState<Position[]>([]);
  const [positionId, setPositionId] = useState(defaultPositionId || "");
  const [tradeType, setTradeType] = useState<TradeType>("OPEN");
  const [startStr, setStartStr] = useState(fromEpochMs(Date.now() - 3600 * 1000));
  const [endStr, setEndStr] = useState(fromEpochMs(Date.now()));
  const [note, setNote] = useState("");

  const [preview, setPreview] = useState<Trade | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    loadOpenPositions().then(setPositions).catch(() => setPositions([]));
  }, []);

  async function runPreview() {
    setError(null);
    setBusy(true);
    try {
      const p = await previewTrade({
        position_id: positionId,
        trade_type: tradeType,
        start_ts: toEpochMs(startStr),
        end_ts: toEpochMs(endStr),
        note: note || undefined,
      });
      setPreview(p);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setPreview(null);
    } finally {
      setBusy(false);
    }
  }

  async function save(doFinalize: boolean) {
    setError(null);
    setBusy(true);
    try {
      const t = await createTrade({
        position_id: positionId,
        trade_type: tradeType,
        start_ts: toEpochMs(startStr),
        end_ts: toEpochMs(endStr),
        note: note || undefined,
      });
      if (doFinalize) {
        await finalizeTrade(t.trade_id);
      }
      onSaved();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const sizeDelta =
    preview && preview.long_size != null && preview.short_size != null
      ? Math.abs(preview.long_size - preview.short_size)
      : 0;
  const avgSize =
    preview && preview.long_size != null && preview.short_size != null
      ? (preview.long_size + preview.short_size) / 2
      : 0;
  const sizeMismatchPct = avgSize > 0 ? (sizeDelta / avgSize) * 100 : 0;
  const showSizeWarning = sizeMismatchPct > 0.5;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-40">
      <div className="w-[600px] max-h-[90vh] overflow-auto rounded bg-white p-6 shadow-lg">
        <h2 className="mb-4 text-xl font-bold">New Trade</h2>

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium">Position</label>
            <select
              className="mt-1 w-full rounded border px-2 py-1"
              value={positionId}
              onChange={(e) => setPositionId(e.target.value)}
            >
              <option value="">— select —</option>
              {positions
                .filter((p) => p.status !== "CLOSED")
                .map((p) => (
                  <option key={p.position_id} value={p.position_id}>
                    {p.position_id} ({p.base || "?"})
                  </option>
                ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium">Type</label>
            <div className="mt-1 flex gap-3">
              <label>
                <input
                  type="radio"
                  checked={tradeType === "OPEN"}
                  onChange={() => setTradeType("OPEN")}
                />{" "}
                OPEN
              </label>
              <label>
                <input
                  type="radio"
                  checked={tradeType === "CLOSE"}
                  onChange={() => setTradeType("CLOSE")}
                />{" "}
                CLOSE
              </label>
            </div>
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-sm font-medium">Start (local)</label>
              <input
                type="datetime-local"
                className="mt-1 w-full rounded border px-2 py-1"
                value={startStr}
                onChange={(e) => setStartStr(e.target.value)}
              />
            </div>
            <div className="flex-1">
              <label className="block text-sm font-medium">End (local)</label>
              <input
                type="datetime-local"
                className="mt-1 w-full rounded border px-2 py-1"
                value={endStr}
                onChange={(e) => setEndStr(e.target.value)}
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium">Note (optional)</label>
            <textarea
              className="mt-1 w-full rounded border px-2 py-1"
              rows={2}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>

          <button
            onClick={runPreview}
            disabled={busy || !positionId}
            className="rounded bg-gray-600 px-3 py-1 text-white disabled:opacity-50"
          >
            Preview
          </button>

          {error && <p className="text-red-600">{error}</p>}

          {preview && (
            <div className="mt-3 rounded bg-gray-50 p-3 text-sm">
              <p>
                <b>Long leg ({preview.long_leg_id}):</b>{" "}
                {preview.long_fill_count ?? 0} fills, size=
                {preview.long_size?.toFixed(4) ?? "—"}, notional=$
                {preview.long_notional?.toFixed(2) ?? "—"}, avg_px=
                {preview.long_avg_px?.toFixed(4) ?? "—"}, fees=$
                {preview.long_fees?.toFixed(4) ?? "—"}
              </p>
              <p>
                <b>Short leg ({preview.short_leg_id}):</b>{" "}
                {preview.short_fill_count ?? 0} fills, size=
                {preview.short_size?.toFixed(4) ?? "—"}, notional=$
                {preview.short_notional?.toFixed(2) ?? "—"}, avg_px=
                {preview.short_avg_px?.toFixed(4) ?? "—"}, fees=$
                {preview.short_fees?.toFixed(4) ?? "—"}
              </p>
              {showSizeWarning && (
                <p className="text-yellow-700">
                  Size delta {sizeMismatchPct.toFixed(2)}% (not delta-neutral)
                </p>
              )}
              <p className="font-medium">
                {tradeType === "OPEN"
                  ? `Entry spread: ${preview.spread_bps?.toFixed(2) ?? "—"} bps`
                  : `Exit spread: ${preview.spread_bps?.toFixed(2) ?? "—"} bps; realized P&L: ${preview.realized_pnl_bps?.toFixed(2) ?? "—"} bps`}
              </p>
            </div>
          )}
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded border px-3 py-1">
            Cancel
          </button>
          <button
            onClick={() => save(false)}
            disabled={busy || !preview}
            className="rounded bg-gray-700 px-3 py-1 text-white disabled:opacity-50"
          >
            Save as DRAFT
          </button>
          <button
            onClick={() => save(true)}
            disabled={busy || !preview}
            className="rounded bg-blue-600 px-3 py-1 text-white disabled:opacity-50"
          >
            Finalize now
          </button>
        </div>
      </div>
    </div>
  );
}
