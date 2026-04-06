"use client";

import { useState } from "react";
import { postManualCashflow } from "@/lib/api";
import type { ManualCashflowRequest } from "@/lib/types";

interface Props {
  onSuccess?: () => void;
}

export default function ManualCashflowForm({ onSuccess }: Props) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    success: boolean;
    message: string;
    cashflow_id?: number;
  } | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setResult(null);

    const form = e.currentTarget;
    const account_id = (form.elements.namedItem("account_id") as HTMLInputElement)
      .value;
    const venue = (form.elements.namedItem("venue") as HTMLSelectElement).value;
    const cf_type = (form.elements.namedItem("cf_type") as HTMLSelectElement)
      .value as "DEPOSIT" | "WITHDRAW";
    const amount = parseFloat(
      (form.elements.namedItem("amount") as HTMLInputElement).value,
    );
    const currency =
      (form.elements.namedItem("currency") as HTMLInputElement).value || "USDC";
    const descRaw = (form.elements.namedItem("description") as HTMLInputElement)
      .value;
    const description = descRaw?.trim() || undefined;

    if (!account_id || !venue || !cf_type || !Number.isFinite(amount) || amount <= 0) {
      setResult({
        success: false,
        message: "All fields are required and amount must be positive.",
      });
      return;
    }

    if (cf_type !== "DEPOSIT" && cf_type !== "WITHDRAW") {
      setResult({
        success: false,
        message: "Type must be DEPOSIT or WITHDRAW.",
      });
      return;
    }

    const payload: ManualCashflowRequest = {
      account_id,
      venue,
      cf_type,
      amount,
      currency,
      description,
    };

    setLoading(true);
    try {
      const res = await postManualCashflow(payload);
      setResult({
        success: true,
        message: `${cf_type} of $${amount.toFixed(2)} recorded successfully.`,
        cashflow_id: res.cashflow_id,
      });
      onSuccess?.();
      form.reset();
      const cur = form.elements.namedItem("currency") as HTMLInputElement;
      if (cur) cur.value = "USDC";
    } catch (err) {
      setResult({
        success: false,
        message: err instanceof Error ? err.message : "Failed to submit cashflow.",
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-4">
        Manual Deposit / Withdraw
      </div>

      {result && (
        <div
          className={`mb-4 p-3 rounded text-sm ${
            result.success
              ? "bg-green-900/20 text-green-400 border border-green-800"
              : "bg-red-900/20 text-red-400 border border-red-800"
          }`}
        >
          {result.message}
          {result.cashflow_id && (
            <span className="ml-2 text-xs text-gray-500">
              ID: {result.cashflow_id}
            </span>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Account Address
            </label>
            <input
              name="account_id"
              type="text"
              required
              placeholder="0x..."
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Venue</label>
            <select
              name="venue"
              required
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
            >
              <option value="hyperliquid">Hyperliquid</option>
              <option value="felix">Felix</option>
            </select>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Type</label>
            <select
              name="cf_type"
              required
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
            >
              <option value="DEPOSIT">Deposit</option>
              <option value="WITHDRAW">Withdraw</option>
            </select>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Amount (positive)
            </label>
            <input
              name="amount"
              type="number"
              step="0.01"
              min="0.01"
              required
              placeholder="1000.00"
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Currency
            </label>
            <input
              name="currency"
              type="text"
              defaultValue="USDC"
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Description (optional)
            </label>
            <input
              name="description"
              type="text"
              placeholder="Deposit from Arbitrum bridge"
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded transition-colors"
        >
          {loading ? "Submitting..." : "Submit"}
        </button>
      </form>
    </div>
  );
}
