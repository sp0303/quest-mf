import React from "react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { BacktestRun } from "@/lib/schema";

export interface BacktestRunsListProps {
  runs: BacktestRun[];
  selectedRunId?: number | null;
  onSelectRun: (runId: number) => void;
}

export const BacktestRunsList: React.FC<BacktestRunsListProps> = ({
  runs,
  selectedRunId,
  onSelectRun,
}) => {
  return (
    <Card className="p-4 border-hairline bg-paper rounded-3xl">
      <h3 className="text-sm font-semibold text-ink mb-3">Historical Simulation Runs</h3>
      <div className="space-y-2 max-h-60 overflow-y-auto">
        {runs.map((r) => {
          const isSelected = r.run_id === selectedRunId;
          return (
            <div
              key={r.run_id}
              onClick={() => onSelectRun(r.run_id)}
              className={`p-3 rounded-2xl cursor-pointer transition-colors border ${
                isSelected
                  ? "border-ink bg-canvas font-medium"
                  : "border-hairline hover:bg-surface-alt"
              }`}
            >
              <div className="flex items-center justify-between text-xs">
                <span className="font-mono text-ink font-semibold">Run #{r.run_id}</span>
                <Badge variant={r.status === "DONE" ? "solid" : "soft"}>
                  {r.status}
                </Badge>
              </div>
              <div className="mt-1 flex items-center justify-between text-xs text-mid-gray">
                <span>
                  Top {r.summary?.top_k || 3} • {r.summary?.rebalance_months || 3}M Rebal
                </span>
                <span className="text-ink font-medium">
                  {r.summary?.cagr_net ? `Net ${(r.summary.cagr_net * 100).toFixed(1)}%` : "—"}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
};
