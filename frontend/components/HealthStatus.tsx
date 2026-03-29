import { formatRelative } from "@/lib/format";
import type { HealthStatus as HealthStatusType } from "@/lib/types";

interface Props {
  data: HealthStatusType;
}

export default function HealthStatus({ data }: Props) {
  const isHealthy = data.status === "ok";

  const items = [
    { label: "Fills", value: formatRelative(data.last_fill_ingestion) },
    { label: "Prices", value: formatRelative(data.last_price_pull) },
    { label: "Positions", value: formatRelative(data.last_position_pull) },
    { label: "Felix JWT", value: formatRelative(data.felix_jwt_expires_at) },
    { label: "DB", value: `${data.db_size_mb.toFixed(1)} MB` },
  ];

  return (
    <div className="flex items-center gap-4 px-4 py-2 bg-gray-900 border border-gray-800 rounded-lg text-xs">
      <div className="flex items-center gap-1.5">
        <div
          className={`w-2 h-2 rounded-full ${
            isHealthy ? "bg-green-400" : "bg-red-400"
          }`}
        />
        <span className="text-gray-400 font-medium uppercase">System</span>
      </div>
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1">
          <span className="text-gray-500">{item.label}:</span>
          <span className="text-gray-300">{item.value}</span>
        </div>
      ))}
    </div>
  );
}
