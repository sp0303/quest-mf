# Changelog

All notable changes to the **quest-mf** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.1] - 2026-09-18

### Added
- **True ECharts Dynamic Lazy Loading (Rule 6 & Rule 5.6)**:
  - Decoupled `echarts-vendor` from the static dependency graph of `ScreenerPage` by introducing `EChartInner.tsx` loaded via `React.lazy` inside `EChart.tsx`.
  - Default route (`/`) JS download strictly reduced to ~69 kB gzip (`index.js` 13.1 kB + `react-vendor.js` 53.1 kB + `ScreenerPage.js` 3.0 kB), fully respecting the $\le 150$ kB gzip gate with zero static reference to `echarts-vendor`.
- **Security, Rate Limiting & Raw Payload Persistence (AGENTS.md §9)**:
  - Enabled standard CA-signed TLS certificate verification (`verify=True`) across all AMFI and MFAPI client requests.
  - Implemented `AsyncRateLimiter` strictly enforcing $\le 1$ req/s throttle against external endpoints.
  - Added `store_raw_payload` to persist unparsed payload bytes directly to `var/data/raw/{source}/{date}/{hash}` before parsing, and linked the relative path to `ops.ingest_log.object_key`.
- **Collision-Free Portfolio Identity**:
  - Replaced integer division `scheme_code // 10` with a database lookup/insert mapping on `(display_name, amc_id)` in `ref.portfolios`.
- **Complete SEBI Equity Category Mappings**:
  - Expanded category normalization from 8 to all 14 official SEBI equity categories (Multi Cap, Large Cap, Large & Mid Cap, Mid Cap, Small Cap, Dividend Yield, Value, Contra, Focused, Sectoral/Thematic, ELSS, Flexi Cap, Index Funds, ETFs).

## [0.3.0] - 2026-09-18

### Added
- **AMFI & MFAPI Data Ingestion Pipeline (`workers/ingestion_worker.py`)**:
  - Live daily feed parsing from `https://portal.amfiindia.com/spages/NAVAll.txt` with support for both legacy 6-column and modern 8-column formats.
  - Strict Rule Q7 & Test L canonical scheme filtering: admits only `DIRECT` plan + `GROWTH` options; filters out IDCW and Regular plans.
  - Historical NAV fetching via `https://api.mfapi.in/mf/{code}` across 10+ years of daily points.
  - Automated point-in-time reconciliation (`reconcile_amfi_vs_mfapi`) verifying discrepancy is $< 0.01\%$ (0.0001).
  - Rule 7 bulk write compliance: temporary staging table + `COPY` + `INSERT ON CONFLICT DO UPDATE` upsert pattern.
  - Audit logging of pipeline batches into `ops.ingest_log`.
  - Ingested 24,444 real daily NAV rows across 27 canonical equity schemes and 55 AMCs into Cloud PostgreSQL.
- **Frontend Bundle & DESIGN.md Token Standardization**:
  - Dedicated Rollup code-splitting for ECharts (`echarts-vendor`), reducing initial bundle to 66 KB gzip ($\le 150$ KB gate) and route chunks to $< 4$ KB gzip ($\le 80$ KB gate).
  - Centralized chart theme resolver (`frontend/src/lib/chartTheme.ts`) mapping canvas styling directly to CSS custom properties.
  - Standardized all chart components (`EChart.tsx`, `FundNavChart.tsx`, `QuadrantMatrixChart.tsx`, `BacktestEquityChart.tsx`) to `DESIGN.md` CSS variable tokens, eliminating all raw hex values.
- **Robust Walk-Forward Mark-to-Market**:
  - Enhanced `questmf_quant/backtest/walkforward.py` to gracefully maintain last observed NAV during market/partial exchange holidays, preventing spurious zero valuations.
- **Integration Test Suite**:
  - Added `backend/tests/integration/test_amfi_ingestion.py` covering AMFI feed parsing, canonical scheme guards, MFAPI threshold reconciliation, and ingest audit logging.
  - Total automated test suite now at 33/33 tests passing with 100% Ruff lint and format compliance.

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
