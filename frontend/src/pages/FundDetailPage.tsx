import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";
import { ArrowLeft, ShieldAlert, TrendingUp, DollarSign, Activity } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { NumberCell } from "@/components/ui/NumberCell";

export const FundDetailPage: React.FC = () => {
  const { portfolioId } = useParams<{ portfolioId: string }>();
  const navigate = useNavigate();
  const pid = parseInt(portfolioId || "101", 10);

  // 1. Fund Profile
  const { data: fundData } = useQuery({
    queryKey: ["fund", pid],
    queryFn: async () => {
      const res = await fetch(`/api/funds/v1/funds/${pid}`);
      if (!res.ok) throw new Error("Fund not found");
      return res.json();
    },
  });

  // 2. Fund Summary Metrics
  const { data: summary } = useQuery({
    queryKey: ["fundSummary", pid],
    queryFn: async () => {
      const res = await fetch(`/api/analytics/v1/funds/${pid}/summary`);
      return res.ok ? res.json() : null;
    },
  });

  // 3. Risk Metrics
  const { data: risk } = useQuery({
    queryKey: ["fundRisk", pid],
    queryFn: async () => {
      const res = await fetch(`/api/analytics/v1/funds/${pid}/risk`);
      return res.ok ? res.json() : null;
    },
  });

  // 4. NAV History Series
  const { data: navData, isLoading: navLoading } = useQuery({
    queryKey: ["navSeries", pid],
    queryFn: async () => {
      const res = await fetch(`/api/market/v1/nav/${pid}?points=1500`);
      return res.ok ? res.json() : null;
    },
  });

  const fund = fundData?.fund;
  const loadRule = fundData?.load_rule;

  // Chart options
  const chartOption = {
    title: {
      text: "Historical Net Asset Value (NAV)",
      left: 10,
      textStyle: { fontSize: 14, fontWeight: "600", color: "#0a0a0a" },
    },
    tooltip: {
      trigger: "axis",
      formatter: (params: any) => {
        const p = params[0];
        return `Date: <b>${p.name}</b><br/>NAV: ₹<b>${p.value.toFixed(2)}</b>`;
      },
    },
    xAxis: {
      type: "category",
      data: navData?.t || [],
      axisLine: { lineStyle: { color: "#737373" } },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      scale: true,
      splitLine: { lineStyle: { type: "dashed", color: "#e5e5e5" } },
    },
    series: [
      {
        name: "NAV",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: navData?.nav || [],
        lineStyle: { color: "#0a0a0a", width: 2 },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(10, 10, 10, 0.15)" },
              { offset: 1, color: "rgba(10, 10, 10, 0.0)" },
            ],
          },
        },
      },
    ],
    grid: { left: 50, right: 30, top: 50, bottom: 40 },
  };

  return (
    <div className="space-y-6">
      {/* Back Button & Title Header */}
      <div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => navigate(-1)}
          className="mb-4 gap-1.5"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Screener
        </Button>

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-ink">
                {fund?.display_name || "Fund Details"}
              </h1>
              {summary?.quadrant && (
                <Badge variant="solid">Quadrant Q{summary.quadrant}</Badge>
              )}
            </div>
            <p className="text-sm text-mid-gray mt-1">
              AMC: <span className="text-ink font-medium">{fund?.amc}</span> · Direct Plan Growth · Launched: {fund?.launch_date}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="bg-paper border border-hairline rounded-2xl px-4 py-2 text-right">
              <div className="text-xs text-mid-gray uppercase tracking-wider font-semibold">Composite Score</div>
              <div className="text-2xl font-bold text-ink tabular-nums">
                {summary?.composite?.toFixed(1) || "—"}
                <span className="text-xs text-mid-gray font-normal"> / 100</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 8-Panel Stat Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="text-xs text-mid-gray uppercase font-semibold">1M Return</div>
          <div className="text-xl font-bold mt-1">
            <NumberCell value={summary?.ret_1m} isPercent={true} />
          </div>
        </Card>

        <Card className="p-4">
          <div className="text-xs text-mid-gray uppercase font-semibold">3M Return</div>
          <div className="text-xl font-bold mt-1">
            <NumberCell value={summary?.ret_3m} isPercent={true} />
          </div>
          <div className="text-xs text-mid-gray mt-1">
            Peer %: <span className="font-semibold text-ink">{Math.round(summary?.peer_pct_3m || 0)}%</span>
          </div>
        </Card>

        <Card className="p-4">
          <div className="text-xs text-mid-gray uppercase font-semibold">1Y Return</div>
          <div className="text-xl font-bold mt-1">
            <NumberCell value={summary?.ret_1y} isPercent={true} />
          </div>
        </Card>

        <Card className="p-4">
          <div className="text-xs text-mid-gray uppercase font-semibold">3Y CAGR</div>
          <div className="text-xl font-bold mt-1">
            <NumberCell value={summary?.cagr_3y} isPercent={true} />
          </div>
        </Card>

        <Card className="p-4">
          <div className="text-xs text-mid-gray uppercase font-semibold">3M Alpha (vs TRI)</div>
          <div className="text-xl font-bold mt-1">
            <NumberCell value={summary?.alpha_3m} isPercent={true} />
          </div>
        </Card>

        <Card className="p-4">
          <div className="text-xs text-mid-gray uppercase font-semibold">3Y Info Ratio</div>
          <div className="text-xl font-bold mt-1 tabular-nums">
            {summary?.ir_3y?.toFixed(2) || "—"}
          </div>
        </Card>

        <Card className="p-4">
          <div className="text-xs text-mid-gray uppercase font-semibold">Ann. Volatility</div>
          <div className="text-xl font-bold mt-1 tabular-nums">
            {risk?.volatility_ann ? `${risk.volatility_ann}%` : "—"}
          </div>
        </Card>

        <Card className="p-4">
          <div className="text-xs text-mid-gray uppercase font-semibold">Max Drawdown (3Y)</div>
          <div className="text-xl font-bold mt-1">
            <NumberCell value={summary?.mdd_3y} isPercent={true} />
          </div>
        </Card>
      </div>

      {/* NAV Chart */}
      <Card className="p-4">
        {navLoading ? (
          <div className="h-[360px] flex items-center justify-center text-mid-gray text-sm">
            Loading NAV time series...
          </div>
        ) : (
          <div className="h-[380px] w-full">
            <ReactECharts option={chartOption} style={{ height: "100%", width: "100%" }} />
          </div>
        )}
      </Card>

      {/* Risk and Costs Panels */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Risk Metrics */}
        <Card className="p-5">
          <h2 className="text-base font-semibold text-ink flex items-center gap-2 mb-4">
            <Activity className="w-4 h-4 text-mid-gray" />
            Risk & Downside Analytics
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between py-1.5 border-b border-hairline">
              <span className="text-mid-gray">Annualized Volatility</span>
              <span className="font-semibold tabular-nums">{risk?.volatility_ann || "—"}%</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-hairline">
              <span className="text-mid-gray">Downside Deviation</span>
              <span className="font-semibold tabular-nums">{risk?.downside_dev_ann || "—"}%</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-hairline">
              <span className="text-mid-gray">Sharpe Ratio (Rf = 6.5%)</span>
              <span className="font-semibold tabular-nums">{risk?.sharpe_ratio || "—"}</span>
            </div>
            <div className="flex justify-between py-1.5">
              <span className="text-mid-gray">Sortino Ratio</span>
              <span className="font-semibold tabular-nums">{risk?.sortino_ratio || "—"}</span>
            </div>
          </div>
        </Card>

        {/* Costs & Friction */}
        <Card className="p-5">
          <h2 className="text-base font-semibold text-ink flex items-center gap-2 mb-4">
            <DollarSign className="w-4 h-4 text-mid-gray" />
            Expense Ratio & Exit Friction
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between py-1.5 border-b border-hairline">
              <span className="text-mid-gray">Total Expense Ratio (TER)</span>
              <span className="font-semibold tabular-nums">
                {summary?.ter ? `${(summary.ter * 100).toFixed(2)}%` : "—"}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-hairline">
              <span className="text-mid-gray">Exit Load Rate</span>
              <span className="font-semibold tabular-nums">
                {summary?.exit_load_rate ? `${(summary.exit_load_rate * 100).toFixed(1)}%` : "Nil"}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-hairline">
              <span className="text-mid-gray">Exit Load Period</span>
              <span className="font-semibold tabular-nums">
                {summary?.exit_load_days ? `${summary.exit_load_days} days` : "—"}
              </span>
            </div>
            <div className="py-2 text-xs text-mid-gray">
              Rule: {loadRule?.rule_text || "Standard SEBI regulated exit terms apply."}
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};
