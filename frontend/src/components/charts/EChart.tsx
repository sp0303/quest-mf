import React, { Suspense, lazy } from "react";
import type { EChartsOption } from "echarts";

const LazyEChartInner = lazy(() =>
  import("./EChartInner").then((mod) => ({ default: mod.EChartInner }))
);

export interface EChartProps {
  option: EChartsOption;
  style?: React.CSSProperties;
  className?: string;
  loading?: boolean;
}

export const EChart: React.FC<EChartProps> = (props) => {
  return (
    <Suspense
      fallback={
        <div
          style={props.style || { height: "100%", width: "100%" }}
          className={`flex items-center justify-center bg-surface-alt/40 animate-pulse rounded-2xl ${
            props.className || ""
          }`}
          role="img"
          aria-label="Loading Chart..."
        >
          <div className="text-xs text-mid-gray">Loading chart visualization...</div>
        </div>
      }
    >
      <LazyEChartInner {...props} />
    </Suspense>
  );
};

