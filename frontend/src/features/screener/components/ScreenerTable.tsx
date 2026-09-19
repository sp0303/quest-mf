import React, { useRef } from "react";
import { ArrowUpDown, ChevronRight } from "lucide-react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Badge } from "@/components/ui/Badge";
import { NumberCell } from "@/components/ui/NumberCell";
import type { ScreenerRow } from "@/lib/schema";

export interface ScreenerTableProps {
  funds: ScreenerRow[];
  sortBy: string;
  sortDir: string;
  onSort: (col: string) => void;
  onSelectFund: (portfolioId: number) => void;
}

// Module-level column definitions per frontend rule §5.7
const COLUMNS = [
  { key: "fund_name", label: "Fund Name", align: "left" },
  { key: "composite", label: "Score", align: "right" },
  { key: "quadrant", label: "Quadrant", align: "center" },
  { key: "ret_3m", label: "3M Ret", align: "right" },
  { key: "ret_1y", label: "1Y Ret", align: "right" },
  { key: "cagr_3y", label: "3Y CAGR", align: "right" },
  { key: "peer_pct_3m", label: "Peer %", align: "right" },
  { key: "shp_3m", label: "SHP %", align: "right" },
] as const;

const TableRow = React.memo<{ fund: ScreenerRow; onSelect: (id: number) => void }>(
  ({ fund, onSelect }) => (
    <tr
      onClick={() => onSelect(fund.portfolio_id)}
      className="cursor-pointer border-b border-hairline/60 hover:bg-canvas/50 transition-colors"
    >
      <th scope="row" className="py-3 px-4 text-left font-normal">
        <div className="font-medium text-sm text-ink">{fund.fund_name}</div>
        <div className="text-xs text-mid-gray">{fund.amc}</div>
      </th>
      <td className="py-3 px-3 text-right">
        <span className="font-semibold text-sm text-ink">
          {fund.composite == null ? "—" : fund.composite.toFixed(1)}
        </span>
      </td>
      <td className="py-3 px-3 text-center">
        <Badge variant={fund.quadrant === 1 ? "solid" : "soft"}>
          Q{fund.quadrant}
        </Badge>
      </td>
      <td className="py-3 px-3 text-right">
        <NumberCell value={fund.ret_3m} isPercent />
      </td>
      <td className="py-3 px-3 text-right">
        <NumberCell value={fund.ret_1y} isPercent />
      </td>
      <td className="py-3 px-3 text-right">
        <NumberCell value={fund.cagr_3y} isPercent />
      </td>
      <td className="py-3 px-3 text-right">
        <NumberCell value={fund.peer_pct_3m} showSign={false} />
      </td>
      <td className="py-3 px-3 text-right">
        <NumberCell value={fund.shp_3m} showSign={false} />
      </td>
      <td className="py-3 px-2 text-right text-mid-gray" aria-label="View fund details">
        <ChevronRight className="w-4 h-4 inline-block" />
      </td>
    </tr>
  )
);
TableRow.displayName = "TableRow";

export const ScreenerTable: React.FC<ScreenerTableProps> = ({
  funds,
  sortBy,
  onSort,
  onSelectFund,
}) => {
  const parentRef = useRef<HTMLDivElement>(null);
  const shouldVirtualize = funds.length > 50;

  const rowVirtualizer = useVirtualizer({
    count: funds.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 61,
    overscan: 8,
    enabled: shouldVirtualize,
  });

  const virtualRows = shouldVirtualize ? rowVirtualizer.getVirtualItems() : [];
  const paddingTop = shouldVirtualize && virtualRows.length > 0 ? virtualRows[0].start : 0;
  const paddingBottom =
    shouldVirtualize && virtualRows.length > 0
      ? rowVirtualizer.getTotalSize() - virtualRows[virtualRows.length - 1].end
      : 0;

  return (
    <div
      ref={parentRef}
      className={`overflow-auto rounded-2xl border border-hairline bg-paper ${
        shouldVirtualize ? "max-h-[640px]" : ""
      }`}
    >
      <table className="w-full text-left border-collapse" aria-label="Mutual Fund Screener">
        <thead className="sticky top-0 z-10 bg-surface-alt border-b border-hairline">
          <tr className="text-xs text-mid-gray font-medium">
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                scope="col"
                onClick={() => onSort(col.key)}
                className={`py-2.5 px-3 cursor-pointer select-none hover:text-ink transition-colors text-${col.align}`}
              >
                <div className={`inline-flex items-center gap-1 ${col.align === "right" ? "justify-end" : ""}`}>
                  <span>{col.label}</span>
                  <ArrowUpDown className={`w-3 h-3 ${sortBy === col.key ? "text-ink" : "opacity-40"}`} />
                </div>
              </th>
            ))}
            <th scope="col" aria-label="Details" className="py-2.5 px-2 w-8">
              <span className="sr-only">Details</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-hairline/40">
          {shouldVirtualize ? (
            <>
              {paddingTop > 0 && (
                <tr aria-hidden="true">
                  <td colSpan={COLUMNS.length + 1} style={{ height: `${paddingTop}px`, padding: 0 }} />
                </tr>
              )}
              {virtualRows.map((virtualRow) => {
                const fund = funds[virtualRow.index];
                return <TableRow key={fund.portfolio_id} fund={fund} onSelect={onSelectFund} />;
              })}
              {paddingBottom > 0 && (
                <tr aria-hidden="true">
                  <td colSpan={COLUMNS.length + 1} style={{ height: `${paddingBottom}px`, padding: 0 }} />
                </tr>
              )}
            </>
          ) : (
            funds.map((fund) => (
              <TableRow key={fund.portfolio_id} fund={fund} onSelect={onSelectFund} />
            ))
          )}
        </tbody>
      </table>
    </div>
  );
};
