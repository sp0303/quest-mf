import React from "react";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Badge } from "@/components/ui/Badge";
import type { PortfolioHoldingsResponse } from "@/lib/schema";

export interface FundHoldingsTabProps {
  holdingsData: PortfolioHoldingsResponse | null;
  isLoading?: boolean;
}

export const FundHoldingsTab: React.FC<FundHoldingsTabProps> = ({ holdingsData, isLoading }) => {
  if (isLoading) {
    return <Skeleton className="h-64 rounded-3xl" />;
  }

  if (!holdingsData || holdingsData.holdings.length === 0) {
    return (
      <Card className="p-8 text-center text-mid-gray bg-paper border-hairline rounded-3xl">
        No monthly portfolio disclosure available for this fund yet.
      </Card>
    );
  }

  const { large_cap_pct, mid_cap_pct, small_cap_pct, cash_pct } = holdingsData;

  return (
    <div className="space-y-4">
      {/* Point-in-time disclosure notice */}
      <div className="flex flex-wrap items-center justify-between text-xs text-mid-gray px-1">
        <span>
          As of <strong className="text-ink">{holdingsData.as_of_date}</strong> (Disclosed: {holdingsData.disclosed_date || "Monthly AMC Feed"})
        </span>
        <span>Stock Count: <strong className="text-ink">{holdingsData.stock_count}</strong> | Top 10: <strong className="text-ink">{holdingsData.top_10_concentration_pct.toFixed(1)}%</strong></span>
      </div>

      {/* Market Cap Split Bar */}
      <Card className="p-4 bg-paper border-hairline rounded-3xl space-y-2">
        <div className="text-xs font-medium text-mid-gray">Market Cap Allocation (AMFI Classification)</div>
        <div className="h-4 w-full rounded-full overflow-hidden flex bg-sand dark:bg-mid-gray/20">
          <div style={{ width: `${large_cap_pct}%` }} className="bg-ink h-full" title={`Large Cap: ${large_cap_pct}%`} />
          <div style={{ width: `${mid_cap_pct}%` }} className="bg-primary h-full" title={`Mid Cap: ${mid_cap_pct}%`} />
          <div style={{ width: `${small_cap_pct}%` }} className="bg-accent h-full" title={`Small Cap: ${small_cap_pct}%`} />
          <div style={{ width: `${cash_pct}%` }} className="bg-mid-gray/40 h-full" title={`Cash: ${cash_pct}%`} />
        </div>
        <div className="flex justify-between text-xs text-ink pt-1 flex-wrap gap-2">
          <span>● Large: {large_cap_pct.toFixed(1)}%</span>
          <span>● Mid: {mid_cap_pct.toFixed(1)}%</span>
          <span>● Small: {small_cap_pct.toFixed(1)}%</span>
          <span>● Cash: {cash_pct.toFixed(1)}%</span>
        </div>
      </Card>

      {/* Top 10 Holdings Table */}
      <Card className="p-4 bg-paper border-hairline rounded-3xl overflow-x-auto">
        <div className="text-sm font-semibold text-ink mb-3">Top Holdings</div>
        <table className="w-full text-xs text-left" aria-label="Top fund holdings">
          <thead>
            <tr className="text-mid-gray border-b border-hairline pb-2">
              <th className="pb-2 font-medium">Security</th>
              <th className="pb-2 font-medium">Sector</th>
              <th className="pb-2 font-medium">Cap Class</th>
              <th className="pb-2 font-medium text-right">% Assets</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-hairline">
            {holdingsData.top_10_holdings.map((h, i) => (
              <tr key={h.isin || `${h.security_name}-${i}`} className="hover:bg-sand/30 dark:hover:bg-sand/10">
                <td className="py-2.5 font-medium text-ink">{h.security_name}</td>
                <td className="py-2.5 text-mid-gray">{h.sector || "—"}</td>
                <td className="py-2.5">
                  <Badge variant="soft">{h.cap_class || "EQUITY"}</Badge>
                </td>
                <td className="py-2.5 font-mono text-right text-ink font-semibold">{h.pct_nav.toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
};
