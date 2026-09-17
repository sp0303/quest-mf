import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppShell } from "./app/layout/AppShell";
import { ScreenerPage } from "./pages/ScreenerPage";
import { FundDetailPage } from "./pages/FundDetailPage";
import { CalculatorPage } from "./pages/CalculatorPage";
import { BacktestPage } from "./pages/BacktestPage";
import { DataHealthPage } from "./pages/DataHealthPage";
import "./styles/globals.css";

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
        <Routes>
          <Route path="/" element={<AppShell />}>
            <Route index element={<ScreenerPage />} />
            <Route path="funds/:portfolioId" element={<FundDetailPage />} />
            <Route path="calculator" element={<CalculatorPage />} />
            <Route path="backtest" element={<BacktestPage />} />
            <Route path="health" element={<DataHealthPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
