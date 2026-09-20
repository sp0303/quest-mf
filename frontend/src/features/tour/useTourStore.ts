import { create } from "zustand";
import type { TourState, TourMode } from "./types";

const WELCOME_KEY = "questmf_tour_welcomed";
const COMPLETED_KEY = "questmf_tour_completed";

const getInitialStorage = (key: string): boolean => {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(key) === "true";
};

export const useTourStore = create<TourState>((set) => ({
  isOpen: false,
  currentStepIndex: 0,
  mode: "grade5",
  hasSeenWelcome: getInitialStorage(WELCOME_KEY),
  hasCompleted: getInitialStorage(COMPLETED_KEY),

  startTour: (stepIndex = 0) => {
    set({
      isOpen: true,
      currentStepIndex: stepIndex,
      hasSeenWelcome: true,
    });
    if (typeof window !== "undefined") {
      window.localStorage.setItem(WELCOME_KEY, "true");
    }
  },

  nextStep: () => {
    set((state) => ({ currentStepIndex: state.currentStepIndex + 1 }));
  },

  prevStep: () => {
    set((state) => ({
      currentStepIndex: Math.max(0, state.currentStepIndex - 1),
    }));
  },

  skipTour: () => {
    set({ isOpen: false, hasCompleted: true, hasSeenWelcome: true });
    if (typeof window !== "undefined") {
      window.localStorage.setItem(COMPLETED_KEY, "true");
      window.localStorage.setItem(WELCOME_KEY, "true");
    }
  },

  setMode: (mode: TourMode) => {
    set({ mode });
  },

  dismissWelcome: () => {
    set({ hasSeenWelcome: true });
    if (typeof window !== "undefined") {
      window.localStorage.setItem(WELCOME_KEY, "true");
    }
  },

  resetTour: () => {
    set({ isOpen: true, currentStepIndex: 0 });
  },
}));
