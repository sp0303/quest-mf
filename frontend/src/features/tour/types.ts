export type TourMode = "grade5" | "quant";

export interface TourStep {
  id: string;
  route: string;
  targetSelector?: string;
  title: string;
  badge: string;
  grade5Story: {
    analogy: string;
    description: string;
    funFact: string;
  };
  quantExplanation: {
    metric: string;
    formula?: string;
    details: string;
  };
  placement?: "top" | "bottom" | "left" | "right" | "center";
}

export interface TourState {
  isOpen: boolean;
  currentStepIndex: number;
  mode: TourMode;
  hasSeenWelcome: boolean;
  hasCompleted: boolean;
  startTour: (stepIndex?: number) => void;
  nextStep: () => void;
  prevStep: () => void;
  skipTour: () => void;
  setMode: (mode: TourMode) => void;
  dismissWelcome: () => void;
  resetTour: () => void;
}
