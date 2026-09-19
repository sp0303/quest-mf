import React, { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { EChart } from "@/components/charts/EChart";
import { Card } from "@/components/ui/Card";
import type { MatrixItem } from "@/lib/schema";

import { getComputedToken } from "@/lib/chartTheme";

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
    const ink = getComputedToken("--color-ink", "#0a0a0a");
    const midGray = getComputedToken("--color-mid-gray", "#737373");
    const hairline = getComputedToken("--color-hairline", "#e5e5e5");

    return {
      title: {
        text: "2×2 Quadrant Matrix",
        subtext: "X: Peer Percentile (3M)  |  Y: Own-History Percentile SHP (3M)",
        left: "center",
        textStyle: { fontSize: 13, fontWeight: "bold" as const, color: ink },
        subtextStyle: { fontSize: 11, color: midGray },
      },
      tooltip: {
        formatter: (params: any) => {
          const d = params.data;
          if (!d) return "";
          const composite = d.composite == null ? "—" : d.composite.toFixed(1);
          return `<b>${d.name}</b><br/>Peer: ${d.value[0]}%<br/>SHP: ${d.value[1]}%<br/>Quadrant: Q${d.quadrant}<br/>Composite: ${composite}`;
        },
      },
      grid: { top: 60, right: 30, bottom: 40, left: 40 },
      xAxis: {
        type: "value",
        min: 0,
        max: 100,
        splitLine: { lineStyle: { type: "dashed", color: hairline } },
        axisLine: { lineStyle: { color: midGray } },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 100,
        splitLine: { lineStyle: { type: "dashed", color: hairline } },
        axisLine: { lineStyle: { color: midGray } },
      },
      series: [
        {
          type: "scatter",
          symbolSize: 12,
          data: data
            .filter((d): d is MatrixItem & { peer_pct_3m: number; shp_3m: number } => d.peer_pct_3m != null && d.shp_3m != null)
            .map((d) => ({
              name: d.fund_name,
              value: [Math.round(d.peer_pct_3m), Math.round(d.shp_3m)],
              quadrant: d.quadrant,
              composite: d.composite,
              itemStyle: {
                color: d.quadrant === 1 ? ink : midGray,
              },
            })),
          markLine: {
            silent: true,
            lineStyle: { color: hairline, type: "solid", width: 1.5 },
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
