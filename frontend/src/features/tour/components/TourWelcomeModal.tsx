import React from "react";
import { Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useTourStore } from "../useTourStore";

export const TourWelcomeModal: React.FC = () => {
  const { hasSeenWelcome, isOpen, startTour, dismissWelcome } = useTourStore();

  if (hasSeenWelcome || isOpen) return null;

  return (
    <aside
      aria-label="Welcome Tour Banner"
      className="fixed bottom-5 right-5 z-40 max-w-sm w-[calc(100vw-2.5rem)] bg-paper border border-hairline rounded-3xl p-5 shadow-xl animate-in slide-in-from-bottom-4 duration-300"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="w-9 h-9 rounded-2xl bg-canvas flex items-center justify-center shrink-0">
          <Sparkles className="w-5 h-5 text-ink" />
        </div>
        <div className="flex-1 space-y-1">
          <h2 className="text-sm font-semibold text-ink tracking-tight">
            New to quest.mf?
          </h2>
          <p className="text-xs text-mid-gray leading-relaxed">
            Take a 2-minute tour explaining all quant tools with simple 5th-grade analogies!
          </p>
        </div>
        <button
          onClick={dismissWelcome}
          aria-label="Dismiss welcome banner"
          className="text-mid-gray hover:text-ink p-1 -mr-1 rounded-full"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex items-center gap-2 mt-4 pt-3 border-t border-hairline">
        <Button
          size="sm"
          variant="default"
          onClick={() => startTour(0)}
          className="flex-1 text-xs gap-1.5"
        >
          <span>Start Tour 🎒</span>
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={dismissWelcome}
          className="text-xs"
        >
          Skip
        </Button>
      </div>
    </aside>
  );
};
