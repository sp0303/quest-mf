import React from "react";
import { ArrowLeft } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { FundSummary } from "@/lib/schema";

export interface FundHeaderProps {
  summary: FundSummary;
  onBack: () => void;
}

export const FundHeader: React.FC<FundHeaderProps> = ({ summary, onBack }) => {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <Button
          variant="secondary"
          size="sm"
          onClick={onBack}
          aria-label="Back to screener"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back
        </Button>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-ink">{summary.fund_name}</h1>
            <Badge variant={summary.quadrant === 1 ? "solid" : "soft"}>
              Quadrant {summary.quadrant}
            </Badge>
          </div>
          <p className="text-xs text-mid-gray mt-0.5">
            {summary.amc} • Model: {summary.model_version} • As of {summary.as_of_date}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <div className="text-right">
          <div className="text-xs text-mid-gray">Composite Score</div>
          <div className="text-2xl font-bold text-ink">{summary.composite == null ? "—" : summary.composite.toFixed(1)}</div>
        </div>
      </div>
    </div>
  );
};
