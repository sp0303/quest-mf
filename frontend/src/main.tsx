import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Suspense, lazy } from "react";
import { AppShell } from "./app/layout/AppShell";
import "./styles/globals.css";

const ScreenerPage = lazy(() =>
  import("./pages/ScreenerPage").then((m) => ({ default: m.ScreenerPage }))
);
const FundDetailPage = lazy(() =>
  import("./pages/FundDetailPage").then((m) => ({ default: m.FundDetailPage }))
);
const CalculatorPage = lazy(() =>
  import("./pages/CalculatorPage").then((m) => ({ default: m.CalculatorPage }))
);
const BacktestPage = lazy(() =>
  import("./pages/BacktestPage").then((m) => ({ default: m.BacktestPage }))
);
const DataHealthPage = lazy(() =>
  import("./pages/DataHealthPage").then((m) => ({ default: m.DataHealthPage }))
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 60 * 1000,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Suspense
          fallback={
            <div className="flex h-screen items-center justify-center text-xs text-mid-gray">
              Loading...
            </div>
          }
        >
          <Routes>
            <Route path="/" element={<AppShell />}>
              <Route index element={<ScreenerPage />} />
              <Route path="fund/:portfolioId" element={<FundDetailPage />} />
              <Route path="funds/:portfolioId" element={<FundDetailPage />} />
              <Route path="calculator" element={<CalculatorPage />} />
              <Route path="backtest" element={<BacktestPage />} />
              <Route path="health" element={<DataHealthPage />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);

