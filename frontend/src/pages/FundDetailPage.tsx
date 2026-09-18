import React from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ErrorCard } from "@/components/ui/ErrorCard";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  FundHeader,
  FundMetricsCard,
  FundNavChart,
  useFundDetail,
} from "@/features/fund-detail";

export const FundDetailPage: React.FC = () => {
  const { portfolioId } = useParams<{ portfolioId: string }>();
  const navigate = useNavigate();
  const pid = parseInt(portfolioId || "101", 10);

  const { summary, risk, navHistory, isLoading, isError, error, refetch } =
    useFundDetail(pid);

  return (
    <div className="space-y-6">
      {isError && (
        <ErrorCard
          title="Failed to load fund details"
          message={error instanceof Error ? error.message : "Fund not found"}
          onRetry={refetch}
        />
      )}

      {isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-16" />
          <Skeleton className="h-32" />
          <Skeleton className="h-[340px]" />
        </div>
      )}

      {!isLoading && summary && (
        <>
          <FundHeader summary={summary} onBack={() => navigate("/")} />
          <FundMetricsCard summary={summary} risk={risk} />
          <FundNavChart
            dates={navHistory?.dates}
            navs={navHistory?.navs}
            loading={isLoading}
          />
        </>
      )}
    </div>
  );
};
