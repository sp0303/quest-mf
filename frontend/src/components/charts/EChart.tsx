import React, { Suspense, lazy, useEffect, useRef, useState } from "react";
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
  const containerRef = useRef<HTMLDivElement>(null);
  const [isInView, setIsInView] = useState(false);

  useEffect(() => {
    if (isInView) return;
    const el = containerRef.current;
    if (!el) return;

    if (typeof IntersectionObserver === "undefined") {
      setIsInView(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setIsInView(true);
          observer.disconnect();
        }
      },
      { rootMargin: "200px" }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [isInView]);

  return (
    <div
      ref={containerRef}
      style={props.style || { height: "100%", width: "100%" }}
      className={props.className}
    >
      {isInView ? (
        <Suspense
          fallback={
            <div
              style={{ height: "100%", width: "100%" }}
              className="flex items-center justify-center bg-surface-alt/40 animate-pulse rounded-2xl"
              role="img"
              aria-label="Loading Chart..."
            >
              <div className="text-xs text-mid-gray">Loading chart visualization...</div>
            </div>
          }
        >
          <LazyEChartInner {...props} />
        </Suspense>
      ) : (
        <div
          style={{ height: "100%", width: "100%" }}
          className="flex items-center justify-center bg-surface-alt/40 rounded-2xl"
          role="img"
          aria-label="Chart placeholder"
        >
          <div className="text-xs text-mid-gray">Loading visualization...</div>
        </div>
      )}
    </div>
  );
};

