"use client";

import { useCallback, useEffect, useState } from "react";
import TradesTable from "@/components/TradesTable";
import NewTradeModal from "@/components/NewTradeModal";
import { listTrades, type Trade } from "@/lib/trades";

interface Props {
  positionId: string;
}

export default function PositionTradesPanel({ positionId }: Props) {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listTrades({ position_id: positionId });
      setTrades(res.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [positionId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <section className="card">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Trades</h2>
        <button
          onClick={() => setShowModal(true)}
          className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700"
        >
          + New Trade
        </button>
      </div>
      {error && <p className="text-red-500">{error}</p>}
      {loading ? (
        <p className="text-gray-400">Loading&hellip;</p>
      ) : (
        <TradesTable trades={trades} showPosition={false} />
      )}
      {showModal && (
        <NewTradeModal
          defaultPositionId={positionId}
          onClose={() => setShowModal(false)}
          onSaved={() => {
            setShowModal(false);
            load();
          }}
        />
      )}
    </section>
  );
}
