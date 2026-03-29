import { getHealth } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import ManualCashflowForm from "@/components/ManualCashflowForm";

export const revalidate = 60;

export default async function SettingsPage() {
  let health;
  let error: string | null = null;

  try {
    health = await getHealth();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to fetch health data";
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      {/* Manual cashflow form */}
      <ManualCashflowForm />

      {/* System info */}
      <div className="card">
        <div className="text-xs text-gray-500 uppercase tracking-wide mb-4">
          System Information
        </div>

        {error || !health ? (
          <p className="text-red-400 text-sm">
            Failed to load system info. {error}
          </p>
        ) : (
          <div className="space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <div className="text-xs text-gray-500">Status</div>
                <div className="flex items-center gap-2">
                  <div
                    className={`w-2 h-2 rounded-full ${
                      health.status === "ok" ? "bg-green-400" : "bg-red-400"
                    }`}
                  />
                  <span className="text-sm text-white">{health.status}</span>
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Open Positions</div>
                <div className="text-sm text-white">{health.open_positions}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">DB Size</div>
                <div className="text-sm text-white">
                  {health.db_size_mb.toFixed(1)} MB
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Uptime</div>
                <div className="text-sm text-white">
                  {Math.floor(health.uptime_seconds / 3600)}h{" "}
                  {Math.floor((health.uptime_seconds % 3600) / 60)}m
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Last Fill Ingestion</div>
                <div className="text-sm text-white">
                  {formatRelative(health.last_fill_ingestion)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Last Price Pull</div>
                <div className="text-sm text-white">
                  {formatRelative(health.last_price_pull)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Last Position Pull</div>
                <div className="text-sm text-white">
                  {formatRelative(health.last_position_pull)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Felix JWT Expiry</div>
                <div className="text-sm text-white">
                  {formatRelative(health.felix_jwt_expires_at)}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Tracking config (display only for now) */}
      <div className="card">
        <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
          Configuration
        </div>
        <div className="text-sm text-gray-400">
          <p>
            Tracking start date and other configuration will be managed via the
            API in a future update.
          </p>
        </div>
      </div>
    </div>
  );
}
