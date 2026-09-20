import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Badge } from "@/components/ui/Badge";
import { useFundOverlap } from "../hooks/useFundOverlap";

export interface FundOverlapTabProps {
  currentPortfolioId: number;
  currentFundName: string;
}

export const FundOverlapTab: React.FC<FundOverlapTabProps> = ({ currentPortfolioId, currentFundName }) => {
  const [compareId, setCompareId] = useState<number | null>(null);

  const { data: screenerFunds } = useQuery({
    queryKey: ["screenerFundsList"],
    queryFn: () => api.getScreener({ limit: 50 }),
  });

  const targetFunds = (screenerFunds || []).filter((f) => f.portfolio_id !== currentPortfolioId);
  const selectedTargetId = compareId ?? (targetFunds.length > 0 ? targetFunds[0].portfolio_id : null);

  const { data: overlapData, isLoading } = useFundOverlap(currentPortfolioId, selectedTargetId);

  return (
    <div className="space-y-4">
      {/* Comparator Selector */}
      <Card className="p-4 bg-paper border-hairline rounded-3xl flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="text-sm font-semibold text-ink">Compare Overlap With:</div>
        <select
          value={selectedTargetId || ""}
          onChange={(e) => setCompareId(Number(e.target.value))}
          className="bg-sand/40 dark:bg-mid-gray/10 text-ink border border-hairline rounded-xl px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-primary"
          aria-label="Select fund to compare portfolio overlap"
        >
          {targetFunds.map((f) => (
            <option key={f.portfolio_id} value={f.portfolio_id} className="text-ink bg-paper">
              {f.fund_name} ({f.amc})
            </option>
          ))}
        </select>
      </Card>

      {/* Overlap Summary Card */}
      {isLoading && <Skeleton className="h-40 rounded-3xl" />}

      {!isLoading && overlapData && (
        <Card className="p-5 bg-paper border-hairline rounded-3xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-hairline pb-4">
            <div>
              <div className="text-xs text-mid-gray">Pairwise Portfolio Overlap</div>
              <div className="text-3xl font-extrabold text-ink mt-1">
                {overlapData.overlap_pct.toFixed(1)}%
              </div>
              <div className="text-xs text-mid-gray mt-1">
                {overlapData.portfolio_a_name} vs {overlapData.portfolio_b_name}
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="p-2 bg-sand/30 dark:bg-sand/10 rounded-xl">
                <div className="text-xs text-mid-gray">Common Stocks</div>
                <div className="text-lg font-bold text-ink">{overlapData.common_holdings_count}</div>
              </div>
              <div className="p-2 bg-sand/30 dark:bg-sand/10 rounded-xl">
                <div className="text-xs text-mid-gray">Unique to {overlapData.portfolio_a_name.slice(0, 8)}…</div>
                <div className="text-lg font-bold text-ink">{overlapData.unique_to_a_count}</div>
              </div>
              <div className="p-2 bg-sand/30 dark:bg-sand/10 rounded-xl">
                <div className="text-xs text-mid-gray">Unique to {overlapData.portfolio_b_name.slice(0, 8)}…</div>
                <div className="text-lg font-bold text-ink">{overlapData.unique_to_b_count}</div>
              </div>
            </div>
          </div>

          {/* Common Holdings Table */}
          <div className="overflow-x-auto">
            <div className="text-xs font-semibold text-mid-gray mb-2">Common Portfolio Holdings (Overlap Contribution)</div>
            <table className="w-full text-xs text-left" aria-label="Common portfolio holdings">
              <thead>
                <tr className="text-mid-gray border-b border-hairline pb-1">
                  <th className="pb-2 font-medium">Security</th>
                  <th className="pb-2 font-medium">Sector</th>
                  <th className="pb-2 font-medium text-right">{currentFundName.slice(0, 10)}…</th>
                  <th className="pb-2 font-medium text-right">{overlapData.portfolio_b_name.slice(0, 10)}…</th>
                  <th className="pb-2 font-medium text-right">Shared Min(A,B)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {overlapData.common_holdings.map((c) => (
                  <tr key={c.identifier} className="hover:bg-sand/30 dark:hover:bg-sand/10">
                    <td className="py-2 font-medium text-ink">{c.name}</td>
                    <td className="py-2 text-mid-gray">{c.sector || "—"}</td>
                    <td className="py-2 font-mono text-right text-mid-gray">{c.weight_a.toFixed(2)}%</td>
                    <td className="py-2 font-mono text-right text-mid-gray">{c.weight_b.toFixed(2)}%</td>
                    <td className="py-2 font-mono text-right font-bold text-ink">{c.overlap_weight.toFixed(2)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
};
