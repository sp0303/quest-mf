import React, { useEffect } from "react";
import { ChevronLeft, ChevronRight, X, Sparkles, BookOpen } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { TourStep, TourMode } from "../types";
import { TourStepBody } from "./TourStepBody";

export interface TourCardProps {
  step: TourStep;
  currentStepIndex: number;
  totalSteps: number;
  mode: TourMode;
  onNext: () => void;
  onPrev: () => void;
  onSkip: () => void;
  onToggleMode: (mode: TourMode) => void;
}

export const TourCard: React.FC<TourCardProps> = ({
  step,
  currentStepIndex,
  totalSteps,
  mode,
  onNext,
  onPrev,
  onSkip,
  onToggleMode,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onSkip();
      if (e.key === "ArrowRight") onNext();
      if (e.key === "ArrowLeft") onPrev();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onSkip, onNext, onPrev]);

  const isLast = currentStepIndex === totalSteps - 1;

  return (
    <div className="w-full max-w-md bg-paper border border-hairline rounded-3xl p-5 shadow-2xl space-y-4 text-ink">
      {/* Header bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="soft" className="text-xs font-semibold">
            {step.badge}
          </Badge>
          <span className="text-xs text-mid-gray">
            {currentStepIndex + 1} of {totalSteps}
          </span>
        </div>
        <button
          onClick={onSkip}
          aria-label="Close tour"
          className="text-mid-gray hover:text-ink p-1 rounded-full hover:bg-canvas transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Mode Switcher */}
      <div className="flex bg-canvas p-1 rounded-2xl border border-hairline text-xs font-medium">
        <button
          onClick={() => onToggleMode("grade5")}
          className={`flex-1 py-1.5 px-2 rounded-xl flex items-center justify-center gap-1.5 transition-all ${
            mode === "grade5"
              ? "bg-paper text-ink shadow-sm font-semibold"
              : "text-mid-gray hover:text-ink"
          }`}
        >
          <Sparkles className="w-3.5 h-3.5 text-ink" />
          <span>Grade 5 Mode 🎒</span>
        </button>
        <button
          onClick={() => onToggleMode("quant")}
          className={`flex-1 py-1.5 px-2 rounded-xl flex items-center justify-center gap-1.5 transition-all ${
            mode === "quant"
              ? "bg-paper text-ink shadow-sm font-semibold"
              : "text-mid-gray hover:text-ink"
          }`}
        >
          <BookOpen className="w-3.5 h-3.5 text-mid-gray" />
          <span>Quant Mode 📐</span>
        </button>
      </div>

      {/* Body content */}
      <div className="space-y-2">
        <h2 className="text-lg font-bold tracking-tight text-ink">
          {step.title}
        </h2>
        <TourStepBody step={step} mode={mode} />
      </div>

      {/* Navigation buttons */}
      <div className="flex items-center justify-between pt-2 border-t border-hairline">
        <Button
          variant="secondary"
          size="sm"
          onClick={onPrev}
          disabled={currentStepIndex === 0}
          className="gap-1 text-xs"
        >
          <ChevronLeft className="w-3.5 h-3.5" />
          Back
        </Button>
        <div className="flex items-center gap-2">
          <Button
            variant="default"
            size="sm"
            onClick={onNext}
            className="gap-1 text-xs px-4"
          >
            {isLast ? "Done! 🚀" : "Next"}
            {!isLast && <ChevronRight className="w-3.5 h-3.5" />}
          </Button>
        </div>
      </div>
    </div>
  );
};
