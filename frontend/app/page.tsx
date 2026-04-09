import { getPortfolioOverview, getOpenPositions, getHealth } from "@/lib/api";
import EquityCard from "@/components/EquityCard";
import WalletBreakdown from "@/components/WalletBreakdown";
import FundingSummary from "@/components/FundingSummary";
import FundUtilizationCard from "@/components/FundUtilizationCard";
import PositionsTable from "@/components/PositionsTable";
import HealthStatus from "@/components/HealthStatus";

export const revalidate = 60; // ISR: revalidate every 60 seconds

export default async function DashboardPage() {
  let portfolioData;
  let positions;
  let health;
  let error: string | null = null;

  try {
    [portfolioData, positions, health] = await Promise.all([
      getPortfolioOverview(),
      getOpenPositions(),
      getHealth(),
    ]);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to fetch data";
  }

  if (error || !portfolioData || !positions || !health) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <div className="card border-red-900">
          <p className="text-red-400">Failed to load dashboard data</p>
          <p className="text-sm text-gray-500 mt-1">{error}</p>
          <p className="text-xs text-gray-600 mt-2">
            Check that the backend is running and API_BASE_URL is configured.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <span className="text-xs text-gray-500">
          Last updated: {new Date(portfolioData.as_of).toLocaleString()}
        </span>
      </div>

      {/* System status bar */}
      <HealthStatus data={health} />

      {/* Top row: Equity + Wallets + Funding + Utilization */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <EquityCard data={portfolioData} />
        <WalletBreakdown data={portfolioData} />
        <FundingSummary data={portfolioData} />
        <FundUtilizationCard data={portfolioData.fund_utilization} />
      </div>

      {/* Open Positions */}
      <PositionsTable positions={positions} />
    </div>
  );
}
