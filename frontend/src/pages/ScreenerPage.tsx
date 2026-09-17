import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import ReactECharts from "echarts-for-react";
import { ArrowUpDown, ChevronRight, SlidersHorizontal, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { NumberCell } from "@/components/ui/NumberCell";
import { Button } from "@/components/ui/Button";

interface ScreenerRow {
  portfolio_id: number;
  fund_name: string;
  amc: string;
  ret_1m: number;
  ret_3m: number;
  ret_6m: number;
  ret_1y: number;
  cagr_3y: number;
  shp_3m: number;
  peer_pct_3m: number;
  alpha_3m: number;
  ir_3y: number;
  mdd_3y: number;
  ter: number;
  composite: number;
  confidence: number;
  quadrant: number;
  investable: boolean;
}

export const ScreenerPage: React.FC = () => {
  const navigate = useNavigate();
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [sortBy, setSortBy] = useState<string>("composite");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  // Fetch categories
  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: async () => {
      const res = await fetch("/api/funds/v1/categories");
      return res.json();
    },
  });

  // Fetch screener rows
  const { data: funds = [], isLoading } = useQuery<ScreenerRow[]>({
    queryKey: ["screener", selectedCategory, sortBy, sortDir],
    queryFn: async () => {
      const params = new URLSearchParams({
        sort: sortBy,
        direction: sortDir,
      });
      if (selectedCategory !== null) {
        params.append("category_id", selectedCategory.toString());
      }
      const res = await fetch(`/api/screener/v1/screener?${params.toString()}`);
      return res.json();
    },
  });

  // 2x2 Matrix ECharts options
  const matrixOption = {
    title: {
      text: "2×2 Quadrant Matrix",
      subtext: "X: Peer Percentile (3M)  |  Y: Own-History Percentile SHP (3M)",
      left: "center",
      textStyle: { fontSize: 14, fontWeight: "600", color: "#0a0a0a" },
      subtextStyle: { fontSize: 11, color: "#737373" },
    },
    tooltip: {
      formatter: (params: any) => {
        const d = params.data;
        return `<b>${d.name}</b><br/>Peer %: ${d.value[0]}%<br/>SHP %: ${d.value[1]}%<br/>Quadrant: Q${d.quadrant}<br/>Composite: ${d.composite}`;
      },
    },
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
        symbolSize: 14,
        data: funds.map((f) => ({
          name: f.fund_name,
          value: [Math.round(f.peer_pct_3m), Math.round(f.shp_3m)],
          quadrant: f.quadrant,
          composite: f.composite,
          itemStyle: {
            color:
              f.quadrant === 1
                ? "#0a0a0a"
                : f.quadrant === 2
                ? "#737373"
                : f.quadrant === 4
                ? "#a3a3a3"
                : "#d4d4d4",
          },
        })),
        markLine: {
          silent: true,
          lineStyle: { color: "#e5e5e5", type: "solid", width: 1.5 },
          data: [{ xAxis: 50 }, { yAxis: 50 }],
        },
      },
    ],
    grid: { left: 40, right: 30, top: 60, bottom: 40 },
  };

  const toggleSort = (col: string) => {
    if (sortBy === col) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortBy(col);
      setSortDir("desc");
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Category Filter */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">
            Mutual Fund Quant Screener
          </h1>
          <p className="text-sm text-mid-gray mt-1">
            Rolling-window, benchmark-relative analysis with execution realism & cost awareness.
          </p>
        </div>

        {/* Category Pills */}
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant={selectedCategory === null ? "default" : "secondary"}
            onClick={() => setSelectedCategory(null)}
          >
            All Categories
          </Button>
          {categories.map((c: any) => (
            <Button
              key={c.category_id}
              size="sm"
              variant={selectedCategory === c.category_id ? "default" : "secondary"}
              onClick={() => setSelectedCategory(c.category_id)}
            >
              {c.label}
            </Button>
          ))}
        </div>
      </div>

      {/* Grid: 2/3 Table + 1/3 Matrix Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Table View (2 Cols) */}
        <Card className="lg:col-span-2 overflow-x-auto p-0 border border-hairline">
          <div className="p-4 border-b border-hairline flex items-center justify-between">
            <span className="font-semibold text-sm text-ink flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4 text-mid-gray" />
              Screened Portfolios ({funds.length})
            </span>
            <span className="text-xs text-mid-gray">Click row for deep-dive panel</span>
          </div>

          <table className="w-full text-left text-sm">
            <thead className="bg-surface-alt border-b border-hairline text-xs uppercase text-mid-gray tracking-wider">
              <tr>
                <th className="py-3 px-4">Fund & AMC</th>
                <th
                  className="py-3 px-3 cursor-pointer text-right hover:text-ink"
                  onClick={() => toggleSort("composite")}
                >
                  <div className="flex items-center justify-end gap-1">
                    Score
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th
                  className="py-3 px-3 cursor-pointer text-right hover:text-ink"
                  onClick={() => toggleSort("ret_3m")}
                >
                  3M Return
                </th>
                <th
                  className="py-3 px-3 cursor-pointer text-right hover:text-ink"
                  onClick={() => toggleSort("peer_pct_3m")}
                >
                  Peer % (3M)
                </th>
                <th
                  className="py-3 px-3 cursor-pointer text-right hover:text-ink"
                  onClick={() => toggleSort("shp_3m")}
                >
                  SHP (3M)
                </th>
                <th
                  className="py-3 px-3 cursor-pointer text-right hover:text-ink"
                  onClick={() => toggleSort("cagr_3y")}
                >
                  3Y CAGR
                </th>
                <th className="py-3 px-4 text-center">Quadrant</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-mid-gray">
                    Loading quant scores from cloud database...
                  </td>
                </tr>
              ) : funds.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-mid-gray">
                    No funds match the current filter criteria.
                  </td>
                </tr>
              ) : (
                funds.map((f) => (
                  <tr
                    key={f.portfolio_id}
                    onClick={() => navigate(`/funds/${f.portfolio_id}`)}
                    className="hover:bg-surface-alt cursor-pointer transition-colors group"
                  >
                    <td className="py-3.5 px-4 font-medium text-ink max-w-[220px]">
                      <div className="truncate font-semibold group-hover:underline">
                        {f.fund_name}
                      </div>
                      <div className="text-xs text-mid-gray truncate mt-0.5">{f.amc}</div>
                    </td>
                    <td className="py-3.5 px-3 text-right">
                      <span className="font-bold text-ink tabular-nums text-sm bg-canvas px-2 py-0.5 rounded-xl border border-hairline">
                        {f.composite.toFixed(1)}
                      </span>
                    </td>
                    <td className="py-3.5 px-3 text-right">
                      <NumberCell value={f.ret_3m} isPercent={true} />
                    </td>
                    <td className="py-3.5 px-3 text-right tabular-nums text-ink font-medium">
                      {f.peer_pct_3m !== null ? `${Math.round(f.peer_pct_3m)}%` : "—"}
                    </td>
                    <td className="py-3.5 px-3 text-right tabular-nums text-mid-gray">
                      {f.shp_3m !== null ? `${Math.round(f.shp_3m)}%` : "—"}
                    </td>
                    <td className="py-3.5 px-3 text-right">
                      <NumberCell value={f.cagr_3y} isPercent={true} />
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      <Badge
                        variant={
                          f.quadrant === 1
                            ? "solid"
                            : f.quadrant === 2
                            ? "soft"
                            : "outline"
                        }
                      >
                        Q{f.quadrant}
                      </Badge>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </Card>

        {/* 2x2 Quadrant Chart (1 Col) */}
        <Card className="flex flex-col justify-between p-4">
          <div className="h-[360px] w-full">
            <ReactECharts option={matrixOption} style={{ height: "100%", width: "100%" }} />
          </div>

          <div className="mt-4 pt-4 border-t border-hairline text-xs text-mid-gray space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-ink">Q1 (Top-Right):</span>
              <span>High Peer Strength & High Historical Persistence</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="font-semibold text-ink">Q2 (Top-Left):</span>
              <span>Lagging Peers, but High vs Own History</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="font-semibold text-ink">Q4 (Bottom-Right):</span>
              <span>Leading Peers, but Subdued vs Own History</span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};
