import type { StrategySummary } from "@/lib/types";

interface Props {
  strategies: StrategySummary[];
}

const COLORS = [
  "bg-emerald-500",
  "bg-sky-500",
  "bg-amber-500",
  "bg-violet-500",
  "bg-rose-500",
];

export default function AllocationBar({ strategies }: Props) {
  const withWeight = strategies.filter(
    (s) => s.weight_pct != null && s.weight_pct > 0,
  );
  if (!withWeight.length) {
    return null;
  }

  return (
    <div className="space-y-2">
      <div className="text-xs text-gray-500 uppercase tracking-wide">Allocation</div>
      <div className="flex h-3 rounded overflow-hidden bg-gray-800">
        {withWeight.map((s, i) => (
          <div
            key={s.strategy_id}
            className={`${COLORS[i % COLORS.length]} transition-all`}
            style={{ width: `${Math.min(100, s.weight_pct ?? 0)}%` }}
            title={`${s.name}: ${(s.weight_pct ?? 0).toFixed(1)}%`}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {withWeight.map((s, i) => (
          <span key={s.strategy_id} className="flex items-center gap-1.5 text-gray-400">
            <span className={`w-2 h-2 rounded-sm ${COLORS[i % COLORS.length]}`} />
            {s.name}{" "}
            <span className="text-gray-300">{(s.weight_pct ?? 0).toFixed(1)}%</span>
          </span>
        ))}
      </div>
    </div>
  );
}
