/**
 * Format a number as USD: $1,234.56
 * Negative values shown as -$1,234.56
 */
export function formatUSD(value: number | null | undefined, decimals = 2): string {
  if (value == null) return "\u2014";
  const abs = Math.abs(value);
  const formatted = abs.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return value < 0 ? `-$${formatted}` : `$${formatted}`;
}

/**
 * Format a percentage: +1.23% or -0.45%
 */
export function formatPct(value: number | null | undefined, decimals = 2): string {
  if (value == null) return "\u2014";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
}

/**
 * Format basis points: +15 bps or -3 bps
 */
export function formatBps(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  const sign = value > 0 ? "+" : "";
  return `${sign}${Math.round(value)} bps`;
}

/**
 * Format a number with commas: 1,234.56
 */
export function formatNumber(
  value: number | null | undefined,
  decimals = 2,
): string {
  if (value == null) return "\u2014";
  return value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/**
 * Format a price — auto-selects decimal places based on magnitude.
 * <1: 4 decimals, <100: 3 decimals, else: 2 decimals.
 */
export function formatPrice(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  const abs = Math.abs(value);
  let decimals = 2;
  if (abs < 1) decimals = 4;
  else if (abs < 100) decimals = 3;
  return `$${formatNumber(value, decimals)}`;
}

/**
 * Format epoch ms to a readable date string: 2026-03-29 10:00
 */
export function formatDate(epochMs: number | string | null | undefined): string {
  if (epochMs == null) return "\u2014";
  const d = typeof epochMs === "string" ? new Date(epochMs) : new Date(epochMs);
  if (isNaN(d.getTime())) return "\u2014";
  return d.toISOString().replace("T", " ").slice(0, 16);
}

/**
 * Format a relative time: "2h ago", "3d ago"
 */
export function formatRelative(isoString: string | null | undefined): string {
  if (!isoString) return "\u2014";
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return "\u2014";
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/**
 * Truncate an address: 0xabc...def
 */
export function truncateAddress(address: string, chars = 4): string {
  if (address.length <= chars * 2 + 3) return address;
  return `${address.slice(0, chars + 2)}...${address.slice(-chars)}`;
}

/**
 * Return the CSS class for a P&L value.
 */
export function pnlColor(value: number | null | undefined): string {
  if (value == null || value === 0) return "pnl-zero";
  return value > 0 ? "pnl-positive" : "pnl-negative";
}
