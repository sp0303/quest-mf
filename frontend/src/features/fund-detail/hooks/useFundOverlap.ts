import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { PortfolioOverlapResponse } from "@/lib/schema";

export function useFundOverlap(portfolioId: number, compareWithId: number | null) {
  return useQuery<PortfolioOverlapResponse | null>({
    queryKey: ["fundOverlap", portfolioId, compareWithId],
    queryFn: () => {
      if (!compareWithId) return null;
      return api.getFundOverlap(portfolioId, compareWithId);
    },
    enabled: !!compareWithId && compareWithId !== portfolioId,
  });
}
