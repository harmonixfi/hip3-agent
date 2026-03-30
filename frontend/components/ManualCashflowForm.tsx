"use client";

import { useState, useTransition } from "react";
import { submitManualCashflow, type ActionResult } from "@/app/settings/actions";

export default function ManualCashflowForm() {
  const [isPending, startTransition] = useTransition();
  const [result, setResult] = useState<ActionResult | null>(null);

  function handleSubmit(formData: FormData) {
    startTransition(async () => {
      const res = await submitManualCashflow(formData);
      setResult(res);
    });
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

      <form action={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Account ID */}
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

          {/* Venue */}
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

          {/* Type */}
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

          {/* Amount */}
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

          {/* Currency */}
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

          {/* Description */}
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
          disabled={isPending}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded transition-colors"
        >
          {isPending ? "Submitting..." : "Submit"}
        </button>
      </form>
    </div>
  );
}
