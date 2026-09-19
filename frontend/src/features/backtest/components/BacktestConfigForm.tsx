import React, { useState } from "react";
import { Play } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

export interface BacktestConfigFormProps {
  onRun: (params: { topK: number; rebalanceMonths: number }) => void;
  isRunning?: boolean;
}

export const BacktestConfigForm: React.FC<BacktestConfigFormProps> = ({
  onRun,
  isRunning = false,
}) => {
  const [topK, setTopK] = useState(3);
  const [rebalanceMonths, setRebalanceMonths] = useState(3);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onRun({ topK, rebalanceMonths });
  };

  return (
    <Card className="p-5 border-hairline bg-paper rounded-3xl">
      <h2 className="text-sm font-semibold text-ink">Walk-Forward Simulation Parameters</h2>
      <p className="text-xs text-mid-gray mt-0.5">
        Execution at NAV(t + 1) with friction: 0.005% stamp duty, 0.1% STT, exit load, and CGT
      </p>

      <form onSubmit={handleSubmit} className="mt-4 flex flex-wrap items-center gap-4">
        <div>
          <label htmlFor="top-k-select" className="block text-xs font-medium text-mid-gray mb-1">Top K Funds</label>
          <select
            id="top-k-select"
            value={topK}
            onChange={(e) => setTopK(parseInt(e.target.value, 10))}
            className="h-9 px-3 rounded-2xl border border-hairline bg-surface-alt text-ink text-xs focus:outline-none focus:border-ink"
            aria-label="Select Top K Funds to include"
          >
            {[1, 2, 3, 5, 10].map((k) => (
              <option key={k} value={k}>
                Top {k} Funds
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="rebalance-cadence" className="block text-xs font-medium text-mid-gray mb-1">Rebalance Cadence</label>
          <select
            id="rebalance-cadence"
            value={rebalanceMonths}
            onChange={(e) => setRebalanceMonths(parseInt(e.target.value, 10))}
            className="h-9 px-3 rounded-2xl border border-hairline bg-surface-alt text-ink text-xs focus:outline-none focus:border-ink"
            aria-label="Select Rebalance Cadence"
          >
            <option value={1}>Monthly (1M)</option>
            <option value={3}>Quarterly (3M)</option>
            <option value={6}>Semi-Annual (6M)</option>
            <option value={12}>Annual (12M)</option>
          </select>
        </div>

        <div className="pt-4">
          <Button type="submit" disabled={isRunning} size="sm" className="gap-2">
            <Play className="w-4 h-4 fill-paper" />
            {isRunning ? "Running Simulation..." : "Run Simulation"}
          </Button>
        </div>
      </form>
    </Card>
  );
};
