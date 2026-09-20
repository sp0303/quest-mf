/**
 * This file was auto-generated from OpenAPI. Do not edit directly.
 */

export interface ScreenerRow {
  portfolio_id: number;
  fund_name: string;
  amc: string;
  ret_1m: number | null;
  ret_3m: number | null;
  ret_6m: number | null;
  ret_1y: number | null;
  cagr_3y: number | null;
  shp_3m: number | null;
  peer_pct_3m: number | null;
  alpha_3m: number | null;
  ir_3y: number | null;
  mdd_3y: number | null;
  ter: number | null;
  exit_load_rate: number | null;
  exit_load_days: number | null;
  composite: number | null;
  confidence: number;
  quadrant: number | null;
  flags: number;
  investable: boolean;
  category_id: number;
  as_of_date?: string;
}

export interface MatrixItem {
  portfolio_id: number;
  fund_name: string;
  peer_pct_3m: number | null;
  shp_3m: number | null;
  quadrant: number | null;
  composite: number | null;
}

export interface FundSummary {
  portfolio_id: number;
  fund_name: string;
  amc: string;
  category_id: number;
  as_of_date: string;
  model_version: string;
  ret_1m: number | null;
  ret_3m: number | null;
  ret_6m: number | null;
  ret_1y: number | null;
  cagr_3y: number | null;
  shp_3m: number | null;
  peer_pct_3m: number | null;
  alpha_3m: number | null;
  ir_3y: number | null;
  mdd_3y: number | null;
  ter: number | null;
  exit_load_rate: number | null;
  exit_load_days: number | null;
  composite: number | null;
  confidence: number;
  quadrant: number | null;
  flags: number;
  investable: boolean;
}

export interface FundRiskMetrics {
  portfolio_id: number;
  as_of_date?: string;
  volatility_ann: number | null;
  downside_dev_ann: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  max_drawdown: number | null;
  cagr_3y?: number | null;
  observations: number;
  alpha_3m?: number | null;
  ir_3y?: number | null;
}

export interface Category {
  category_id: number;
  code: string;
  label: string;
  asset_class: string;
}

export interface NetReturnCalculation {
  initial_investment: number;
  stamp_duty: number;
  net_invested: number;
  units: number;
  gross_proceeds: number;
  exit_load: number;
  proceeds_after_load: number;
  stt: number;
  capital_gain: number;
  tax: number;
  net_proceeds: number;
  net_profit: number;
  gross_return_pct: number;
  net_return_pct: number;
}

export interface BacktestRunSummary {
  model_version: string;
  cagr_gross: number;
  cagr_net: number;
  sharpe_ratio: number;
  max_drawdown: number;
  rank_ic_mean: number;
  top_k: number;
  rebalance_months: number;
}

export interface BacktestRun {
  run_id: number;
  model_version: string;
  status: "QUEUED" | "RUNNING" | "DONE" | "FAILED" | "CANCELLED";
  progress_pct: number;
  summary: BacktestRunSummary;
  created_at: string;
  finished_at: string | null;
}

export interface BacktestSeriesResponse {
  run_id: number;
  gross: [string, number][];
  net: [string, number][];
}

export interface FundProfile {
  portfolio_id: number;
  fund_manager: string | null;
  aum_cr: number | null;
  ter_pct: number | null;
  portfolio_turnover_ratio: number | null;
  pe_ratio: number | null;
  pb_ratio: number | null;
  riskometer: string | null;
  min_sip_amount: number | null;
  updated_at?: string;
}

export interface SectorAllocationItem {
  sector: string;
  pct: number;
}

export interface HoldingItemDetail {
  isin: string | null;
  security_name: string;
  asset_type?: string;
  sector: string | null;
  pct_nav: number;
  cap_class?: "LARGE_CAP" | "MID_CAP" | "SMALL_CAP" | null;
}

export interface PortfolioHoldingsResponse {
  portfolio_id: number;
  as_of_date: string;
  disclosed_date: string | null;
  stock_count: number;
  top_10_concentration_pct: number;
  large_cap_pct: number;
  mid_cap_pct: number;
  small_cap_pct: number;
  cash_pct: number;
  sector_allocation: SectorAllocationItem[];
  top_10_holdings: HoldingItemDetail[];
  holdings: HoldingItemDetail[];
}

export interface CommonHoldingItem {
  identifier: string;
  name: string;
  weight_a: number;
  weight_b: number;
  overlap_weight: number;
  sector: string | null;
}

export interface PortfolioOverlapResponse {
  portfolio_a_id: number;
  portfolio_b_id: number;
  portfolio_a_name: string;
  portfolio_b_name: string;
  as_of_date_a: string | null;
  as_of_date_b: string | null;
  overlap_pct: number;
  common_holdings_count: number;
  fund_a_total_weight: number;
  fund_b_total_weight: number;
  unique_to_a_count: number;
  unique_to_b_count: number;
  common_holdings: CommonHoldingItem[];
}
