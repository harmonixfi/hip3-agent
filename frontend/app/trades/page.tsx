"use client";

import { useEffect, useState } from "react";
import TradesTable from "@/components/TradesTable";
import NewTradeModal from "@/components/NewTradeModal";
import { listTrades, type Trade, type TradeType, type TradeState } from "@/lib/trades";

export default function TradesPage() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [positionFilter, setPositionFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState<TradeType | "">("");
  const [stateFilter, setStateFilter] = useState<TradeState | "">("");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await listTrades({
        position_id: positionFilter || undefined,
        trade_type: typeFilter || undefined,
        state: stateFilter || undefined,
      });
      setTrades(res.items);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [positionFilter, typeFilter, stateFilter]);

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Trades</h1>
        <button
          onClick={() => setShowModal(true)}
          className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
        >
          + New Trade
        </button>
      </div>
      <div className="mb-4 flex gap-3">
        <input
          className="rounded border px-2 py-1"
          placeholder="Filter by position_id"
          value={positionFilter}
          onChange={(e) => setPositionFilter(e.target.value)}
        />
        <select
          className="rounded border px-2 py-1"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as TradeType | "")}
        >
          <option value="">All Types</option>
          <option value="OPEN">OPEN</option>
          <option value="CLOSE">CLOSE</option>
        </select>
        <select
          className="rounded border px-2 py-1"
          value={stateFilter}
          onChange={(e) => setStateFilter(e.target.value as TradeState | "")}
        >
          <option value="">All States</option>
          <option value="DRAFT">DRAFT</option>
          <option value="FINALIZED">FINALIZED</option>
        </select>
      </div>
      {error && <p className="mb-3 text-red-600">Error: {error}</p>}
      {loading ? <p>Loading...</p> : <TradesTable trades={trades} />}
      {showModal && (
        <NewTradeModal
          onClose={() => setShowModal(false)}
          onSaved={() => {
            setShowModal(false);
            load();
          }}
        />
      )}
    </div>
  );
}
