# Changelog

All notable changes to the **quest-mf** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] - 2026-09-18

### Added
- **Security & Authentication Hardening**:
  - Replaced test auth mocks with database-backed Argon2id password verification against `auth.users`.
  - Implemented asymmetric RS256 JWT generation with dynamically generated keypairs and public JWKS endpoint (`/.well-known/jwks.json`).
  - Closed guest token bypasses to ensure secure access.
- **Pure Quant Walk-Forward Backtester (`questmf_quant/backtest/walkforward.py`)**:
  - Full walk-forward simulation engine strictly adhering to Rule Q11, Test M, and Test N.
  - Periodic out-of-sample rebalancing with execution fill at $T + \text{EXEC\_LAG}$ (no same-day fills).
  - Restriction awareness: funds restricted at decision date $t$ are never bought.
  - Multi-period friction model tracking gross vs net equity curves, transaction costs, stamp duty, STT, exit load penalties, and capital gains taxes.
  - Spearman Rank Information Coefficient (IC) tracking across historical rebalance dates.
- **Batch Compute Worker (`workers/compute_worker.py`)**:
  - Standalone worker precomputing rolling returns (1M, 3M, 6M, 1Y, 3Y CAGR), annualized volatility, downside deviation, Sharpe, Sortino, max drawdown, peer percentiles, SHP, and composite scores.
  - Populates `analytics.fund_summary`, `scoring.screener_snapshot`, and updates `scoring.latest`.
- **Frontend Architecture & Rule §5 Compliance**:
  - Feature-sliced structure under `frontend/src/features/` (`screener/`, `fund-detail/`, `backtest/`).
  - Created modular ECharts wrapper (`components/charts/EChart.tsx`) using `echarts/core` with zero global bundle leakage.
  - Standardized all UI styling using `DESIGN.md` tokens (`text-ink`, `text-mid-gray`, `bg-paper`, `border-hairline`, `rounded-2xl`, `rounded-3xl`) with zero raw hex codes.
  - Refactored `ScreenerPage.tsx`, `FundDetailPage.tsx`, and `BacktestPage.tsx` into concise composition-only pages ($\le 85$ lines each).
  - Implemented route-level lazy loading (`React.lazy` + `Suspense`), reducing initial bundle to 65 KB gzip and route chunks to $< 3$ KB gzip.
  - Automated OpenAPI type generator (`scripts/gen-api.mjs`) generating `src/lib/schema.d.ts`.
  - Robust 4-state asynchronous UX (loading skeleton, empty, ErrorCard with retry, and data).
- **Extended Quant & Integration Tests**:
  - Acceptance tests for Spec v2 §28 (Tests D, E, F, G, L, P, R, and Q12 sentinel verification).
  - Full API integration test suite verifying health, categories, screener queries, precomputed risk metrics, 2x2 matrix, and walk-forward simulation lifecycle.

### Changed
- **Rule 1 & Rule 8 API Compliance**:
  - Replaced live quant calculations in `/api/analytics/v1/funds/{id}/risk` with precomputed lookups from `analytics.fund_summary` (Rule 1).
  - Replaced `SELECT *` across all analytics and screener endpoints with explicit column lists and mandatory `as_of_date` time predicates (Rule 8).

---

## [0.1.0] - 2026-09-17

### Added
- **Architecture Simplification (Modular Monolith)**:
  - Consolidated microservices into a unified FastAPI backend application on port `8000` (`backend/app/main.py`).
  - Native zero-Docker execution: directly connects to cloud PostgreSQL 16 (`140.245.194.172:5432`) and cloud Redis (`140.245.194.172:6379`).
  - Added asyncpg connection pool management with statement timeouts and graceful in-memory cache fallbacks.
- **Pure Quantitative Finance Core (`backend/libs/quant/questmf_quant`)**:
  - `calendar/windows.py`: End-of-month (EOM) clipping (`CAL_1M` ending 31 Mar resolves to 28/29 Feb), on-or-before boundary rule with staleness limits, and observation window counting (`M - N + 1`).
  - `returns.py`: Simple return, log return, CAGR (365.25-day base), active return, excess return, and Newton-Raphson XIRR solver.
  - `drawdown.py`: Max drawdown, peak/trough indices, and underwater percentage time series.
  - `downsample.py`: Largest Triangle Three Buckets (LTTB) algorithm downsampling large series to $\le 2000$ points.
  - `risk.py`: Annualized volatility, downside deviation below MAR, Sharpe ratio, Sortino ratio, tracking error, Information Ratio, CAPM Beta, Alpha, and up/down market capture.
  - `percentile.py`: Mid-rank peer percentiles with tie-handling (minimum 8 peers threshold), and Self-History Percentile (SHP) with expanding windows (zero future leakage).
  - `scoring.py`: Multi-factor composite scores (momentum, persistence, quality, risk, cost), confidence indicators, and 2×2 matrix quadrant classification (Q1–Q4).
  - `friction.py`: Full Indian mutual fund friction model: exit load, stamp duty (0.005%), STT (0.1%), and capital gains tax (post-Budget 2024: STCG 20%, LTCG 12.5%).
  - `backtest/`: Walk-forward simulation engine with $T+1$ execution lag, minimum holding periods, Spearman Rank IC, and quintile return distributions.
- **Cloud Database Tier**:
  - `schema.sql`: Full DDL script creating all 7 core schemas (`ops`, `ref`, `market`, `analytics`, `scoring`, `backtest`, `auth`).
  - `seed_sample_data.py`: Reference metadata (categories, benchmarks, AMCs) and 12 funds with 3 years of daily NAV time-series and precalculated screener snapshots.
- **API Endpoints**:
  - `/api/auth/v1`: Login, JWT token issuing (Argon2id hashing), and profile endpoints.
  - `/api/funds/v1`: Categories, AMCs, fund list, profile details, and quick search.
  - `/api/market/v1`: Downsampled NAV history, benchmark rebased overlays, and platform freshness.
  - `/api/analytics/v1`: Fund summary, risk breakdown, and interactive net-return friction calculator.
  - `/api/screener/v1`: Screener rankings, 2×2 matrix scatter points, model versions, and latest date.
  - `/api/backtests/v1`: Walk-forward simulation execution and gross vs net equity curve series.
- **Frontend Dashboard (`frontend/`)**:
  - Built with React 18, TypeScript, Vite, TanStack Query, and Tailwind CSS v4 using DESIGN.md tokens.
  - **Screener Page**: Category selector, sortable data table, and interactive 2×2 Quadrant Matrix scatter chart.
  - **Fund Detail Page**: 8-metric stat grid, interactive NAV history chart, downside risk panel, and fee/exit load breakdown.
  - **Net-Return Calculator**: Interactive duration, exit load, and tax computation.
  - **Backtest Page**: Simulation launcher and gross vs net equity curve viewer.
  - **Platform Health Page**: Real-time database and data counts monitor.
  - **Disclaimer Footer**: Complying with Rule Q16 ("Research only — not investment advice").
- **Testing & Quality**:
  - 19 automated tests (`tests/unit` and `tests/integration`) implementing Spec v2 §28 Tests A, B, C, H, I, J, K, M, N, O, Q, and Rule Q12.
  - Zero-error code formatting and linting via Ruff.
  - Clean production frontend build via Vite.
