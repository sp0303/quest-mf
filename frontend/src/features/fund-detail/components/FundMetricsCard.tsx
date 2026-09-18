import React from "react";
import { Card } from "@/components/ui/Card";
import { NumberCell } from "@/components/ui/NumberCell";
import type { FundRiskMetrics, FundSummary } from "@/lib/schema";

export interface FundMetricsCardProps {
  summary: FundSummary;
  risk?: FundRiskMetrics;
}

export const FundMetricsCard: React.FC<FundMetricsCardProps> = ({ summary, risk }) => {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <Card className="p-4 bg-paper border-hairline rounded-3xl">
        <div className="text-xs text-mid-gray">1M Return</div>
        <div className="text-lg font-semibold mt-1">
          <NumberCell value={summary.ret_1m} isPercent />
        </div>
      </Card>
      <Card className="p-4 bg-paper border-hairline rounded-3xl">
        <div className="text-xs text-mid-gray">3M Return</div>
        <div className="text-lg font-semibold mt-1">
          <NumberCell value={summary.ret_3m} isPercent />
        </div>
      </Card>
      <Card className="p-4 bg-paper border-hairline rounded-3xl">
        <div className="text-xs text-mid-gray">1Y Return</div>
        <div className="text-lg font-semibold mt-1">
          <NumberCell value={summary.ret_1y} isPercent />
        </div>
      </Card>
      <Card className="p-4 bg-paper border-hairline rounded-3xl">
        <div className="text-xs text-mid-gray">3Y CAGR</div>
        <div className="text-lg font-semibold mt-1">
          <NumberCell value={summary.cagr_3y} isPercent />
        </div>
      </Card>

      {/* Risk Metrics */}
      <Card className="p-4 bg-paper border-hairline rounded-3xl">
        <div className="text-xs text-mid-gray">Annualized Volatility</div>
        <div className="text-lg font-semibold mt-1 text-ink">
          {risk?.volatility_ann ? `${risk.volatility_ann.toFixed(2)}%` : "—"}
        </div>
      </Card>
      <Card className="p-4 bg-paper border-hairline rounded-3xl">
        <div className="text-xs text-mid-gray">Sharpe Ratio (Rf=6.5%)</div>
        <div className="text-lg font-semibold mt-1 text-ink">
          {risk?.sharpe_ratio !== undefined ? risk.sharpe_ratio.toFixed(2) : "—"}
        </div>
      </Card>
      <Card className="p-4 bg-paper border-hairline rounded-3xl">
        <div className="text-xs text-mid-gray">Sortino Ratio</div>
        <div className="text-lg font-semibold mt-1 text-ink">
          {risk?.sortino_ratio !== undefined ? risk.sortino_ratio.toFixed(2) : "—"}
        </div>
      </Card>
      <Card className="p-4 bg-paper border-hairline rounded-3xl">
        <div className="text-xs text-mid-gray">Max Drawdown</div>
        <div className="text-lg font-semibold mt-1">
          <NumberCell value={risk?.max_drawdown !== undefined && risk?.max_drawdown !== null ? risk.max_drawdown / 100 : null} isPercent />
        </div>
      </Card>

    </div>
  );
};
