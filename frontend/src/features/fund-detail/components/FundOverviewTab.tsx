import React from "react";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Badge } from "@/components/ui/Badge";
import type { FundProfile, FundSummary } from "@/lib/schema";

export interface FundOverviewTabProps {
  profile: FundProfile | null;
  summary: FundSummary;
  isLoading?: boolean;
}

export const FundOverviewTab: React.FC<FundOverviewTabProps> = ({ profile, summary, isLoading }) => {
  if (isLoading) {
    return <Skeleton className="h-48 rounded-3xl" />;
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="p-4 bg-paper border-hairline rounded-3xl">
          <div className="text-xs text-mid-gray">Fund Manager</div>
          <div className="text-sm font-semibold mt-1 text-ink line-clamp-1">
            {profile?.fund_manager || "Professional Team"}
          </div>
        </Card>
        <Card className="p-4 bg-paper border-hairline rounded-3xl">
          <div className="text-xs text-mid-gray">AUM (AUM Cr)</div>
          <div className="text-base font-semibold mt-1 text-ink">
            {profile?.aum_cr ? `₹${profile.aum_cr.toLocaleString("en-IN")} Cr` : "—"}
          </div>
        </Card>
        <Card className="p-4 bg-paper border-hairline rounded-3xl">
          <div className="text-xs text-mid-gray">Expense Ratio (TER)</div>
          <div className="text-base font-semibold mt-1 text-ink">
            {profile?.ter_pct != null ? `${(profile.ter_pct * 100).toFixed(2)}%` : summary.ter != null ? `${(summary.ter * 100).toFixed(2)}%` : "—"}
          </div>
        </Card>
        <Card className="p-4 bg-paper border-hairline rounded-3xl">
          <div className="text-xs text-mid-gray">Turnover Ratio</div>
          <div className="text-base font-semibold mt-1 text-ink">
            {profile?.portfolio_turnover_ratio != null ? `${profile.portfolio_turnover_ratio.toFixed(1)}%` : "—"}
          </div>
        </Card>
        <Card className="p-4 bg-paper border-hairline rounded-3xl">
          <div className="text-xs text-mid-gray">P/E Ratio</div>
          <div className="text-base font-semibold mt-1 text-ink">
            {profile?.pe_ratio != null ? profile.pe_ratio.toFixed(2) : "—"}
          </div>
        </Card>
        <Card className="p-4 bg-paper border-hairline rounded-3xl">
          <div className="text-xs text-mid-gray">P/B Ratio</div>
          <div className="text-base font-semibold mt-1 text-ink">
            {profile?.pb_ratio != null ? profile.pb_ratio.toFixed(2) : "—"}
          </div>
        </Card>
        <Card className="p-4 bg-paper border-hairline rounded-3xl">
          <div className="text-xs text-mid-gray">Riskometer</div>
          <div className="mt-1">
            <Badge variant="soft">{profile?.riskometer || "High Risk"}</Badge>
          </div>
        </Card>
        <Card className="p-4 bg-paper border-hairline rounded-3xl">
          <div className="text-xs text-mid-gray">Minimum SIP</div>
          <div className="text-base font-semibold mt-1 text-ink">
            {profile?.min_sip_amount ? `₹${profile.min_sip_amount}` : "₹500"}
          </div>
        </Card>
      </div>
      <div className="text-xs text-mid-gray px-1 italic">
        Factual evidence only (Rule Q16). No subjective buy or sell recommendations.
      </div>
    </div>
  );
};
