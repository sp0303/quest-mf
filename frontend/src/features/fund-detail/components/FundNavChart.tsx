import React, { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { EChart } from "@/components/charts/EChart";
import { Card } from "@/components/ui/Card";

export interface FundNavChartProps {
  dates?: string[];
  navs?: number[];
  loading?: boolean;
}

export const FundNavChart: React.FC<FundNavChartProps> = ({
  dates = [],
  navs = [],
  loading = false,
}) => {
  const option: EChartsOption = useMemo(() => {
    return {

      title: {
        text: "Historical NAV Series (Canonical Direct-Growth)",
        left: "left",
        textStyle: { fontSize: 13, fontWeight: "bold" as const, color: "#0a0a0a" },

      },
      tooltip: {
        trigger: "axis",
        formatter: (params: any) => {
          const item = params[0];
          return `<b>${item.name}</b><br/>NAV: ₹${Number(item.value).toFixed(2)}`;
        },
      },
      grid: { top: 50, right: 20, bottom: 60, left: 50 },
      xAxis: {
        type: "category",
        data: dates,
        axisLine: { lineStyle: { color: "#737373" } },
      },
      yAxis: {
        type: "value",
        scale: true,
        splitLine: { lineStyle: { type: "dashed", color: "#e5e5e5" } },
        axisLine: { lineStyle: { color: "#737373" } },
      },
      dataZoom: [{ type: "inside" }, { type: "slider", bottom: 10 }],
      series: [
        {
          name: "NAV",
          type: "line",
          data: navs,
          smooth: true,
          showSymbol: false,
          lineStyle: { color: "#0a0a0a", width: 2 },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(10, 10, 10, 0.12)" },
                { offset: 1, color: "rgba(10, 10, 10, 0.0)" },
              ],
            },
          },
        },
      ],
    };
  }, [dates, navs]);

  return (
    <Card className="p-4 border-hairline bg-paper rounded-3xl">
      <div className="h-[340px] w-full">
        <EChart option={option} loading={loading} />
      </div>
    </Card>
  );
};
