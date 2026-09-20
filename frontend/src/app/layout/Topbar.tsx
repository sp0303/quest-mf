import React, { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Activity,
  BarChart3,
  Calculator,
  Compass,
  Database,
  Filter,
  Menu,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { useTourStore } from "@/features/tour";

export const Topbar: React.FC = () => {
  const location = useLocation();
  const { startTour } = useTourStore();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navItems = [
    { label: "Screener", path: "/", icon: Filter },
    { label: "Backtest", path: "/backtest", icon: BarChart3 },
    { label: "Net Calculator", path: "/calculator", icon: Calculator },
    { label: "Data Health", path: "/health", icon: Activity },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-hairline bg-paper/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto flex h-16 items-center justify-between px-4">
        {/* Brand */}
        <div className="flex items-center gap-6">
          <Link
            to="/"
            data-tour="brand-logo"
            className="flex items-center gap-2 font-semibold text-lg tracking-tight"
            aria-label="quest.mf — Mutual Fund Quant Screener by Sharat Patnayakuni"
          >
            <span
              className="w-8 h-8 rounded-2xl bg-ink text-paper flex items-center justify-center font-bold text-sm"
              aria-hidden="true"
            >
              Q
            </span>
            <span>quest<span className="text-mid-gray">.mf</span></span>
          </Link>

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center gap-1" aria-label="Main Navigation">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  aria-label={item.label}
                  className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-2xl text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-canvas text-ink"
                      : "text-mid-gray hover:text-ink hover:bg-surface-alt"
                  }`}
                >
                  <Icon className="w-4 h-4" aria-hidden="true" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Status indicator & Tour trigger */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => startTour(0)}
            aria-label="Start interactive feature tour"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-2xl text-xs font-medium bg-canvas hover:bg-surface-alt text-ink border border-hairline transition-colors shadow-sm"
          >
            <Compass className="w-3.5 h-3.5 text-ink" />
            <span>Tour 🧭</span>
          </button>
          <Badge variant="soft" className="hidden sm:flex items-center gap-1.5 text-xs text-mid-gray">
            <Database className="w-3.5 h-3.5 text-ink" />
            <span>Cloud Postgres + Redis</span>
          </Badge>
          <button
            onClick={() => setMobileOpen((o) => !o)}
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            aria-expanded={mobileOpen}
            className="md:hidden inline-flex items-center justify-center w-9 h-9 rounded-2xl text-ink hover:bg-surface-alt transition-colors"
          >
            {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile navigation panel */}
      {mobileOpen && (
        <nav
          className="md:hidden border-t border-hairline bg-paper px-4 py-2"
          aria-label="Main Navigation"
        >
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={() => setMobileOpen(false)}
                aria-label={item.label}
                className={`flex items-center gap-3 px-3 py-3 rounded-2xl text-sm font-medium transition-colors ${
                  isActive ? "bg-canvas text-ink" : "text-mid-gray hover:text-ink hover:bg-surface-alt"
                }`}
              >
                <Icon className="w-4 h-4" aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      )}
    </header>
  );
};
