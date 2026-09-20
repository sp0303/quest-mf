import React from "react";
import type { TourStep, TourMode } from "../types";

export interface TourStepBodyProps {
  step: TourStep;
  mode: TourMode;
}

export const TourStepBody: React.FC<TourStepBodyProps> = ({ step, mode }) => {
  if (mode === "quant") {
    return (
      <div className="space-y-2">
        <div className="p-3 bg-canvas/70 rounded-2xl border border-hairline/80">
          <div className="text-xs font-bold text-ink uppercase tracking-wider mb-1">
            {step.quantExplanation.metric}
          </div>
          {step.quantExplanation.formula && (
            <div className="font-mono text-xs text-ink bg-paper px-2 py-1 rounded-xl border border-hairline my-1.5 inline-block">
              {step.quantExplanation.formula}
            </div>
          )}
          <p className="text-sm text-ink-soft leading-relaxed">
            {step.quantExplanation.details}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="p-3 bg-canvas/70 rounded-2xl border border-hairline/80">
        <div className="text-xs font-bold text-ink uppercase tracking-wider mb-1">
          {step.grade5Story.analogy}
        </div>
        <p className="text-sm text-ink-soft leading-relaxed">
          {step.grade5Story.description}
        </p>
      </div>
      <div className="text-xs text-mid-gray flex items-center gap-1.5 italic">
        <span>💡</span>
        <span>{step.grade5Story.funFact}</span>
      </div>
    </div>
  );
};
