import React from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { ErrorCard } from "@/components/ui/ErrorCard";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  QuadrantMatrixChart,
  ScreenerFilters,
  ScreenerTable,
  useScreener,
} from "@/features/screener";
import { SEO } from "@/components/common/SEO";

export const ScreenerPage: React.FC = () => {
  const navigate = useNavigate();
  const {
    categoryId,
    sort,
    setCategory,
    setSorting,
    categories,
    funds,
    matrixData,
    isLoading,
    isError,
    error,
    refetch,
  } = useScreener();

  return (
    <div className="space-y-6">
      <SEO
        title="Mutual Fund Quant Screener & 2x2 Matrix | quest-mf"
        description="Screen Indian direct mutual funds using rolling returns, benchmark TRI alpha, Sharpe ratios, and 2x2 quadrant peer percentiles with zero lookahead bias."
        keywords="mutual fund screener, quant screener, direct mutual funds, rolling returns, Indian mutual funds, Sharpe ratio, alpha, AMFI NAV, equity mutual funds, Sharat Patnayakuni"
        canonicalPath="/"
      />
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink flex items-center gap-2">
            <span>Quant Screener</span>
            <Sparkles className="w-5 h-5 text-ink-soft" />
          </h1>
          <p className="text-xs text-mid-gray mt-0.5">
            Rolling-window, benchmark-relative peer ranking with zero lookahead bias
          </p>
        </div>
        <ScreenerFilters
          categories={categories}
          selectedCategoryId={categoryId}
          onSelectCategory={setCategory}
        />
      </div>

      {/* 4-State Handling */}
      {isError && (
        <ErrorCard
          title="Failed to load screener data"
          message={error instanceof Error ? error.message : "Unknown error"}
          onRetry={() => refetch()}
        />
      )}

      {isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-[280px]" />
          <Skeleton className="h-64" />
        </div>
      )}

      {!isLoading && !isError && funds.length === 0 && (
        <div className="p-12 text-center rounded-3xl border border-hairline bg-paper text-mid-gray">
          No funds found matching the selected filter.
        </div>
      )}

      {!isLoading && !isError && funds.length > 0 && (
        <>
          <QuadrantMatrixChart
            data={matrixData}
            onSelectFund={(id) => navigate(`/fund/${id}`)}
          />
          <ScreenerTable
            funds={funds}
            sortBy={sort}
            sortDir=""
            onSort={setSorting}
            onSelectFund={(id) => navigate(`/fund/${id}`)}
          />
        </>
      )}
    </div>
  );
};
