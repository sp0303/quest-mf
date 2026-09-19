# 0002. MVP Universe Scope, Calendar Engine Boundaries, and Peer Governance

* **Status**: Accepted
* **Date**: 2026-09-19
* **Deciders**: Engineering & Quant Team, Project Owner
* **Consulted**: `docs/mf_quant_screener_spec_v2.md` §6.1, §6.2, §7.1–7.3, §8.2–8.3, §13.1, §28; `AGENTS.md` §3, §4 (Rules Q1–Q16)

---

## 1. Context and Problem Statement

A thorough audit of the live platform and codebase revealed three critical deviations from the specification:

1. **Universe Contamination (violating Spec §6.1, §6.2 & §7.1)**:
   The compute worker (`backend/workers/compute_worker.py`) scored all canonical schemes regardless of asset class, defaulting unmapped schemes to `EQ_SMALL_CAP` via `COALESCE(c.code, 'EQ_SMALL_CAP')`. Consequently, ~1,000 out-of-scope instruments (ETFs, Index Funds, Debt/Liquid schemes, Fund-of-Funds, and Overseas/Taiwan/Commodity funds) entered the screener snapshot and walk-forward backtests. This contaminated peer percentile rankings and violated the platform's core research thesis.

2. **Window Boundary & Calendar Bypassing (violating Rules Q3, Q4 & Q12)**:
   The compute worker calculated rolling returns using fixed index offsets (`navs[-22]`, `navs[-65]`, etc.) instead of the pure quant calendar engine (`questmf_quant.calendar.windows.find_boundary_nav_date` and `resolve_calendar_start_date`). This ignored calendar date gaps, End-Of-Month (EOM) clipping (Test H), and staleness limits (Test I), and substituted `0.0` instead of `None` / `INSUFFICIENT_HISTORY` for truncated series.

3. **Peer Percentile Minimums & Config Versioning (violating Rules Q8 & Q13)**:
   Peer percentiles were computed without verifying the minimum peer threshold ($N \ge 8$). Furthermore, composite factor scaling was hard-coded in worker code rather than loaded from versioned configurations in `scoring.model_versions`.

4. **Multiple Canonical Schemes per Portfolio**:
   The ingestion worker hardcoded `is_canonical = true` on every ingested scheme, causing duplicate canonical rows for portfolios with multiple share classes.

---

## 2. Decision Drivers

- **Purity of Core Research Thesis**: The screener must exclusively rank active, open-ended, direct-growth Indian equity funds.
- **Strict Adherence to Rules Q1–Q16**: Non-negotiable quant correctness rules must be enforced in worker execution, not just isolated unit tests.
- **Robust Failure Modes**: Incomplete history or small peer groups must yield `None` / null, never synthetic zeros or false rankings.

---

## 3. Decision

### 3.1 Universe Scope Definition (Spec §6.1, §6.2)
- The eligible universe for MVP screener snapshots and walk-forward backtests is strictly restricted to:
  - `ref.categories.asset_class = 'EQUITY'`
  - Category code NOT IN (`'EQ_ETF'`, `'EQ_INDEX'`)
  - Excluding FoFs (Fund of Funds), International/Overseas schemes, and commodity/precious metals schemes.
  - Active open-ended portfolios (`p.closed_date IS NULL` and `s.status = 'ACTIVE'`).
  - Active point-in-time category mapping (`as_of_date BETWEEN ch.valid_from AND ch.valid_to`).
- Unmapped portfolios are dropped from the screener, **never** defaulted to `EQ_SMALL_CAP`.

### 3.2 Pure Calendar Boundary Integration (Rules Q3, Q4, Q12)
- All rolling returns (`CAL_1M`, `CAL_3M`, `CAL_6M`, `CAL_1Y`, `CAL_3Y`) must be resolved using `resolve_calendar_start_date` (with EOM clipping) and `find_boundary_nav_date` (latest date $\le$ target start within `MAX_STALENESS = 7` days).
- If no valid boundary NAV exists, return `None` (representing `INSUFFICIENT_HISTORY`). Never substitute `0.0`.
- Benchmark alpha calculations must align to the exact resolved start and end dates of the fund.

### 3.3 Peer Percentile Minimum (Rule Q8)
- For any category with fewer than 8 peer funds ($N < 8$), `peer_pct` is assigned `None`.

### 3.4 Ingestion Deduplication (Rule Q7)
- The ingestion worker will only assign `is_canonical = true` to Direct-Growth schemes.
- Database queries and ingestion will deduplicate canonical schemes per portfolio using `select_canonical_scheme` logic, ensuring exactly one canonical series per `portfolio_id`.

### 3.5 Model Versioning (Rule Q13)
- Model factor weights and parameters are loaded dynamically from `scoring.model_versions` based on the active default model version.

---

## 4. Consequences

### Positive
- **Clean Alpha & Backtests**: Eliminates commodity ETFs, Taiwan funds, and debt funds from equity peer percentiles and backtest allocation.
- **Mathematically Sound Boundaries**: Guarantees calendar integrity across leap years, month-end clipping, and trading holidays.
- **Zero-Lookahead & Full Reproducibility**: Satisfies Acceptance Tests A–R and guards against spurious data leakage.

### Neutral / Trade-offs
- The number of scored funds in `scoring.screener_snapshot` reduces from ~1,772 to ~750 cleanly classified equity funds.
- Categories with fewer than 8 funds will show null peer percentiles and null quadrants, accurately reflecting statistical significance limits.
