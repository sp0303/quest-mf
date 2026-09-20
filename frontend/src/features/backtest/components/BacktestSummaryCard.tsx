import React from "react";
import { Card } from "@/components/ui/Card";
import { NumberCell } from "@/components/ui/NumberCell";
import type { BacktestRunSummary } from "@/lib/schema";

export interface BacktestSummaryCardProps {
  summary?: BacktestRunSummary;
}

export const BacktestSummaryCard: React.FC<BacktestSummaryCardProps> = ({ summary }) => {
  if (!summary) return null;

  const s: BacktestRunSummary | undefined =
    typeof summary === "string"
      ? (() => {
          try {
            return JSON.parse(summary);
          } catch {
            return undefined;
          }
        })()
      : summary;

  if (!s) return null;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
      <Card className="p-4 bg-paper border-hairline rounded-3xl">
        <div className="text-xs text-mid-gray">CAGR (Gross)</div>
        <div className="text-lg font-semibold mt-1">
          <NumberCell value={s.cagr_gross} isPercent />
        </div>
      </Card>
      <Card className="p-4 bg-paper border-hairline rounded-3xl">
        <div className="text-xs text-mid-gray">CAGR (Net of Friction)</div>
        <div className="text-lg font-semibold mt-1">
          <NumberCell value={s.cagr_net} isPercent />
        </div>
      </Card>
      <Card className="p-4 bg-paper border-hairline rounded-3xl">
        <div className="text-xs text-mid-gray">Sharpe Ratio</div>
        <div className="text-lg font-semibold mt-1 text-ink">
          {s.sharpe_ratio == null ? "—" : s.sharpe_ratio.toFixed(2)}
        </div>
      </Card>
      <Card className="p-4 bg-paper border-hairline rounded-3xl">
        <div className="text-xs text-mid-gray">Max Drawdown</div>
        <div className="text-lg font-semibold mt-1">
          <NumberCell value={s.max_drawdown} isPercent />
        </div>
      </Card>

      <Card className="p-4 bg-paper border-hairline rounded-3xl">
        <div className="text-xs text-mid-gray">Mean Rank IC</div>
        <div className="text-lg font-semibold mt-1 text-ink">
          {s.rank_ic_mean == null ? "—" : s.rank_ic_mean.toFixed(3)}
        </div>
      </Card>
    </div>
  );
};
