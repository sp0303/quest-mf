import React, { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart, ScatterChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TitleComponent,
  TooltipComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsOption } from "echarts";
import { getComputedToken } from "@/lib/chartTheme";

// Register necessary modular ECharts components per frontend rule §5.8
echarts.use([
  LineChart,
  ScatterChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  DataZoomComponent,
  MarkLineComponent,
  CanvasRenderer,
]);

export interface EChartInnerProps {
  option: EChartsOption;
  style?: React.CSSProperties;
  className?: string;
  loading?: boolean;
}

export const EChartInner: React.FC<EChartInnerProps> = ({
  option,
  style = { height: "100%", width: "100%" },
  className,
  loading = false,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;

    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current);
    }

    chartInstance.current.setOption(option, true);

    const handleResize = () => {
      chartInstance.current?.resize();
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, [option]);

  useEffect(() => {
    if (chartInstance.current) {
      if (loading) {
        chartInstance.current.showLoading("default", {
          text: "Loading...",
          color: getComputedToken("--color-ink", "#0a0a0a"),
          textColor: getComputedToken("--color-mid-gray", "#737373"),
          maskColor: "rgba(255, 255, 255, 0.8)",
          zlevel: 0,
        });
      } else {
        chartInstance.current.hideLoading();
      }
    }
  }, [loading]);

  useEffect(() => {
    return () => {
      chartInstance.current?.dispose();
      chartInstance.current = null;
    };
  }, []);

  return (
    <div
      ref={chartRef}
      style={style}
      className={className}
      role="img"
      aria-label="Quant Visualization Chart"
    />
  );
};
