import React, { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { EChart } from "@/components/charts/EChart";
import { Card } from "@/components/ui/Card";
import type { BacktestSeriesResponse } from "@/lib/schema";

export interface BacktestEquityChartProps {
  series?: BacktestSeriesResponse;
  loading?: boolean;
}

import { getComputedToken } from "@/lib/chartTheme";

export const BacktestEquityChart: React.FC<BacktestEquityChartProps> = ({
  series,
  loading = false,
}) => {
  const option: EChartsOption = useMemo(() => {
    const dates = series?.gross?.map(([d]) => d) || [];
    const grossValues = series?.gross?.map(([, v]) => v) || [];
    const netValues = series?.net?.map(([, v]) => v) || [];

    const ink = getComputedToken("--color-ink", "#0a0a0a");
    const midGray = getComputedToken("--color-mid-gray", "#737373");
    const hairline = getComputedToken("--color-hairline", "#e5e5e5");

    return {
      title: {
        text: "Walk-Forward Portfolio Equity Curve (₹100k Base)",
        left: "left",
        textStyle: { fontSize: 13, fontWeight: "bold" as const, color: ink },
      },
      tooltip: {
        trigger: "axis",
        formatter: (params: any) => {
          let str = `<b>${params[0]?.name}</b><br/>`;
          params.forEach((p: any) => {
            str += `${p.marker} ${p.seriesName}: ₹${Number(p.value).toLocaleString("en-IN")}<br/>`;
          });
          return str;
        },
      },
      legend: { data: ["Gross Equity", "Net Equity (After Friction)"], top: 5 },
      grid: { top: 60, right: 20, bottom: 40, left: 60 },
      xAxis: {
        type: "category",
        data: dates,
        axisLine: { lineStyle: { color: midGray } },
      },
      yAxis: {
        type: "value",
        scale: true,
        splitLine: { lineStyle: { type: "dashed", color: hairline } },
        axisLine: { lineStyle: { color: midGray } },
      },
      series: [
        {
          name: "Gross Equity",
          type: "line",
          data: grossValues,
          smooth: true,
          showSymbol: false,
          lineStyle: { color: midGray, width: 2, type: "dashed" },
        },
        {
          name: "Net Equity (After Friction)",
          type: "line",
          data: netValues,
          smooth: true,
          showSymbol: false,
          lineStyle: { color: ink, width: 2.5 },
        },
      ],
    };
  }, [series]);

  return (
    <Card className="p-4 border-hairline bg-paper rounded-3xl">
      <div className="h-[340px] w-full">
        <EChart option={option} loading={loading} />
      </div>
    </Card>
  );
};
