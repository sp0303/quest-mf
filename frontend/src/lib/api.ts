import type {
  BacktestRun,
  BacktestSeriesResponse,
  Category,
  FundRiskMetrics,
  FundSummary,
  MatrixItem,
  NetReturnCalculation,
  ScreenerRow,
} from "./schema";

const API_BASE = "/api";

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const errorBody = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${errorBody || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  // Categories
  getCategories: () => fetchJson<Category[]>(`${API_BASE}/funds/v1/categories`),

  // Screener
  getScreener: (params?: {
    categoryId?: number;
    sort?: string;
    direction?: string;
    limit?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.categoryId) query.set("category_id", params.categoryId.toString());
    if (params?.sort) query.set("sort", params.sort);
    if (params?.direction) query.set("direction", params.direction);
    if (params?.limit) query.set("limit", params.limit.toString());
    const qs = query.toString();
    return fetchJson<ScreenerRow[]>(`${API_BASE}/screener/v1/screener${qs ? `?${qs}` : ""}`);
  },

  getMatrix: (categoryId?: number) => {
    const qs = categoryId ? `?category_id=${categoryId}` : "";
    return fetchJson<MatrixItem[]>(`${API_BASE}/screener/v1/matrix${qs}`);
  },

  // Fund Details
  getFundSummary: (portfolioId: number) =>
    fetchJson<FundSummary>(`${API_BASE}/analytics/v1/funds/${portfolioId}/summary`),

  getFundRisk: (portfolioId: number) =>
    fetchJson<FundRiskMetrics>(`${API_BASE}/analytics/v1/funds/${portfolioId}/risk`),

  getFundNavHistory: (portfolioId: number) =>
    fetchJson<{ dates: string[]; navs: number[] }>(
      `${API_BASE}/market/v1/funds/${portfolioId}/nav-history`
    ),

  // Net Return Calculator
  calculateNetReturn: (payload: {
    initial_amount: number;
    buy_nav: number;
    sell_nav: number;
    days_held: number;
    exit_load_rate?: number;
    exit_load_days?: number;
    stcg_rate?: number;
    ltcg_rate?: number;
  }) =>
    fetchJson<NetReturnCalculation>(`${API_BASE}/analytics/v1/calculator/net-return`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  // Backtests
  listRuns: () => fetchJson<BacktestRun[]>(`${API_BASE}/backtests/v1/runs`),

  getRun: (runId: number) => fetchJson<BacktestRun>(`${API_BASE}/backtests/v1/runs/${runId}`),

  getRunSeries: (runId: number) =>
    fetchJson<BacktestSeriesResponse>(`${API_BASE}/backtests/v1/runs/${runId}/series`),

  createRun: (payload: {
    model_version?: string;
    top_k?: number;
    rebalance_months?: number;
    exec_lag_days?: number;
  }) =>
    fetchJson<{ run_id: number; status: string; summary: Record<string, unknown> }>(
      `${API_BASE}/backtests/v1/runs`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }
    ),
};
