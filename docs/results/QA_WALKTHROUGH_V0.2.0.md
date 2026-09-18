# Walkthrough: QuestMF Deep QA, Quant Core & Architecture Hardening (v0.2.0)

All components have been verified, automated tests pass cleanly (100% pass rate across 30 unit and integration tests), and code has been pushed to `main` at `commit c677fe3`.

---

## Key Achievements & Milestones

### 1. Security & Authentication Hardening
- **Real Database-Backed Auth**: Replaced dummy credentials with Argon2id password verification against table `auth.users`. Default analyst account (`analyst@questmf.local` / `Analyst@2026!`) seeded.
- **Asymmetric RS256 Tokens & JWKS**: Generated 2048-bit RSA keypair issuing RS256 JWTs with public JWKS available at `/.well-known/jwks.json`.
- **Closed Guest Bypass**: Guaranteed zero unauthenticated route leakage.

### 2. Pure Quant Core & Backtesting (`questmf_quant`)
- **Walk-Forward Simulation Engine (`questmf_quant/backtest/walkforward.py`)**:
  - Strictly adheres to **Rule Q11**, **Test M**, and **Test N**.
  - Periodic out-of-sample rebalancing with execution fill at $T + \text{EXEC\_LAG}$ (never on decision day $t$).
  - Investability checks: restricted funds at decision date $t$ are excluded from purchase.
  - Multi-period friction accounting: buy stamp duty (0.005%), sell STT (0.1%), exit loads (if held < exit_load_days), and Capital Gains Tax (STCG 20%, LTCG 12.5%).
  - Spearman Rank Information Coefficient (IC) tracking across historical rebalance periods.
- **Extended Acceptance Suite (`tests/unit/test_acceptance_extended.py`)**:
  - Implements Spec v2 §28 tests: Test D (no future leakage in rolling windows), Test E (benchmark alignment), Test F (weekend skipping without fake zeros), Test G (reproducibility), Test L (IDCW rejection from canonical series), Test P (survivorship bias prevention via merged fund inclusion), Test R (golden spreadsheet exactness), and Rule Q12 history sentinels.

### 3. Architecture Compliance (Rules 1 & 8)
- **Precompute Worker (`workers/compute_worker.py`)**:
  - Standalone batch worker calculating rolling returns (1M, 3M, 6M, 1Y, 3Y CAGR), annualized volatility, downside deviation, Sharpe, Sortino, max drawdown, mid-rank peer percentiles, and expanding SHP.
  - Precomputes and stores records in `analytics.fund_summary`, `scoring.screener_snapshot`, and updates `scoring.latest`.
- **API Cleanups**:
  - `/api/analytics/v1/funds/{id}/risk`: Serves precomputed metrics directly from `analytics.fund_summary` (Rule 1: zero computation on request path).
  - Explicit column selections and mandatory time predicates (`as_of_date = COALESCE(...)`) on all screener and matrix queries (Rule 8: no `SELECT *`).

### 4. Frontend Architecture & Rule §5 Compliance
- **Feature-Sliced Architecture (`src/features/`)**:
  - `src/features/screener/`: `ScreenerFilters`, `QuadrantMatrixChart`, `ScreenerTable`, and `useScreener` hook.
  - `src/features/fund-detail/`: `FundHeader`, `FundMetricsCard`, `FundNavChart`, and `useFundDetail` hook.
  - `src/features/backtest/`: `BacktestConfigForm`, `BacktestSummaryCard`, `BacktestEquityChart`, `BacktestRunsList`, and `useBacktest` hook.
- **Modular ECharts Wrapper (`components/charts/EChart.tsx`)**:
  - Modular imports via `echarts/core` (`LineChart`, `ScatterChart`, `GridComponent`, `TooltipComponent`, `CanvasRenderer`).
- **Design System Tokens (`DESIGN.md`)**:
  - Zero raw hex codes in component markup (`text-ink`, `text-mid-gray`, `bg-paper`, `border-hairline`, `rounded-2xl`, `rounded-3xl`).
- **Page Sizing**:
  - `ScreenerPage.tsx`: Reduced from 306 to 85 lines (pure composition).
  - `FundDetailPage.tsx`: Reduced from 285 to 53 lines (pure composition).
  - `BacktestPage.tsx`: Reduced from 178 to 68 lines (pure composition).
- **Code-Splitting & Lazy Loading**:
  - Route-level lazy loading (`React.lazy` + `<Suspense />`), reducing initial JS bundle to 65 KB gzip (budget $\le 150$ KB) and route chunks to $1.3 - 2.9$ KB gzip (budget $\le 80$ KB).
- **Automated API Type Generation**:
  - `scripts/gen-api.mjs` generates `src/lib/schema.d.ts` without hand-editing.

---

## Verification Results

| Suite | Status | Details |
|---|---|---|
| Backend Unit Tests | **PASSED** | 23 passed (`tests/unit`) |
| Backend Integration Tests | **PASSED** | 7 passed (`tests/integration`) |
| Ruff Linting | **PASSED** | `ruff check .` clean (0 errors) |
| Ruff Formatting | **PASSED** | `ruff format --check .` clean (39 files formatted) |
| Frontend Typecheck | **PASSED** | `tsc -b --noEmit` clean (0 errors) |
| Frontend Production Build | **PASSED** | Vite build clean, code-split chunks verified |
| Git Main Branch | **PUSHED** | Commit `c677fe3` pushed to `origin/main` |
