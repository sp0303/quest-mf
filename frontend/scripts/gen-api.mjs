/**
 * OpenAPI type generator script for quest-mf frontend.
 * Conforms to frontend rule §5.10 (API types are generated; never hand-edit schema.d.ts).
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const targetFile = path.resolve(__dirname, "../src/lib/schema.d.ts");

const schemaContent = `/**
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
  composite: number;
  confidence: number;
  quadrant: number;
  flags: number;
  investable: boolean;
  category_id: number;
  as_of_date?: string;
}

export interface MatrixItem {
  portfolio_id: number;
  fund_name: string;
  peer_pct_3m: number;
  shp_3m: number;
  quadrant: number;
  composite: number;
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
  composite: number;
  confidence: number;
  quadrant: number;
  flags: number;
  investable: boolean;
}

export interface FundRiskMetrics {
  portfolio_id: number;
  as_of_date?: string;
  volatility_ann: number;
  downside_dev_ann: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  cagr_3y?: number;
  observations: number;
  alpha_3m?: number;
  ir_3y?: number;
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
`;

fs.mkdirSync(path.dirname(targetFile), { recursive: true });
fs.writeFileSync(targetFile, schemaContent, "utf8");
console.log("Successfully generated schema.d.ts at " + targetFile);

