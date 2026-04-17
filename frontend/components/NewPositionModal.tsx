"use client";

import { useState } from "react";

interface Props {
  onClose: () => void;
  onSaved: () => void;
}

type StrategyType = "SPOT_PERP" | "PERP_PERP";

export default function NewPositionModal({ onClose, onSaved }: Props) {
  const [positionId, setPositionId] = useState("");
  const [base, setBase] = useState("");
  const [strategyType, setStrategyType] = useState<StrategyType>("SPOT_PERP");
  const [venue, setVenue] = useState("hyperliquid");
  const [longInst, setLongInst] = useState("");
  const [longWallet, setLongWallet] = useState("main");
  const [shortInst, setShortInst] = useState("");
  const [shortWallet, setShortWallet] = useState("main");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save() {
    setError(null);
    setBusy(true);
    try {
      const body = {
        position_id: positionId,
        base,
        strategy_type: strategyType,
        venue,
        long_leg: {
          leg_id: `${positionId}_SPOT`,
          venue,
          inst_id: longInst,
          side: "LONG",
          wallet_label: longWallet,
        },
        short_leg: {
          leg_id: `${positionId}_PERP`,
          venue,
          inst_id: shortInst,
          side: "SHORT",
          wallet_label: shortWallet,
        },
      };
      const res = await fetch("/api/harmonix/positions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const msg = await res.text().catch(() => "");
        throw new Error(`Create failed (${res.status}): ${msg}`);
      }
      onSaved();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-40">
      <div className="w-[500px] max-h-[90vh] overflow-auto rounded bg-white p-6 shadow-lg text-black">
        <h2 className="mb-4 text-xl font-bold">New Position</h2>
        <div className="space-y-3 text-sm">
          <label className="block">
            <span className="font-medium">Position ID</span>
            <input
              className="mt-1 w-full rounded border px-2 py-1"
              value={positionId}
              onChange={(e) => setPositionId(e.target.value)}
              placeholder="pos_xyz_GOOGL"
            />
          </label>
          <label className="block">
            <span className="font-medium">Base</span>
            <input
              className="mt-1 w-full rounded border px-2 py-1"
              value={base}
              onChange={(e) => setBase(e.target.value)}
              placeholder="GOOGL"
            />
          </label>
          <label className="block">
            <span className="font-medium">Strategy</span>
            <select
              className="mt-1 w-full rounded border px-2 py-1"
              value={strategyType}
              onChange={(e) => setStrategyType(e.target.value as StrategyType)}
            >
              <option value="SPOT_PERP">SPOT_PERP</option>
              <option value="PERP_PERP">PERP_PERP</option>
            </select>
          </label>
          <label className="block">
            <span className="font-medium">Venue</span>
            <input
              className="mt-1 w-full rounded border px-2 py-1"
              value={venue}
              onChange={(e) => setVenue(e.target.value)}
            />
          </label>
          <div className="rounded border p-2">
            <p className="font-medium">Long leg</p>
            <label className="block">
              <span>inst_id</span>
              <input
                className="mt-1 w-full rounded border px-2 py-1"
                value={longInst}
                onChange={(e) => setLongInst(e.target.value)}
              />
            </label>
            <label className="block">
              <span>wallet</span>
              <input
                className="mt-1 w-full rounded border px-2 py-1"
                value={longWallet}
                onChange={(e) => setLongWallet(e.target.value)}
              />
            </label>
          </div>
          <div className="rounded border p-2">
            <p className="font-medium">Short leg</p>
            <label className="block">
              <span>inst_id</span>
              <input
                className="mt-1 w-full rounded border px-2 py-1"
                value={shortInst}
                onChange={(e) => setShortInst(e.target.value)}
              />
            </label>
            <label className="block">
              <span>wallet</span>
              <input
                className="mt-1 w-full rounded border px-2 py-1"
                value={shortWallet}
                onChange={(e) => setShortWallet(e.target.value)}
              />
            </label>
          </div>
          {error && <p className="text-red-600">{error}</p>}
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded border px-3 py-1">
            Cancel
          </button>
          <button
            onClick={save}
            disabled={busy || !positionId || !base || !longInst || !shortInst}
            className="rounded bg-blue-600 px-3 py-1 text-white disabled:opacity-50"
          >
            Create
          </button>
        </div>
      </div>
    </div>
  );
}
