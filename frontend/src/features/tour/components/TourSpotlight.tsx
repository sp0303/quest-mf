import React, { useEffect, useState, useCallback } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router-dom";
import { useTourStore } from "../useTourStore";
import { TOUR_STEPS } from "../tourSteps";
import { TourCard } from "./TourCard";

interface TargetRect {
  top: number;
  left: number;
  width: number;
  height: number;
}

export const TourSpotlight: React.FC = () => {
  const {
    isOpen,
    currentStepIndex,
    mode,
    nextStep,
    prevStep,
    skipTour,
    setMode,
  } = useTourStore();

  const location = useLocation();
  const navigate = useNavigate();
  const [targetRect, setTargetRect] = useState<TargetRect | null>(null);

  const step = TOUR_STEPS[currentStepIndex];

  const updateTargetRect = useCallback(() => {
    if (!step?.targetSelector) {
      setTargetRect(null);
      return;
    }
    const el = document.querySelector(step.targetSelector);
    if (el) {
      const rect = el.getBoundingClientRect();
      setTargetRect({
        top: rect.top + window.scrollY,
        left: rect.left + window.scrollX,
        width: rect.width,
        height: rect.height,
      });
      el.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } else {
      setTargetRect(null);
    }
  }, [step]);

  useEffect(() => {
    if (!isOpen || !step) return;

    if (step.route && location.pathname !== step.route) {
      navigate(step.route);
    }

    const timer = setTimeout(updateTargetRect, 250);
    window.addEventListener("resize", updateTargetRect);
    window.addEventListener("scroll", updateTargetRect);

    return () => {
      clearTimeout(timer);
      window.removeEventListener("resize", updateTargetRect);
      window.removeEventListener("scroll", updateTargetRect);
    };
  }, [isOpen, step, location.pathname, navigate, updateTargetRect]);

  if (!isOpen || !step) return null;

  const handleNext = () => {
    if (currentStepIndex >= TOUR_STEPS.length - 1) {
      skipTour();
    } else {
      nextStep();
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-50 pointer-events-auto flex items-center justify-center p-4">
      {/* Dimmed backdrop */}
      <div
        className="fixed inset-0 bg-ink/40 backdrop-blur-[1px] transition-opacity"
        onClick={skipTour}
        aria-hidden="true"
      />

      {/* Target highlight cutout outline */}
      {targetRect && (
        <div
          className="absolute border-2 border-paper rounded-2xl shadow-[0_0_0_9999px_rgba(10,10,10,0.45)] pointer-events-none transition-all duration-300"
          style={{
            top: targetRect.top - 6,
            left: targetRect.left - 6,
            width: targetRect.width + 12,
            height: targetRect.height + 12,
          }}
        />
      )}

      {/* Dialog Card */}
      <div className="relative z-10 animate-in fade-in zoom-in-95 duration-200">
        <TourCard
          step={step}
          currentStepIndex={currentStepIndex}
          totalSteps={TOUR_STEPS.length}
          mode={mode}
          onNext={handleNext}
          onPrev={prevStep}
          onSkip={skipTour}
          onToggleMode={setMode}
        />
      </div>
    </div>,
    document.body
  );
};
