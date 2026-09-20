import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useFundDetail(portfolioId: number) {
  const summaryQuery = useQuery({
    queryKey: ["fundSummary", portfolioId],
    queryFn: () => api.getFundSummary(portfolioId),
  });

  const riskQuery = useQuery({
    queryKey: ["fundRisk", portfolioId],
    queryFn: () => api.getFundRisk(portfolioId),
  });

  const navHistoryQuery = useQuery({
    queryKey: ["fundNavHistory", portfolioId],
    queryFn: () => api.getFundNavHistory(portfolioId),
  });

  const profileQuery = useQuery({
    queryKey: ["fundProfile", portfolioId],
    queryFn: () => api.getFundProfile(portfolioId),
  });

  const holdingsQuery = useQuery({
    queryKey: ["fundHoldings", portfolioId],
    queryFn: () => api.getFundHoldings(portfolioId),
  });

  const isLoading =
    summaryQuery.isLoading || riskQuery.isLoading || navHistoryQuery.isLoading;
  const isError = summaryQuery.isError || riskQuery.isError;
  const error = summaryQuery.error || riskQuery.error;

  return {
    summary: summaryQuery.data,
    risk: riskQuery.data,
    navHistory: navHistoryQuery.data,
    profile: profileQuery.data,
    holdings: holdingsQuery.data,
    isProfileLoading: profileQuery.isLoading,
    isHoldingsLoading: holdingsQuery.isLoading,
    isLoading,
    isError,
    error,
    refetch: () => {
      summaryQuery.refetch();
      riskQuery.refetch();
      navHistoryQuery.refetch();
      profileQuery.refetch();
      holdingsQuery.refetch();
    },
  };
}
