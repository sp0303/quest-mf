import React from "react";
import { Link, useLocation } from "react-router-dom";
import { Activity, BarChart3, Calculator, Database, Filter } from "lucide-react";
import { Badge } from "@/components/ui/Badge";

export const Topbar: React.FC = () => {
  const location = useLocation();

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

        {/* Status indicator */}
        <div className="flex items-center gap-3">
          <Badge variant="soft" className="flex items-center gap-1.5 text-xs text-mid-gray">
            <Database className="w-3.5 h-3.5 text-ink" />
            <span>Cloud Postgres + Redis</span>
          </Badge>
        </div>
      </div>
    </header>
  );
};
