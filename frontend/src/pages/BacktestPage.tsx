import React from "react";
import { BarChart3 } from "lucide-react";
import { ErrorCard } from "@/components/ui/ErrorCard";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  BacktestConfigForm,
  BacktestEquityChart,
  BacktestRunsList,
  BacktestSummaryCard,
  useBacktest,
} from "@/features/backtest";

export const BacktestPage: React.FC = () => {
  const {
    runs,
    selectedRunId,
    selectedRun,
    setSelectedRunId,
    series,
    isLoading,
    isSeriesLoading,
    isCreating,
    createRun,
    isError,
    error,
    refetch,
  } = useBacktest();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink flex items-center gap-2">
          <span>Walk-Forward Backtest Simulator</span>
          <BarChart3 className="w-5 h-5 text-ink-soft" />
        </h1>
        <p className="text-xs text-mid-gray mt-0.5">
          Out-of-sample periodic rebalancing with execution lag, holding bounds, and transaction frictions
        </p>
      </div>

      <BacktestConfigForm onRun={createRun} isRunning={isCreating} />

      {isError && (
        <ErrorCard
          title="Backtest error"
          message={error instanceof Error ? error.message : "Failed to run simulation"}
          onRetry={refetch}
        />
      )}

      {isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-24" />
          <Skeleton className="h-[340px]" />
        </div>
      )}

      {!isLoading && selectedRun && (
        <>
          <BacktestSummaryCard summary={selectedRun.summary} />
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <BacktestEquityChart series={series} loading={isSeriesLoading} />
            </div>
            <div>
              <BacktestRunsList
                runs={runs}
                selectedRunId={selectedRunId}
                onSelectRun={setSelectedRunId}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
};
