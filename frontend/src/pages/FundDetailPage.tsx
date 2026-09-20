import React, { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ErrorCard } from "@/components/ui/ErrorCard";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  FundHeader,
  FundHoldingsTab,
  FundMetricsCard,
  FundNavChart,
  FundOverviewTab,
  FundOverlapTab,
  useFundDetail,
} from "@/features/fund-detail";
import { SEO } from "@/components/common/SEO";

type TabKey = "quant" | "overview" | "holdings" | "overlap";

export const FundDetailPage: React.FC = () => {
  const { portfolioId } = useParams<{ portfolioId: string }>();
  const navigate = useNavigate();
  const pid = parseInt(portfolioId || "101", 10);
  const [activeTab, setActiveTab] = useState<TabKey>("quant");

  const {
    summary,
    risk,
    navHistory,
    profile,
    holdings,
    isProfileLoading,
    isHoldingsLoading,
    isLoading,
    isError,
    error,
    refetch,
  } = useFundDetail(pid);

  const pageTitle = summary
    ? `${summary.fund_name} — Historical NAV, Alpha & Sharpe | quest-mf`
    : "Mutual Fund Quantitative Analytics | quest-mf";
  const pageDesc = summary
    ? `Comprehensive quantitative analytics for ${summary.fund_name} (${summary.amc}): rolling returns, benchmark-relative alpha, composite rank, Sharpe ratio, and canonical direct-growth NAV history.`
    : "Mutual fund quantitative analytics and performance metrics.";

  return (
    <div className="space-y-6">
      <SEO
        title={pageTitle}
        description={pageDesc}
        keywords={`mutual fund, ${summary?.fund_name || "fund"}, ${summary?.amc || "AMC"}, NAV history, alpha, Sharpe ratio, direct mutual funds`}
        canonicalPath={`/fund/${pid}`}
      />
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

          {/* Accessible Tab Navigation */}
          <div className="flex border-b border-hairline gap-2 overflow-x-auto" role="tablist" aria-label="Fund detail views">
            <button
              role="tab"
              aria-selected={activeTab === "quant"}
              onClick={() => setActiveTab("quant")}
              className={`pb-2.5 px-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === "quant"
                  ? "border-primary text-ink font-semibold"
                  : "border-transparent text-mid-gray hover:text-ink"
              }`}
            >
              Quant & Returns
            </button>
            <button
              role="tab"
              aria-selected={activeTab === "overview"}
              onClick={() => setActiveTab("overview")}
              className={`pb-2.5 px-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === "overview"
                  ? "border-primary text-ink font-semibold"
                  : "border-transparent text-mid-gray hover:text-ink"
              }`}
            >
              Overview & Factsheet
            </button>
            <button
              role="tab"
              aria-selected={activeTab === "holdings"}
              onClick={() => setActiveTab("holdings")}
              className={`pb-2.5 px-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === "holdings"
                  ? "border-primary text-ink font-semibold"
                  : "border-transparent text-mid-gray hover:text-ink"
              }`}
            >
              Holdings & Allocation
            </button>
            <button
              role="tab"
              aria-selected={activeTab === "overlap"}
              onClick={() => setActiveTab("overlap")}
              className={`pb-2.5 px-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === "overlap"
                  ? "border-primary text-ink font-semibold"
                  : "border-transparent text-mid-gray hover:text-ink"
              }`}
            >
              Portfolio Overlap
            </button>
          </div>

          {/* Tab Content Panels */}
          {activeTab === "quant" && (
            <div className="space-y-6" role="tabpanel" aria-label="Quant and Returns">
              <FundMetricsCard summary={summary} risk={risk} />
              <FundNavChart
                dates={navHistory?.dates}
                navs={navHistory?.navs}
                loading={isLoading}
              />
            </div>
          )}

          {activeTab === "overview" && (
            <div role="tabpanel" aria-label="Overview & Factsheet">
              <FundOverviewTab
                profile={profile || null}
                summary={summary}
                isLoading={isProfileLoading}
              />
            </div>
          )}

          {activeTab === "holdings" && (
            <div role="tabpanel" aria-label="Holdings & Allocation">
              <FundHoldingsTab
                holdingsData={holdings || null}
                isLoading={isHoldingsLoading}
              />
            </div>
          )}

          {activeTab === "overlap" && (
            <div role="tabpanel" aria-label="Portfolio Overlap">
              <FundOverlapTab
                currentPortfolioId={summary.portfolio_id}
                currentFundName={summary.fund_name}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
};

