import type { SubPair } from "./types";

export type SubPairBpsKey = "entry_spread_bps" | "exit_spread_bps" | "spread_pnl_bps";

function isFiniteNumber(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

/**
 * Mean of non-null, finite bps values. Returns null if there are no usable samples
 * (avoids NaN from 0/0 and misleading averages that treat null as 0).
 */
export function avgSubPairBps(
  pairs: SubPair[],
  key: SubPairBpsKey,
): number | null {
  let sum = 0;
  let n = 0;
  for (const sp of pairs) {
    const v = sp[key];
    if (isFiniteNumber(v)) {
      sum += v;
      n += 1;
    }
  }
  if (n === 0) return null;
  return sum / n;
}
