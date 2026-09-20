import React from "react";
import { Outlet } from "react-router-dom";
import { Topbar } from "./Topbar";
import { DisclaimerFooter } from "./DisclaimerFooter";
import { TourSpotlight, TourWelcomeModal } from "@/features/tour";

export const AppShell: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col bg-canvas text-ink">
      <Topbar />
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-6">
        <Outlet />
      </main>
      <DisclaimerFooter />
      <TourSpotlight />
      <TourWelcomeModal />
    </div>
  );
};
