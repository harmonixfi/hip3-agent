"use server";

import { postManualCashflow } from "@/lib/api";
import type { ManualCashflowRequest } from "@/lib/types";

export interface ActionResult {
  success: boolean;
  message: string;
  cashflow_id?: number;
}

export async function submitManualCashflow(
  formData: FormData,
): Promise<ActionResult> {
  const account_id = formData.get("account_id") as string;
  const venue = formData.get("venue") as string;
  const cf_type = formData.get("cf_type") as "DEPOSIT" | "WITHDRAW";
  const amount = parseFloat(formData.get("amount") as string);
  const currency = formData.get("currency") as string;
  const description = formData.get("description") as string;

  // Validation
  if (!account_id || !venue || !cf_type || isNaN(amount) || amount <= 0) {
    return {
      success: false,
      message: "All fields are required and amount must be positive.",
    };
  }

  if (cf_type !== "DEPOSIT" && cf_type !== "WITHDRAW") {
    return {
      success: false,
      message: "Type must be DEPOSIT or WITHDRAW.",
    };
  }

  const payload: ManualCashflowRequest = {
    account_id,
    venue,
    cf_type,
    amount,
    currency: currency || "USDC",
    description: description || undefined,
  };

  try {
    const result = await postManualCashflow(payload);
    return {
      success: true,
      message: `${cf_type} of $${amount.toFixed(2)} recorded successfully.`,
      cashflow_id: result.cashflow_id,
    };
  } catch (e) {
    return {
      success: false,
      message: e instanceof Error ? e.message : "Failed to submit cashflow.",
    };
  }
}
