import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useBacktest() {
  const queryClient = useQueryClient();
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);

  const runsQuery = useQuery({
    queryKey: ["backtestRuns"],
    queryFn: api.listRuns,
  });

  const runs = runsQuery.data || [];

  useEffect(() => {
    if (runs.length > 0 && selectedRunId === null) {
      setSelectedRunId(runs[0].run_id);
    }
  }, [runs, selectedRunId]);

  const selectedRun = runs.find((r) => r.run_id === selectedRunId);

  const seriesQuery = useQuery({
    queryKey: ["backtestSeries", selectedRunId],
    enabled: selectedRunId !== null,
    queryFn: () => api.getRunSeries(selectedRunId!),
  });

  const createMutation = useMutation({
    mutationFn: (params: { topK: number; rebalanceMonths: number }) =>
      api.createRun({
        model_version: "v1_baseline",
        top_k: params.topK,
        rebalance_months: params.rebalanceMonths,
        exec_lag_days: 1,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["backtestRuns"] });
      setSelectedRunId(data.run_id);
    },
  });

  return {
    runs,
    selectedRunId,
    selectedRun,
    setSelectedRunId,
    series: seriesQuery.data,
    isLoading: runsQuery.isLoading,
    isSeriesLoading: seriesQuery.isLoading,
    isCreating: createMutation.isPending,
    createRun: createMutation.mutate,
    isError: runsQuery.isError || createMutation.isError,
    error: runsQuery.error || createMutation.error,
    refetch: runsQuery.refetch,
  };
}
