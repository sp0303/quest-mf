import React from "react";
import { AlertCircle } from "lucide-react";

export const DisclaimerFooter: React.FC = () => {
  return (
    <footer className="mt-12 border-t border-hairline bg-surface-alt py-6 px-4">
      <div className="max-w-7xl mx-auto flex items-start gap-3 text-xs text-mid-gray">
        <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-mid-gray" />
        <div>
          <p className="font-medium text-ink">
            Research & Educational Platform — Not Investment Advice
          </p>
          <p className="mt-1 leading-relaxed">
            Mutual fund investments are subject to market risks. Read all scheme related documents
            carefully. Past performance across rolling windows is historical evidence and does not
            guarantee future results. All figures, metrics, and quadrant classifications are for
            quantitative evaluation purposes only.
          </p>
        </div>
      </div>
      <div className="max-w-7xl mx-auto mt-4 pt-4 border-t border-hairline text-center text-xs text-mid-gray">
        A Sharat Patnayakuni product
      </div>
    </footer>
  );
};
