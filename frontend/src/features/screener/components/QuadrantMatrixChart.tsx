import React, { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { EChart } from "@/components/charts/EChart";
import { Card } from "@/components/ui/Card";
import type { MatrixItem } from "@/lib/schema";

export interface QuadrantMatrixChartProps {
  data: MatrixItem[];
  onSelectFund?: (portfolioId: number) => void;
  loading?: boolean;
}

export const QuadrantMatrixChart: React.FC<QuadrantMatrixChartProps> = ({
  data,
  loading = false,
}) => {
  const option: EChartsOption = useMemo(() => {
    return {

      title: {
        text: "2×2 Quadrant Matrix",
        subtext: "X: Peer Percentile (3M)  |  Y: Own-History Percentile SHP (3M)",
        left: "center",
        textStyle: { fontSize: 13, fontWeight: "bold" as const, color: "#0a0a0a" },

        subtextStyle: { fontSize: 11, color: "#737373" },
      },
      tooltip: {
        formatter: (params: any) => {
          const d = params.data;
          if (!d) return "";
          return `<b>${d.name}</b><br/>Peer: ${d.value[0]}%<br/>SHP: ${d.value[1]}%<br/>Quadrant: Q${d.quadrant}<br/>Composite: ${d.composite.toFixed(1)}`;
        },
      },

      grid: { top: 60, right: 30, bottom: 40, left: 40 },
      xAxis: {
        type: "value",
        min: 0,
        max: 100,
        splitLine: { lineStyle: { type: "dashed", color: "#e5e5e5" } },
        axisLine: { lineStyle: { color: "#737373" } },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 100,
        splitLine: { lineStyle: { type: "dashed", color: "#e5e5e5" } },
        axisLine: { lineStyle: { color: "#737373" } },
      },
      series: [
        {
          type: "scatter",
          symbolSize: 12,
          data: data.map((d) => ({
            name: d.fund_name,
            value: [Math.round(d.peer_pct_3m), Math.round(d.shp_3m)],
            quadrant: d.quadrant,
            composite: d.composite,
            itemStyle: {
              color:
                d.quadrant === 1
                  ? "#0a0a0a"
                  : d.quadrant === 2
                  ? "#737373"
                  : "#a3a3a3",
            },
          })),
          markLine: {
            silent: true,
            lineStyle: { color: "#e5e5e5", type: "solid", width: 1.5 },
            data: [{ xAxis: 50 }, { yAxis: 50 }],
          },
        },
      ],
    };
  }, [data]);

  return (
    <Card className="p-4 border-hairline bg-paper rounded-3xl">
      <div className="h-[280px] w-full">
        <EChart option={option} loading={loading} />
      </div>
    </Card>
  );
};
