"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createVaultCashflow } from "@/lib/api";

export default function CashflowForm() {
  const router = useRouter();
  const [cfType, setCfType] = useState("DEPOSIT");
  const [amount, setAmount] = useState("");
  const [strategyId, setStrategyId] = useState("");
  const [fromId, setFromId] = useState("");
  const [toId, setToId] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus(null);
    const n = parseFloat(amount);
    if (!Number.isFinite(n) || n <= 0) {
      setStatus("Enter a positive amount.");
      return;
    }
    setLoading(true);
    try {
      const body: Parameters<typeof createVaultCashflow>[0] = {
        cf_type: cfType,
        amount: n,
        description: description || undefined,
      };
      if (cfType === "TRANSFER") {
        body.from_strategy_id = fromId || undefined;
        body.to_strategy_id = toId || undefined;
      } else {
        body.strategy_id = strategyId || undefined;
      }
      const res = await createVaultCashflow(body);
      setStatus(res.message);
      setAmount("");
      setDescription("");
      router.refresh();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="card space-y-4 max-w-lg">
      <h2 className="text-lg font-semibold text-white">Record cashflow</h2>
      <div>
        <label className="block text-xs text-gray-500 mb-1">Type</label>
        <select
          value={cfType}
          onChange={(e) => setCfType(e.target.value)}
          className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-white"
        >
          <option value="DEPOSIT">DEPOSIT</option>
          <option value="WITHDRAW">WITHDRAW</option>
          <option value="TRANSFER">TRANSFER</option>
        </select>
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-1">Amount (USDC)</label>
        <input
          type="text"
          inputMode="decimal"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-white"
          placeholder="5000"
        />
      </div>
      {cfType === "TRANSFER" ? (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">From strategy id</label>
            <input
              value={fromId}
              onChange={(e) => setFromId(e.target.value)}
              className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-white"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">To strategy id</label>
            <input
              value={toId}
              onChange={(e) => setToId(e.target.value)}
              className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-white"
            />
          </div>
        </div>
      ) : (
        <div>
          <label className="block text-xs text-gray-500 mb-1">Strategy id</label>
          <input
            value={strategyId}
            onChange={(e) => setStrategyId(e.target.value)}
            className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-white"
            placeholder="lending"
          />
        </div>
      )}
      <div>
        <label className="block text-xs text-gray-500 mb-1">Description</label>
        <input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-white"
        />
      </div>
      <button
        type="submit"
        disabled={loading}
        className="px-4 py-2 rounded bg-emerald-700 hover:bg-emerald-600 text-white text-sm disabled:opacity-50"
      >
        {loading ? "Submitting…" : "Submit"}
      </button>
      {status && <p className="text-sm text-gray-400">{status}</p>}
    </form>
  );
}
