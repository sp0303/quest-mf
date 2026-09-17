import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";
import { BarChart3, Play, History, TrendingUp } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

export const BacktestPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [topK, setTopK] = useState<number>(3);
  const [rebalanceMonths, setRebalanceMonths] = useState<number>(3);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);

  // 1. Fetch runs
  const { data: runs = [], isLoading: runsLoading } = useQuery({
    queryKey: ["backtestRuns"],
    queryFn: async () => {
      const res = await fetch("/api/backtests/v1/runs");
      return res.json();
    },
  });

  // Auto-select latest run
  React.useEffect(() => {
    if (runs.length > 0 && selectedRunId === null) {
      setSelectedRunId(runs[0].run_id);
    }
  }, [runs]);

  // 2. Fetch series for selected run
  const { data: seriesData } = useQuery({
    queryKey: ["backtestSeries", selectedRunId],
    enabled: selectedRunId !== null,
    queryFn: async () => {
      const res = await fetch(`/api/backtests/v1/runs/${selectedRunId}/series`);
      return res.json();
    },
  });

  // 3. Create run mutation
  const createMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch("/api/backtests/v1/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model_version: "v1_baseline",
          top_k: topK,
          rebalance_months: rebalanceMonths,
          exec_lag_days: 1,
        }),
      });
      return res.json();
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["backtestRuns"] });
      setSelectedRunId(data.run_id);
    },
  });

  const selectedRun = runs.find((r: any) => r.run_id === selectedRunId);
  const summary = selectedRun?.summary;

  // Chart options
  const grossDates = seriesData?.gross?.map((pt: any) => pt[0]) || [];
  const grossValues = seriesData?.gross?.map((pt: any) => pt[1]) || [];
  const netValues = seriesData?.net?.map((pt: any) => pt[1]) || [];

  const chartOption = {
    title: {
      text: "Walk-Forward Equity Curve (Gross vs Net of Friction)",
      left: 10,
      textStyle: { fontSize: 14, fontWeight: "600", color: "#0a0a0a" },
    },
    tooltip: { trigger: "axis" },
    legend: { data: ["Gross Equity", "Net Equity (Load + Tax)"], right: 20 },
    xAxis: {
      type: "category",
      data: grossDates,
      axisLine: { lineStyle: { color: "#737373" } },
    },
    yAxis: {
      type: "value",
      scale: true,
      splitLine: { lineStyle: { type: "dashed", color: "#e5e5e5" } },
    },
    series: [
      {
        name: "Gross Equity",
        type: "line",
        data: grossValues,
        lineStyle: { color: "#737373", type: "dashed", width: 2 },
      },
      {
        name: "Net Equity (Load + Tax)",
        type: "line",
        data: netValues,
        lineStyle: { color: "#0a0a0a", width: 2.5 },
      },
    ],
    grid: { left: 60, right: 30, top: 50, bottom: 40 },
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-ink" />
            Walk-Forward Backtesting
          </h1>
          <p className="text-sm text-mid-gray mt-1">
            Simulate historical rebalancing strategies at T+1 NAV with full exit friction & capital gains tax.
          </p>
        </div>

        <Button
          onClick={() => createMutation.mutate()}
          disabled={createMutation.isPending}
          className="gap-2"
        >
          <Play className="w-4 h-4" />
          {createMutation.isPending ? "Simulating..." : "Run New Backtest"}
        </Button>
      </div>

      {/* Configuration & Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="text-xs text-mid-gray uppercase font-semibold">Gross CAGR</div>
          <div className="text-2xl font-bold text-ink tabular-nums mt-1">
            {summary ? `+${(summary.cagr_gross * 100).toFixed(1)}%` : "—"}
          </div>
        </Card>

        <Card className="p-4">
          <div className="text-xs text-mid-gray uppercase font-semibold">Net CAGR (Post-Tax)</div>
          <div className="text-2xl font-bold text-ink tabular-nums mt-1">
            {summary ? `+${(summary.cagr_net * 100).toFixed(1)}%` : "—"}
          </div>
          <div className="text-xs text-ember mt-0.5">
            Friction Drag: -{summary ? ((summary.cagr_gross - summary.cagr_net) * 100).toFixed(1) : "0"}%
          </div>
        </Card>

        <Card className="p-4">
          <div className="text-xs text-mid-gray uppercase font-semibold">Net Sharpe Ratio</div>
          <div className="text-2xl font-bold text-ink tabular-nums mt-1">
            {summary ? summary.sharpe_ratio.toFixed(2) : "—"}
          </div>
        </Card>

        <Card className="p-4">
          <div className="text-xs text-mid-gray uppercase font-semibold">Max Drawdown</div>
          <div className="text-2xl font-bold text-ember tabular-nums mt-1">
            {summary ? `${(summary.max_drawdown * 100).toFixed(1)}%` : "—"}
          </div>
        </Card>
      </div>

      {/* Equity Curve Chart */}
      <Card className="p-4">
        {grossValues.length > 0 ? (
          <div className="h-[380px] w-full">
            <ReactECharts option={chartOption} style={{ height: "100%", width: "100%" }} />
          </div>
        ) : (
          <div className="h-[380px] flex flex-col items-center justify-center text-mid-gray text-sm">
            <History className="w-8 h-8 mb-2 stroke-1" />
            No backtest runs found. Click "Run New Backtest" to generate a simulation.
          </div>
        )}
      </Card>
    </div>
  );
};
