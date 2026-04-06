"use client";

import { useEffect, useState } from "react";
import { fetchVaultOverview, postManualCashflow } from "@/lib/api";
import type { ManualCashflowRequest, StrategySummary } from "@/lib/types";

interface Props {
  onSuccess?: () => void;
}

type FlowKind = "DEPOSIT" | "WITHDRAW" | "TRANSFER";

export default function ManualCashflowForm({ onSuccess }: Props) {
  const [loading, setLoading] = useState(false);
  const [strategies, setStrategies] = useState<StrategySummary[]>([]);
  const [strategiesError, setStrategiesError] = useState<string | null>(null);
  const [flowKind, setFlowKind] = useState<FlowKind>("DEPOSIT");
  const [result, setResult] = useState<{
    success: boolean;
    message: string;
    vault_cashflow_id?: number;
    pm_cashflow_ids?: number[];
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchVaultOverview()
      .then((ov) => {
        if (!cancelled) {
          const active = (ov.strategies ?? []).filter((s) => s.status === "ACTIVE");
          setStrategies(active);
          setStrategiesError(null);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setStrategies([]);
          setStrategiesError(
            e instanceof Error ? e.message : "Could not load strategies",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setResult(null);

    const form = e.currentTarget;
    const accountRaw = (
      form.elements.namedItem("account_id") as HTMLInputElement
    ).value?.trim();
    const account_id = accountRaw ? accountRaw : undefined;
    const amount = parseFloat(
      (form.elements.namedItem("amount") as HTMLInputElement).value,
    );
    const currency =
      (form.elements.namedItem("currency") as HTMLInputElement).value || "USDC";
    const descRaw = (form.elements.namedItem("description") as HTMLInputElement)
      .value;
    const description = descRaw?.trim() || undefined;

    if (!Number.isFinite(amount) || amount <= 0) {
      setResult({
        success: false,
        message: "A positive amount is required.",
      });
      return;
    }

    let payload: ManualCashflowRequest;

    if (flowKind === "TRANSFER") {
      const from_strategy_id = (
        form.elements.namedItem("from_strategy_id") as HTMLSelectElement
      ).value;
      const to_strategy_id = (
        form.elements.namedItem("to_strategy_id") as HTMLSelectElement
      ).value;
      if (!from_strategy_id || !to_strategy_id) {
        setResult({
          success: false,
          message: "Select both From strategy and To strategy.",
        });
        return;
      }
      if (from_strategy_id === to_strategy_id) {
        setResult({
          success: false,
          message: "From and To strategy must be different (internal transfer only).",
        });
        return;
      }
      payload = {
        from_strategy_id,
        to_strategy_id,
        cf_type: "TRANSFER",
        amount,
        currency,
        description,
        ...(account_id ? { account_id } : {}),
      };
    } else {
      const strategy_id = (form.elements.namedItem("strategy_id") as HTMLSelectElement)
        .value;
      if (!strategy_id) {
        setResult({
          success: false,
          message: "Strategy and a positive amount are required.",
        });
        return;
      }
      payload = {
        strategy_id,
        cf_type: flowKind,
        amount,
        currency,
        description,
        ...(account_id ? { account_id } : {}),
      };
    }

    setLoading(true);
    try {
      const res = await postManualCashflow(payload);
      setResult({
        success: true,
        message: `${flowKind} of $${amount.toFixed(2)} recorded successfully.`,
        vault_cashflow_id: res.vault_cashflow_id,
        pm_cashflow_ids: res.pm_cashflow_ids,
      });
      onSuccess?.();
      form.reset();
      const cur = form.elements.namedItem("currency") as HTMLInputElement;
      if (cur) cur.value = "USDC";
      setFlowKind("DEPOSIT");
      const strat = form.elements.namedItem("strategy_id") as HTMLSelectElement;
      if (strat && strategies.length > 0) strat.value = strategies[0].strategy_id;
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
        Manual Deposit / Withdraw / Internal transfer
      </div>

      {strategiesError && (
        <p className="text-amber-400 text-sm mb-3">{strategiesError}</p>
      )}

      {result && (
        <div
          className={`mb-4 p-3 rounded text-sm ${
            result.success
              ? "bg-green-900/20 text-green-400 border border-green-800"
              : "bg-red-900/20 text-red-400 border border-red-800"
          }`}
        >
          {result.message}
          {result.pm_cashflow_ids != null && result.pm_cashflow_ids.length > 0 && (
            <span className="ml-2 text-xs text-gray-500">
              PM {result.pm_cashflow_ids.map((id) => `#${id}`).join(", ")}
              {result.vault_cashflow_id != null && (
                <> · Vault #{result.vault_cashflow_id}</>
              )}
            </span>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Account address (optional)
            </label>
            <input
              name="account_id"
              type="text"
              placeholder="0x... — for reference only"
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Flow type</label>
            <select
              name="flow_kind"
              value={flowKind}
              onChange={(e) => setFlowKind(e.target.value as FlowKind)}
              disabled={strategies.length === 0}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none disabled:opacity-50"
            >
              <option value="DEPOSIT">Deposit (external)</option>
              <option value="WITHDRAW">Withdraw (external)</option>
              <option value="TRANSFER">Transfer between strategies</option>
            </select>
          </div>

          {flowKind === "TRANSFER" ? (
            <>
              <div>
                <label className="block text-xs text-gray-400 mb-1">
                  From strategy
                </label>
                <select
                  name="from_strategy_id"
                  required
                  disabled={strategies.length < 2}
                  className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none disabled:opacity-50"
                >
                  {strategies.length < 2 ? (
                    <option value="">Need at least two active strategies</option>
                  ) : (
                    strategies.map((s) => (
                      <option key={s.strategy_id} value={s.strategy_id}>
                        {s.name} ({s.type})
                      </option>
                    ))
                  )}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">
                  To strategy
                </label>
                <select
                  name="to_strategy_id"
                  required
                  disabled={strategies.length < 2}
                  className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none disabled:opacity-50"
                >
                  {strategies.length < 2 ? (
                    <option value="">Need at least two active strategies</option>
                  ) : (
                    strategies.map((s) => (
                      <option key={`to-${s.strategy_id}`} value={s.strategy_id}>
                        {s.name} ({s.type})
                      </option>
                    ))
                  )}
                </select>
              </div>
            </>
          ) : (
            <div>
              <label className="block text-xs text-gray-400 mb-1">Strategy</label>
              <select
                name="strategy_id"
                required
                disabled={strategies.length === 0}
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none disabled:opacity-50"
              >
                {strategies.length === 0 ? (
                  <option value="">No active strategies</option>
                ) : (
                  strategies.map((s) => (
                    <option key={s.strategy_id} value={s.strategy_id}>
                      {s.name} ({s.type})
                    </option>
                  ))
                )}
              </select>
            </div>
          )}

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

          <div className="md:col-span-2">
            <label className="block text-xs text-gray-400 mb-1">
              Description (optional)
            </label>
            <input
              name="description"
              type="text"
              placeholder={
                flowKind === "TRANSFER"
                  ? "Reallocate equity label"
                  : "Deposit from Arbitrum bridge"
              }
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
            />
          </div>
        </div>

        <p className="text-xs text-gray-500">
          {flowKind === "TRANSFER"
            ? "Transfers only re-label equity between strategies (no on-chain move). External deposits/withdrawals use Deposit or Withdraw."
            : "External capital in or out of the portfolio. Use Transfer for moves between strategies only."}
        </p>

        <button
          type="submit"
          disabled={
            loading ||
            strategies.length === 0 ||
            (flowKind === "TRANSFER" && strategies.length < 2)
          }
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded transition-colors"
        >
          {loading ? "Submitting..." : "Submit"}
        </button>
      </form>
    </div>
  );
}
