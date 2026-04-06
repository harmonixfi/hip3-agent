import { formatUSD, truncateAddress } from "@/lib/format";
import type { PortfolioOverview } from "@/lib/types";

interface Props {
  data: PortfolioOverview;
}

export default function WalletBreakdown({ data }: Props) {
  const accounts = Object.entries(data.equity_by_account);

  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
        Wallet Breakdown
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Label</th>
            <th>Address</th>
            <th>Venue</th>
            <th className="text-right">Equity</th>
          </tr>
        </thead>
        <tbody>
          {accounts.map(([label, acct]) => (
            <tr key={label}>
              <td className="font-medium text-white">{label}</td>
              <td className="font-mono text-gray-400 text-xs">
                {truncateAddress(acct.address)}
              </td>
              <td className="text-gray-400">{acct.venue}</td>
              <td className="text-right text-white tabular-nums">
                {formatUSD(acct.equity_usd)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
