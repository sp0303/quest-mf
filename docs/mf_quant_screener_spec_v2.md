# MF Quant Screener — Specification v2 (Reviewed & Extended)

**Status:** Draft v2.0 — review of v1 + gap closure
**Date:** 17 September 2026
**Supersedes:** [`mf_quant_screener_spec_v1.md`](mf_quant_screener_spec_v1.md) (v1 stays in the repo for reference)
**Scope of v2:** Indian open-ended mutual funds, **equity-oriented, Direct plan, Growth option** for the MVP.

> **Disclaimer.** This is a research platform. It is not investment advice. Past performance does not guarantee future results. Tax and regulatory figures below were correct as far as we know when written. Check each one against the current official source before relying on it (see §22).

---

## Table of contents

- [Part I — Review of v1](#part-i--review-of-v1)
  - [1. Overall verdict](#1-overall-verdict)
  - [2. What v1 gets right](#2-what-v1-gets-right)
  - [3. Corrections and weak spots in v1](#3-corrections-and-weak-spots-in-v1)
  - [4. What v1 is missing (gap list)](#4-what-v1-is-missing-gap-list)
- [Part II — The v2 specification](#part-ii--the-v2-specification)
  - [5. Problem statement and hypotheses](#5-problem-statement-and-hypotheses)
  - [6. Scope, non-goals, regulatory boundary](#6-scope-non-goals-regulatory-boundary)
  - [7. Universe construction](#7-universe-construction)
  - [8. Time, dates and window definitions](#8-time-dates-and-window-definitions)
  - [9. Return definitions](#9-return-definitions)
  - [10. Rolling-window engine](#10-rolling-window-engine)
  - [11. Distribution and percentile engine](#11-distribution-and-percentile-engine)
  - [12. Benchmark layer](#12-benchmark-layer)
  - [13. Risk metrics (extended)](#13-risk-metrics-extended)
  - [14. Technical / momentum features](#14-technical--momentum-features)
  - [15. Fund-level fundamentals (new)](#15-fund-level-fundamentals-new)
  - [16. Scoring model](#16-scoring-model)
  - [17. Execution realism](#17-execution-realism)
  - [18. Friction: exit load, stamp duty, STT, tax](#18-friction-exit-load-stamp-duty-stt-tax)
  - [19. Walk-forward backtesting (extended)](#19-walk-forward-backtesting-extended)
  - [20. Statistical validity](#20-statistical-validity)
  - [21. Data model (revised)](#21-data-model-revised)
  - [22. Data sources and ingestion](#22-data-sources-and-ingestion)
  - [23. Data-quality rules (extended)](#23-data-quality-rules-extended)
  - [24. Architecture and tech stack](#24-architecture-and-tech-stack)
  - [25. Repository layout](#25-repository-layout)
  - [26. API design](#26-api-design)
  - [27. UI / dashboard](#27-ui--dashboard)
  - [28. Testing strategy and acceptance criteria](#28-testing-strategy-and-acceptance-criteria)
  - [29. Operations](#29-operations)
  - [30. Roadmap and milestones](#30-roadmap-and-milestones)
  - [31. Open decisions](#31-open-decisions)
  - [32. Git workflow: clone, commit, push](#32-git-workflow-clone-commit-push)
- [Appendix A — Formula reference](#appendix-a--formula-reference)
- [Appendix B — Glossary](#appendix-b--glossary)
- [Appendix C — Sources](#appendix-c--sources)

---

# Part I — Review of v1

## 1. Overall verdict

v1 is a **strong, well-reasoned document**. It correctly rejects "sort by latest 3M return" and replaces it with a sound research design: rolling distributions, benchmark-relative returns, own-history and peer percentiles, cost awareness, and walk-forward validation. The anti-overfitting rules (§31) and the "V1 before V2" discipline (§32–33) are exactly right.

Its gaps fall into four groups:

1. **Execution realism.** v1 does not model *when* an investor can actually transact, or how heavy the friction is for a 1–3 month rotation strategy. For an Indian equity fund held under 12 months, exit load plus short-term capital-gains tax can use up most of the edge. This is the single most important missing piece.
2. **Look-ahead in derived features.** The own-history percentile (SHP) and the category mapping can leak future information if they are built from full history.
3. **Statistical evaluation.** v1 says that overlapping windows are not independent, but it does not say *how* to evaluate correctly. It needs rank IC, HAC or bootstrap errors, and multiple-testing control.
4. **Universe mechanics.** v1 does not cover the Oct-2017 SEBI re-categorisation, the Direct-plan history that only starts in 2013, Direct/Regular duplicates, IDCW distortion, subscription restrictions, or side-pocketing.

## 2. What v1 gets right

| v1 section | Why it is good |
|---|---|
| §2, §24 — `CAL_3M` vs `CAL_90D` vs `OBS_90` | Removes a real source of bugs by naming each window type explicitly. |
| §5, §26 — window count `M − N + 1` | Corrects the "90-day window = 90 windows" misconception. |
| §6 — overlap ≠ independence | Correct, and often ignored. |
| §8–9 — SHP vs CP | Two different questions, kept separate. |
| §10 — TRI benchmarks | Matches SEBI's requirement. Price-return indices would overstate alpha by roughly the dividend yield. |
| §13 — 2×2 matrix | Keeps information visible instead of collapsing it into one score too early. |
| §15 — path, not just endpoint | Captures the investor's experience, not just the endpoint return. |
| §17 — do not subtract TER twice | A correct and commonly missed point. |
| §19 — tax kept out of the fund score | Correct separation of concerns. |
| §31 — anti-overfitting rules | Correct and necessary. |
| §35 — `INSUFFICIENT_HISTORY` instead of zero | Correct handling of missing data. |

## 3. Corrections and weak spots in v1

### 3.1 §3 "Window B / Window C" is muddled
The two example lines are nearly identical and hard to read. v2 replaces them with one precise boundary rule (§8.3).

### 3.2 No concrete boundary rule
v1 says repeatedly "use the project-defined boundary rule" but never defines one. v2 defines it (§8.3): **previous available NAV on or before the target date, with a maximum staleness tolerance**.

### 3.3 Calendar month arithmetic is not specified
`31 May − 3M` has no 31 Feb. v2 specifies **end-of-month clipping** (`31 May − 3M → 28/29 Feb`). The recommended way to get this is `pandas.DateOffset(months=3)` / `dateutil.relativedelta`.

### 3.4 SHP can leak future data
The SHP at date `t` in a backtest must use **only rolling returns that ended on or before `t`** (an expanding window). If it is computed over the full history, every backtest that uses SHP is contaminated. v1's Test D ("no future leakage") covers this in principle, but the feature is not specified that way. v2 fixes this (§11.2).

### 3.5 Minimum history is too thin for SHP
v1 suggests "3M model → 1 year minimum". One year of history holds only about **4 non-overlapping 3M windows**, so a percentile computed from it is mostly noise. v2 requires **3 years** for a "full-confidence" SHP and adds an explicit `effective_n` confidence field (§11.3).

### 3.6 Momentum vs mean reversion is assumed, not tested
v1 implicitly treats high current strength as good. The academic evidence on mutual-fund performance persistence is weak outside the losers' tail (Carhart 1997 and later work). The Indian evidence is mixed. A high SHP could just as well predict **mean reversion**. v2 states both as competing hypotheses (§5.2) and evaluates the sign of the signal empirically. v2 does not assume it.

### 3.7 Momentum acceleration mixes compounding conventions
`R_1M − R_3M/3` is fine as an exploratory feature, but it divides a compounded return linearly. v2 uses log returns: `r_1M − r_3M/3` with `r = ln(1+R)` (§14).

### 3.8 The composite weights appear twice with different numbers
§12 uses 30/35/25/10. §32 uses 25/35/15/15/10. v2 keeps **one** baseline (§16) and treats all weights as versioned config.

### 3.9 Sortino without a defined MAR
Downside deviation needs a minimum acceptable return (0, or the risk-free rate). v2 defines MAR = daily risk-free rate (§13).

### 3.10 The rolling pseudocode is O(dates × horizons) Python loops
It is correct but slow for about 1,500 schemes × 20 years × 8 window types. v2 specifies a vectorised implementation (§10.4).

### 3.11 Plan dual-stack before MVP need
v1's architecture shows PostgreSQL *and* DuckDB. §39 already says that DuckDB + Parquet is enough for the MVP, and v2 makes that the default.

## 4. What v1 is missing (gap list)

Ranked by impact.

| # | Gap | Why it matters | v2 section |
|---|---|---|---|
| G1 | **Friction realism for short horizons** — exit load (typically 1% under 12 months for equity), STCG tax, stamp duty, STT | A monthly or quarterly rotation strategy can have a positive gross edge and a negative net edge. The backtest must report both. | §18, §19.5 |
| G2 | **NAV applicability timing / signal lag** | NAV(t) is published in the evening of `t`. You cannot trade at NAV(t) using a signal computed from NAV(t). The earliest realistic entry is NAV(t+1). | §17 |
| G3 | **Point-in-time SHP and categories** | Prevents look-ahead bias. | §7.3, §11.2 |
| G4 | **SEBI re-categorisation (Oct 2017 circular, effective 2018)** | Categories before 2018 do not match today's. Peer groups before that date need a mapping or must be excluded. | §7.3 |
| G5 | **Direct plans only exist from 1 Jan 2013** | Direct-plan history is at most about 13 years. Before 2013 a Regular-plan proxy is needed, with a TER adjustment flag. | §7.2 |
| G6 | **Direct/Regular and Growth/IDCW duplicates** | They share one portfolio. Counting both inflates peer groups and distorts percentiles. | §7.2 |
| G7 | **IDCW NAV drops on payouts** | Returns based on raw IDCW NAV are wrong. Use Growth only, or adjust for payouts. | §7.2 |
| G8 | **Subscription restrictions** | Some small-cap funds have restricted or suspended lump-sum inflows. A top-ranked fund may not be investable. | §7.4 |
| G9 | **Evaluation statistics** — rank IC, HAC/Newey-West, block bootstrap, deflated Sharpe, multiple testing | Without these, walk-forward "wins" may be noise. | §20 |
| G10 | **Missing risk metrics** — beta, tracking error, information ratio, up/down capture, Sharpe, Calmar | These are standard, and they are needed to understand where alpha comes from. | §13 |
| G11 | **Risk-free rate series** | Needed for Sharpe, Sortino and excess returns. | §12.4, §22 |
| G12 | **Fund fundamentals** — AUM, fund-manager changes, portfolio holdings, style drift, cash levels | Momentum driven by a manager who has since left is not persistent. | §15 |
| G13 | **Category vs fund-selection decomposition** | Tells us whether the "edge" is really category rotation (small-cap beta) or fund selection. | §19.4 |
| G14 | **Regulatory boundary** — publishing ranked recommendations may fall under SEBI Research Analyst / Investment Adviser regulations | This is a legal risk once the tool is shared beyond the team. | §6.3 |
| G15 | **Debt, liquid and index funds need different treatment** | Momentum on an overnight fund means nothing. Index funds should be scored on tracking error, not alpha. | §6.1, §7.1 |
| G16 | **Side-pocketing, wind-ups, NAV restatements** (for example, the 2020 Franklin Templeton debt-scheme wind-up) | Affects survivorship and return integrity. | §7.5, §23 |
| G17 | **SIP / XIRR view** | Most Indian retail money arrives through SIPs. A lump-sum-only view misses how most investors actually experience a fund. | §9.4 |
| G18 | **Market regime conditioning** | A signal may only work in some regimes. Report results by regime. | §19.6 |
| G19 | **Percentile method definition** (ties, interpolation, min peer count) | Needed for reproducibility. | §11.1 |
| G20 | **Ops**: schedule, AMFI publish timing, idempotent re-runs, monitoring | Needed for production readiness. | §29 |
| G21 | **Repo structure, tooling, CI, git workflow** | The team needs a concrete starting point. | §25, §32 |

---

# Part II — The v2 specification

## 5. Problem statement and hypotheses

### 5.1 Core question
> Among eligible, **investable** funds today, which combine strong current behaviour with historically persistent, benchmark-relative, risk-acceptable performance? **After realistic timing and friction**, does ranking by this evidence add out-of-sample value over holding the category benchmark or an equal-weight category basket?

### 5.2 Explicit, falsifiable hypotheses

| ID | Hypothesis | Test |
|---|---|---|
| H1 | Peer-relative 3M/6M momentum predicts next-3M peer-relative return (positive rank IC). | Rank IC across walk-forward dates, HAC t-stat (§20). |
| H2 | Persistence (rolling benchmark-beat %) predicts next-3M active return. | Same. |
| H3 | A high SHP predicts **lower** subsequent return (mean reversion). | Sign and significance of the SHP IC. |
| H4 | The composite beats the equal-weight category basket **net of friction** at a ≥6M holding period. | Net long-only top-quintile vs basket (§19.5). |
| H5 | Any edge comes from fund selection, not category timing. | Within-category vs cross-category decomposition (§19.4). |

H3 is the reason v2 does not hard-code "high SHP = good".

## 6. Scope, non-goals, regulatory boundary

### 6.1 MVP scope
- Open-ended **equity-oriented** schemes: Large, Mid, Small, Large & Mid, Multi, Flexi, Focused, Value/Contra, ELSS, Sectoral/Thematic (sectoral funds ranked only within their own theme).
- **Direct plan, Growth option** as the canonical series.
- Horizons: 1M, 3M, 6M, 1Y for state; 3Y, 5Y as quality priors.

### 6.2 Out of scope for MVP
- Debt / liquid / money-market funds. These need YTM, duration and credit metrics, not momentum.
- Index funds and ETFs. These need a separate tracking-error screener.
- FoFs, international funds (currency and overseas limits), hybrids (phase 2).
- Machine learning models (phase 8+).
- Order placement or any brokerage integration.

### 6.3 Regulatory boundary
- Internal research use only until legal review. In India, publishing buy/sell recommendations or personalised advice can require registration under SEBI (Research Analysts) or (Investment Advisers) Regulations.
- UI copy must describe **evidence** ("ranked 94th percentile vs peers on 3M"), not **advice** ("buy this").
- Every page carries the standard mutual-fund risk disclaimer.

## 7. Universe construction

### 7.1 Eligibility (point-in-time)
A scheme is eligible on date `t` if:
- it is open-ended, equity-oriented, and not an index fund or ETF (as classified **at `t`**);
- it had a NAV within the last 5 business days before `t`;
- it has at least the minimum history required by the feature (§11.3);
- it had AUM ≥ ₹100 cr at the last disclosure on or before `t` (configurable). This filters out tiny, noisy schemes.

### 7.2 One canonical series per portfolio
- Group share classes by an internal `portfolio_id`. Direct and Regular plans, and Growth and IDCW options, of the same scheme share one portfolio.
- The canonical series is **Direct-Growth**. Before 1 Jan 2013 (when Direct plans started), use **Regular-Growth** as a proxy and set `is_proxy_series = true`. Optionally add back the TER difference as a documented adjustment, off by default.
- Never compute returns from raw IDCW NAV.
- Peer percentiles count **one row per `portfolio_id`**.

### 7.3 Point-in-time categories
- Store `category_history(portfolio_id, effective_from, effective_to, sebi_category)`.
- SEBI's categorisation and rationalisation circular (October 2017, implemented in 2018) reshaped categories. Before that date, either:
  - (a) map legacy categories to current ones using a curated mapping table with a `mapping_confidence` field, or
  - (b) start peer-based backtests from mid-2018.
- **MVP default:** option (b) for peer percentiles. Pre-2018 data is still used for the fund's own rolling distributions.

### 7.4 Investability
- Store `subscription_status_history` (open / lump-sum restricted / SIP-only / suspended).
- The screener shows restricted funds with a badge.
- The backtester **cannot buy** a fund that is restricted at the decision date.

### 7.5 Corporate actions and events
- Mergers, renames, category changes, benchmark changes, manager changes, segregated portfolios (side pockets) and wind-ups are recorded in `scheme_events`.
- Merged-out schemes stay in historical universes (no survivorship bias). Their last NAV marks their exit.

## 8. Time, dates and window definitions

### 8.1 Calendars
- `nav_calendar(scheme)` = the dates on which that scheme actually has a NAV.
- `trading_calendar` = NSE trading days, used for gap detection only.
- All dates are stored as `DATE` in IST. There are no timestamps in calculations.

### 8.2 Window identifiers (from v1, kept)

| ID | Meaning |
|---|---|
| `CAL_1M`, `CAL_3M`, `CAL_6M`, `CAL_1Y`, `CAL_3Y`, `CAL_5Y` | Calendar-month offsets with end-of-month clipping |
| `CAL_30D`, `CAL_90D`, `CAL_182D`, `CAL_365D` | Fixed calendar-day offsets |
| `OBS_21`, `OBS_63`, `OBS_126`, `OBS_252` | N valid NAV observations, inclusive |

### 8.3 Boundary rule (normative)
For the calendar windows (`CAL_*`) ending at a valid NAV date `t`:

```text
target_start = t − offset                  # EOM-clipped for month offsets
start_date   = max{ d ∈ nav_calendar : d ≤ target_start }
valid if  (target_start − start_date) ≤ MAX_STALENESS (default 7 calendar days)
```

- **On or before** is used, never after. This keeps the window at least as long as nominal, and it never peeks forward.
- The benchmark uses **the same `start_date` and `t`** (§12.2). If the benchmark has no value on one of those dates, use its previous value, subject to the same staleness rule.
- For `OBS_N` windows: `start_index = end_index − (N − 1)`.

### 8.4 End-date stepping
The primary series uses **one window per valid NAV date** (v1 §23). The calendar-day view is for presentation only.

## 9. Return definitions

### 9.1 Simple and log returns
```text
R_H(t) = NAV(t) / NAV(start) − 1
r_H(t) = ln(NAV(t) / NAV(start))
```
Store `R` for display. Use `r` for aggregation, averaging and the acceleration feature.

### 9.2 Annualisation
- Horizons ≤ 1Y: never annualise for display.
- Horizons > 1Y: `CAGR = (1 + R)^(365.25 / days) − 1`, where `days` is the actual calendar days between `start` and `t`.

### 9.3 Excess return over risk-free
`R_excess = R_H − Rf_H`, where `Rf_H` is compounded from the daily risk-free series (§12.4).

### 9.4 SIP / XIRR view (new)
For each fund and each rolling 1Y/3Y/5Y window, simulate a monthly SIP (same day each month, next valid NAV) and compute **XIRR**. Store the rolling SIP-XIRR distribution alongside the lump-sum distribution. Display only; not in the V1 score.

## 10. Rolling-window engine

### 10.1 Outputs per `(portfolio_id, end_date, window_id)`
`start_date, n_obs, ret, log_ret, bench_ret, active_ret, excess_ret, max_dd, vol_ann, downside_dev_ann, worst_day, best_day, neg_day_pct, beta, tracking_error, staleness_days`

### 10.2 Daily return series
`d_t = NAV_t / NAV_prev − 1`, where `prev` is the previous valid NAV. **No forward-fill.** If the gap exceeds `MAX_GAP` (default 7 calendar days), the return is flagged and any window containing it is marked `has_gap = true`.

### 10.3 Annualisation of volatility
`vol_ann = std(d) × sqrt(252)` using observation-based scaling, documented as such.

### 10.4 Vectorised implementation (normative guidance)
```python
import pandas as pd

def rolling_calendar_returns(nav: pd.Series, months: int, max_stale_days: int = 7) -> pd.DataFrame:
    """nav: DatetimeIndex (valid NAV dates only), sorted, unique."""
    ends = nav.index
    targets = ends - pd.DateOffset(months=months)          # EOM clipping built in
    left = pd.DataFrame({"end": ends, "target": targets}).sort_values("target")
    right = pd.DataFrame({"start": ends, "start_nav": nav.values})
    m = pd.merge_asof(left, right, left_on="target", right_on="start",
                      direction="backward")                  # on-or-before rule
    m["stale"] = (m["target"] - m["start"]).dt.days
    m = m[(m["stale"] <= max_stale_days) & m["start"].notna()]
    m["end_nav"] = nav.reindex(m["end"]).values
    m["ret"] = m["end_nav"] / m["start_nav"] - 1
    return m.set_index("end").sort_index()
```
- Rolling drawdown inside a window: for `OBS_N`, use a rolling max; for `CAL_*`, use a numba kernel keyed on start/end indices.
- Use **Polars or DuckDB** for the cross-fund fan-out. Partition Parquet output by `window_id/year`.
- Target: the full universe × all windows recomputes in under 10 minutes on a laptop. The daily incremental run recomputes only new end dates.

## 11. Distribution and percentile engine

### 11.1 Percentile definition (normative)
- `percentile_rank(x, S) = 100 × (count(s < x) + 0.5 × count(s == x)) / |S|` (mid-rank; ties handled).
- **Peer percentile** requires `|peers| ≥ 8` on that date. Otherwise it is `null` with `reason = SMALL_PEER_GROUP`.
- Higher is better for returns. For costs and drawdown magnitude, invert explicitly (`100 − pct`) and name the result (`ter_pct_inv`).

### 11.2 Point-in-time distributions
`rolling_distribution_features(portfolio_id, as_of_date, window_id, …)` uses **only windows with `end_date ≤ as_of_date`**. Two variants:
- `EXPANDING`: all history up to `as_of_date` (default).
- `TRAILING_KY`: the last K years only (sensitivity check; K = 5).

**SHP(t)** = percentile of `ret(t)` among `{ret(s) : s < t}` for that window. The current value is excluded from its own reference set.

### 11.3 Confidence
```text
effective_n = history_days / window_days      # ≈ non-overlapping windows
```

| effective_n | Label | Used in score? |
|---|---|---|
| < 4 | `INSUFFICIENT_HISTORY` | No |
| 4–11 | `LOW_CONFIDENCE` | Yes, shrunk toward 50 |
| ≥ 12 | `OK` | Yes |

Shrinkage: `shp_adj = 50 + (shp − 50) × min(1, effective_n / 12)`.

This means a 3M SHP needs about 3 years of history for full confidence.

### 11.4 Stored statistics
From v1: mean, median, std, min, max, P10/P25/P50/P75/P90, positive %.
Added: `benchmark_beat_pct`, `median_active`, `p10_active`, `median_max_dd`, `p90_max_dd_magnitude`, `effective_n`, `confidence`.

## 12. Benchmark layer

### 12.1 Mapping
- `benchmark_history(portfolio_id, effective_from, effective_to, benchmark_id, tier)`. SEBI introduced two-tier benchmarking in 2021, so schemes may have changed benchmarks over time.
- **Always use the TRI variant.** If only a price-return index is available, flag it as `bench_is_pri = true` and exclude the fund from alpha-based scoring.

### 12.2 Alignment
Fund and benchmark returns use **identical `start_date` and `end_date`** (acceptance test E).

### 12.3 Category benchmark
Separately from the scheme's own benchmark, each category has a **reference TRI** (for example, Nifty Smallcap 250 TRI for small-cap). It is used for category-level comparison and for the backtest baseline.

### 12.4 Risk-free rate
91-day T-bill yield (RBI) or an overnight rate (MIBOR / TREPS). Convert to a daily rate: `(1 + y)^(1/365) − 1`, applied per calendar day between NAV dates.

## 13. Risk metrics (extended)

| Metric | Definition | Notes |
|---|---|---|
| Volatility | `std(d) × √252` | |
| Downside deviation | `√(mean(min(d − MAR, 0)²)) × √252`, MAR = daily Rf | v1 left MAR undefined |
| Max drawdown | v1 §16 | per window and full history |
| Recovery time | Days from trough back to the prior peak | `null` if not yet recovered |
| **Sharpe** | `ann_excess / vol` | new |
| **Sortino** | `ann_excess / downside_dev` | new |
| **Calmar** | `CAGR / |MDD|` over 3Y | new |
| **Beta** | `cov(d_f, d_b) / var(d_b)` | new; from daily data over 1Y |
| **Tracking error** | `std(d_f − d_b) × √252` | new |
| **Information ratio** | `ann_active / TE` | new; the best single "skill" metric |
| **Up / down capture** | Mean fund return ÷ mean benchmark return on up / down benchmark months | new |
| Worst / best day, neg-day % | v1 §15 | |

## 14. Technical / momentum features

Phase 7 only, and only after the baseline is validated (as v1 requires).

| Feature | Definition |
|---|---|
| RSI(14) | Wilder smoothing on NAV |
| SMA 20/50/200 state | `NAV > SMA`, `SMA20 > SMA50`, `SMA50 > SMA200` |
| Distance from SMA | `NAV / SMA − 1` |
| ROC | `NAV(t) / NAV(t − N obs) − 1` |
| **Momentum acceleration** | `r_1M − r_3M / 3` (log returns) |
| **Relative-strength trend** | slope of `ln(NAV / bench)` over 63 obs, from OLS |
| **Momentum 12-1** | `r_12M − r_1M` (skip-month momentum, a standard definition) |
| Vol regime | `vol_63 / vol_252` |

Note: MF NAVs are smoothed daily portfolio values. They are not traded prices. Price-pattern indicators have weaker grounds than they do for stocks, which is why feature ablation (v1 §33) is mandatory.

## 15. Fund-level fundamentals (new)

| Data | Source | Use |
|---|---|---|
| AUM (monthly) | AMFI / AMC disclosures | Eligibility, capacity flag (for example, a small-cap fund AUM above a threshold) |
| Fund-manager history | SID/KIM and AMC notices | `manager_tenure_days`; **reset or down-weight persistence** when the manager changed within the window |
| Monthly portfolio holdings | AMC monthly portfolio disclosures | Cash %, top-10 concentration, market-cap mix → **style-drift** check against category |
| Portfolio turnover | Factsheets | Friction proxy |
| Riskometer history | Monthly disclosures | Display |

MVP: AUM and manager tenure only. Holdings-based features come in phase 2.

## 16. Scoring model

### 16.1 Normalisation
1. For each raw feature, compute a **within-category, point-in-time percentile** (0–100).
2. Invert the "lower is better" features.
3. Component score = mean of its feature percentiles, ignoring nulls. If more than 50% of a component's features are null, the component is null.
4. Composite = weighted mean of the non-null components, with weights renormalised. If more than one component is null, the composite is null and the fund is labelled `INCOMPLETE`.

### 16.2 V1 baseline (single source of truth)

| Component | Weight | Features |
|---|---|---|
| Momentum | 25% | peer pct of 1M, 3M, 6M returns |
| Persistence | 35% | 3M & 1Y benchmark-beat %, 3M median active, IR (3Y) |
| Long-term quality | 15% | peer pct of 3Y, 5Y CAGR |
| Risk | 15% | peer pct (inv) of 3Y MDD, downside dev, beta |
| Cost | 10% | peer pct (inv) of TER; exit-load days |

**SHP is not in the composite in V1.** Its sign is unknown (H3), so it is shown as a separate diagnostic axis (the 2×2 matrix) until backtesting settles it.

### 16.3 Versioning
Weights, feature lists and thresholds live in `config/models/<model_version>.yaml`. Every score row stores `model_version` and `data_snapshot_id`. Same inputs + same version = same output (test G).

### 16.4 Output labels
Besides the number: `confidence`, `matrix_quadrant`, `investability`, and `flags[]` (manager change, style drift, proxy series, small peer group, restricted).

## 17. Execution realism

### 17.1 Signal timing
- AMFI NAVs for day `t` are generally published late in the evening of `t`.
- A signal computed from NAV(t) can therefore act **no earlier than day t+1**.
- **Normative backtest rule:** decision on `t` → purchase at **NAV(t+1)**. That assumes the order is placed on t+1 before the cut-off and the money is realised the same day. The lag is configurable (`EXEC_LAG_DAYS = 1`; sensitivity 2).

### 17.2 Cut-off and money realisation
For purchases, the applicable NAV depends on when the money reaches the AMC relative to the 3 PM cut-off (SEBI rules effective 2021). Redemption NAV is the NAV of the request day if it is made before the cut-off. Proceeds arrive a few business days later, so a switch **cannot** buy the new fund on the same NAV date. Model a sell → buy gap: `SWITCH_GAP_DAYS`, default 2 business days.

### 17.3 Rebalancing frequencies to test
Monthly, quarterly, semi-annual, annual. v2 expects friction to make **monthly** rotation uneconomic (see §18).

## 18. Friction: exit load, stamp duty, STT, tax

> These rates are as understood at the time of writing (Budget 2024 rules). They must be stored as **dated config**, and verified against current Income Tax / SEBI notifications before use.

| Item | Typical value (equity funds) | Modelled as |
|---|---|---|
| Exit load | Often 1% if redeemed within 12 months (scheme-specific; some use 7/30/90/365 days) | Point-in-time `load_rules` |
| Stamp duty | 0.005% on purchase / switch-in amount (since 1 Jul 2020) | Deducted at buy |
| STT | 0.001% on redemption of equity-oriented units | Deducted at sell |
| STCG (held ≤ 12 months) | 20% on gains (sales on/after 23 Jul 2024) | Investor module |
| LTCG (held > 12 months) | 12.5% on gains above ₹1.25 lakh per FY | Investor module |
| TER | Already inside NAV — **do not deduct** | Comparison only |

### 18.1 Break-even intuition (why this matters)
A quarterly rotation into a fund that gains 5% in the quarter, then exits:

```text
gross gain              5.00%
exit load (1% of value) −1.05%
STCG 20% on ~3.95%      −0.79%
stamp + STT             −0.01%
net                     ≈ 3.15%   → about 37% of the gross gain lost to friction
```

A rotation strategy must beat buy-and-hold **after** this. The backtester therefore reports gross, net-of-load and net-of-tax results side by side (§19.5).

### 18.2 Friction-aware rule option
`MIN_HOLD_DAYS = exit_load_days` (switch only after the load-free period) is a parameter in the backtest. It is expected to be the dominant setting.

## 19. Walk-forward backtesting (extended)

### 19.1 Protocol
```text
for each decision date d in schedule (e.g., month-ends):
    universe_d   = eligible & investable funds as of d        # point-in-time
    features_d   = computed from data with date ≤ d
    scores_d     = model(features_d, model_version)
    portfolio_d  = select(scores_d)                           # top-k / top-quintile per category
    execute at NAV(d + EXEC_LAG) respecting SWITCH_GAP, MIN_HOLD
    measure forward returns over 1M, 3M, 6M, 12M (gross & net)
```

### 19.2 Data split
- **Development:** 2013 (Direct start) → 2020
- **Validation:** 2021 → 2023 (used for model selection)
- **Hold-out:** 2024 → present. **Touched once**, at the end, and the result is recorded in `docs/results/` even if it is bad.
- Report results separately for the pre-2018 (proxy categories) and post-2018 periods.

### 19.3 Baselines (all must be reported)
1. Category reference TRI
2. Equal-weight all eligible funds in the category
3. Random top-k (1,000 draws) → gives the null distribution
4. Largest-AUM fund(s) in the category (the "default investor" choice)
5. Pure 1Y trailing-return ranking (the naive screener)

### 19.4 Decomposition (H5)
- **Within-category:** long top-quintile vs equal-weight of the *same* category → selection skill.
- **Cross-category:** category-level scores → timing skill. Report these separately.

### 19.5 Reported metrics
v1's list plus: **rank IC** (Spearman of score vs forward return, per date), IC mean / std / t-stat, IC hit rate, top-minus-bottom quintile spread, turnover per year, **gross vs net** (load, stamp, STT, and a flat 20% STCG / 12.5% LTCG investor), CAGR, vol, Sharpe, MDD, IR vs category TRI.

### 19.6 Regime breakdown
Tag each decision date by market regime, using the category TRI:
- trend: 200-day SMA slope sign
- volatility: 63-day vol percentile
Report IC and net excess return per regime.

## 20. Statistical validity

| Issue | Remedy |
|---|---|
| Overlapping forward windows (3M forward on monthly dates) | **Newey-West HAC** standard errors with lag = horizon − 1 in rebalance periods, or evaluate on non-overlapping dates as a check |
| Cross-sectional correlation within a date | Fama-MacBeth style: compute IC per date, then test the time series of ICs |
| Small samples | **Stationary block bootstrap** of the IC series (block ≈ 6 months) for confidence intervals |
| Many variants tried | Log **every** configuration tried in `experiments/registry.csv`; apply the **Deflated Sharpe Ratio** / White's Reality Check (or Hansen SPA) before accepting a winner |
| Hold-out reuse | The hold-out is used once, and that use is logged |
| Effect size | Require IC ≥ 0.03 **and** net excess > 0 across at least 2 of 3 sub-periods before a feature is accepted |

## 21. Data model (revised)

Storage: Parquet on disk (partitioned), queried with DuckDB. Names shown as `table(columns)`; the ★ marks new tables or columns in v2.

```text
schemes(scheme_code PK, isin, portfolio_id★, fund_name, amc, plan, option,
        inception_date, status, is_canonical★)

portfolios★(portfolio_id PK, display_name, amc, launch_date, closed_date, close_reason)

category_history★(portfolio_id, effective_from, effective_to, sebi_category,
                  source, mapping_confidence)

benchmark_history★(portfolio_id, effective_from, effective_to, benchmark_id, tier, source)

subscription_status_history★(portfolio_id, effective_from, effective_to, status, note, source_url)

scheme_events★(portfolio_id, event_date, event_type, details_json, source_url)
     -- MERGER | RENAME | CATEGORY_CHANGE | BENCHMARK_CHANGE | MANAGER_CHANGE
     -- | SEGREGATION | WIND_UP | NAV_RESTATEMENT

manager_history★(portfolio_id, manager_name, from_date, to_date, source_url)

nav_history(scheme_code, nav_date, nav, source, retrieved_at, raw_hash)
     PK (scheme_code, nav_date)

benchmark_values(benchmark_id, value_date, tri_value, is_tri★, source, retrieved_at)

risk_free_rates★(rate_date, series_id, annual_yield, source)

aum_history★(portfolio_id, month_end, aum_cr, source)

ter_history(scheme_code, effective_date, ter, base_ter, gst, other, source)

load_rules(scheme_code, effective_from, effective_to, exit_load_rate,
           exit_load_days, rule_text, source_url)

tax_rules★(asset_class, effective_from, effective_to, stcg_rate, ltcg_rate,
           ltcg_exemption, holding_days_for_lt, stamp_duty_rate, stt_rate, source_url)

rolling_metrics(portfolio_id, end_date, window_id, start_date, n_obs, ret, log_ret,
                bench_ret, active_ret, excess_ret, max_dd, vol_ann, downside_dev_ann,
                beta★, tracking_error★, worst_day, best_day, neg_day_pct,
                has_gap★, staleness_days★)

rolling_distribution_features(portfolio_id, as_of_date, window_id, variant★,
                mean, median, std, min, max, p10, p25, p50, p75, p90,
                positive_pct, benchmark_beat_pct, median_active, p10_active★,
                median_max_dd★, effective_n★, confidence★)

daily_features(portfolio_id, feature_date, ret_1m, ret_3m, ret_6m, ret_1y,
               cagr_3y, cagr_5y, shp_3m★, peer_pct_3m★, sharpe_1y★, sortino_1y★,
               ir_3y★, rsi14, sma20, sma50, sma200, mom_accel, mom_12_1★, rs_slope★)

scores(portfolio_id, as_of_date, model_version, data_snapshot_id★,
       momentum, persistence, lt_quality★, risk, cost, composite,
       confidence★, matrix_quadrant★, flags★)

backtest_runs★(run_id, model_version, config_json, started_at, git_sha, data_snapshot_id)
backtest_results★(run_id, decision_date, portfolio_id, weight, fwd_ret_1m, fwd_ret_3m,
                  fwd_ret_net_3m, …)
```

`raw_ingest/` keeps every downloaded payload unchanged, keyed by `raw_hash`, so that any calculation can be rebuilt (v1 §38).

## 22. Data sources and ingestion

| Priority | Data | Source | Notes |
|---|---|---|---|
| 1 | Daily NAV (latest) | AMFI `NAVAll.txt` | Semicolon-delimited; scheme code, ISINs, name, NAV, date |
| 1 | Historical NAV | AMFI NAV history download | Pull in **date-range chunks**; retry with backoff; be polite (rate-limit) |
| 1 | TER | AMFI TER page | Monthly snapshots; keep history |
| 1 | AUM | AMFI monthly / quarterly AUM disclosures | |
| 2 | Scheme docs, loads, benchmark, category | SEBI MF filings (SID/KIM), AMC notices | Largely manual or semi-automated; store `source_url` |
| 2 | Benchmark TRI | NSE Indices (niftyindices.com) historical TRI; BSE (asiaindex) for S&P BSE / BSE indices | Check the terms of use / licensing before redistributing |
| 2 | Risk-free | RBI DBIE (T-bill yields) / FBIL | |
| 3 | Convenience | MFAPI.in (`/mf/{code}`) | Cache and recovery only; reconcile against AMFI |
| 3 | Holdings | AMC monthly portfolio files | Phase 2 |

Rules:
- The scraper follows each site's terms of use. Cache aggressively and never hammer endpoints.
- Every row keeps `source`, `source_url`, `retrieved_at`, `raw_hash`, `parser_version`.
- **Reconciliation job:** for a random sample of 50 schemes a week, compare AMFI and MFAPI NAVs. If the difference is above 0.01%, raise an alert.

## 23. Data-quality rules (extended)

All of v1 §37, plus:

| Check | Action |
|---|---|
| One-day move > 10% (equity) | Flag; hold out of features until reviewed or confirmed by a second source |
| NAV restated (same date, new value) | Keep both versions, use the latest, log a `NAV_RESTATEMENT` event |
| Scheme has no NAV for > 10 business days while `status = active` | Alert |
| IDCW option used as a canonical series | Hard fail |
| Benchmark is PRI, not TRI | Flag `bench_is_pri` |
| Category missing at date `t` | Exclude from peer ranking at `t` |
| Direct NAV < Regular NAV for the same portfolio (normally Direct ≥ Regular) | Flag possible mapping error |
| Sudden NAV drop matching a segregation event | Link to the `SEGREGATION` event; exclude the window from distributions |

Great Expectations or pandera schemas run in CI and after every ingestion.

## 24. Architecture and tech stack

```text
 AMFI ─┐   SEBI/AMC ─┐   NSE/BSE TRI ─┐   RBI ─┐   MFAPI ─┐
       └──────────────┴───────────────┴────────┴──────────┘
                              │
                     ingest/ (httpx, retries, raw cache)
                              │
                     validate/ (pandera)  ──► alerts
                              │
                 Parquet lake (raw → clean → features)
                              │  DuckDB / Polars
        ┌─────────────────────┼──────────────────────┐
   rolling engine      distribution / pct      risk & tech
        └─────────────────────┼──────────────────────┘
                              │
                  scoring (versioned YAML models)
                              │
               backtester (walk-forward, friction)
                              │
                     FastAPI (read-only)
                              │
            React + TypeScript + (ECharts / Recharts)
```

| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.12 | Ecosystem |
| Env / deps | `uv` + `pyproject.toml` | Fast, reproducible |
| Dataframes | Polars (+ pandas where needed) | Speed |
| Storage / query | Parquet + DuckDB | Zero-ops for the MVP |
| Validation | pandera | Typed dataframe schemas |
| Orchestration | Plain CLI + cron / GitHub Actions to start; Prefect/Dagster later | Keep it simple |
| API | FastAPI + Pydantic | Typed |
| Frontend | React + TypeScript + Vite; ECharts | Handles large time series well |
| Testing | pytest, hypothesis | Property tests for window math |
| Lint / format | ruff, mypy; eslint, prettier | |
| CI | GitHub Actions | |

Move to PostgreSQL only when there are multiple concurrent users or write-heavy metadata editing.

## 25. Repository layout

```text
quest-mf/
├── README.md
├── pyproject.toml
├── docs/
│   ├── mf_quant_screener_spec_v1.md
│   ├── mf_quant_screener_spec_v2.md      ← this file
│   ├── decisions/                        ← ADRs (one file per decision)
│   └── results/                          ← frozen backtest reports
├── config/
│   ├── settings.yaml                     ← staleness, min peers, exec lag…
│   ├── tax_rules.yaml
│   ├── category_mapping_pre2018.csv
│   └── models/
│       └── v1_baseline.yaml
├── src/questmf/
│   ├── ingest/        (amfi.py, sebi.py, benchmarks.py, rbi.py, mfapi.py)
│   ├── validate/      (schemas.py, checks.py)
│   ├── calendar/      (windows.py — CAL_/OBS_ logic, boundary rule)
│   ├── engine/        (rolling.py, distribution.py, percentile.py, risk.py, technical.py)
│   ├── universe/      (eligibility.py, canonical.py, categories.py)
│   ├── scoring/       (normalize.py, model.py)
│   ├── backtest/      (walkforward.py, execution.py, friction.py, stats.py)
│   ├── api/           (main.py, routers/)
│   └── cli.py         (questmf ingest | compute | score | backtest)
├── web/                                  ← React app
├── experiments/
│   └── registry.csv                      ← every config ever tried (§20)
├── data/                                 ← git-ignored (raw/, clean/, features/)
└── tests/
    ├── unit/
    ├── property/
    └── golden/                           ← small hand-verified NAV fixtures
```

## 26. API design

All endpoints are read-only, versioned under `/api/v1`, and accept `as_of=YYYY-MM-DD` (default: latest), so that any past screen can be reproduced.

```text
GET /api/v1/funds?category=&amc=&q=
GET /api/v1/funds/{portfolio_id}
GET /api/v1/funds/{portfolio_id}/nav?from=&to=
GET /api/v1/funds/{portfolio_id}/rolling?window=CAL_3M
GET /api/v1/funds/{portfolio_id}/distribution?window=CAL_3M&variant=EXPANDING
GET /api/v1/funds/{portfolio_id}/risk
GET /api/v1/funds/{portfolio_id}/costs
GET /api/v1/funds/{portfolio_id}/events
GET /api/v1/screener?category=small-cap&window=CAL_3M&min_confidence=OK
                   &investable_only=true&sort=composite&model=v1_baseline
GET /api/v1/categories
GET /api/v1/backtests
GET /api/v1/backtests/{run_id}
POST /api/v1/calculator/net-return   (body: amounts, dates, scheme → load/stamp/STT/tax estimate)
GET /api/v1/meta/data-freshness
```

## 27. UI / dashboard

v1 §27, §28 and §41 are kept. v2 adds:

- **Screener columns:** `SHP`, `Peer`, `Alpha 3M`, `IR 3Y`, `MDD`, `TER`, `Exit load`, `Score`, `Confidence`, badges (🔒 restricted, 👤 manager change, ⚠ proxy history).
- **Fund page, new panels:**
  - "Evidence strip": each score component with its underlying percentiles (why the rank is what it is).
  - Rolling IR chart; up/down capture bars.
  - SIP-XIRR rolling distribution.
  - Event timeline (manager, benchmark, category changes) overlaid on the NAV chart.
- **Backtest page:** equity curve gross vs net, IC time series with a rolling mean, quintile spread bars, regime table.
- **Net-return calculator:** amount, buy date, sell date → load, stamp, STT, estimated tax, net.
- **Data freshness banner:** last NAV date, last TER month, any failed checks.

## 28. Testing strategy and acceptance criteria

v1 tests A–G are kept. Added:

| ID | Test |
|---|---|
| H | `CAL_1M` ending 31 Mar resolves its target to 28/29 Feb (EOM clipping) |
| I | Boundary rule picks on-or-before, never after; staleness > limit → window dropped |
| J | SHP(t) is unchanged when NAV data after `t` is appended (property test) |
| K | Peer percentile counts one row per `portfolio_id` |
| L | IDCW series cannot become canonical (raises) |
| M | Backtest cannot buy at NAV(d); first possible fill is NAV(d + EXEC_LAG) |
| N | Restricted fund at `d` is never bought at `d` |
| O | Friction: a 1% load + 20% STCG example matches a hand-computed golden value |
| P | Merged-out fund appears in the universe before its merger date |
| Q | Percentile with ties uses mid-rank; `< 8` peers → null |
| R | Golden fixture: 3 funds × 2 years hand-calculated in a spreadsheet; engine output matches to 1e-9 |
| S | Full pipeline on a fixed snapshot gives a byte-identical scores Parquet file (reproducibility) |

Coverage target: 90% for `calendar/`, `engine/` and `backtest/`.

## 29. Operations

- **Schedule:** a nightly run after AMFI publishes (for example, 23:30 IST), plus a morning retry at 07:00 IST.
- **Idempotent:** re-running a date overwrites the same partitions. Runs are keyed by `data_snapshot_id`.
- **Incremental:** only new end dates are recomputed. A full rebuild runs weekly.
- **Monitoring:** row counts versus the previous day, number of failed checks, and freshness. Alerts go to email or Slack.
- **Backups:** `raw_ingest/` is append-only and backed up. Everything else can be rebuilt from it.
- **Secrets:** none are needed for the MVP (public sources). Keep `.env` out of git.

## 30. Roadmap and milestones

| Phase | Deliverable | Exit criteria |
|---|---|---|
| 0 | Repo skeleton, CI, spec v2 | CI green; this document merged |
| 1 | Ingestion: AMFI NAV (history + daily), scheme master, TER, category/benchmark mapping (post-2018), TRI for ~10 main indices, risk-free | Tests A, F, K, L pass; reconciliation vs MFAPI < 0.01% |
| 2 | Rolling engine (all `CAL_*`/`OBS_*`) + risk metrics | Tests A–C, E, H, I, R pass; full rebuild < 10 min |
| 3 | Distribution + percentile engine (point-in-time) | Tests D, J, Q pass |
| 4 | Scoring v1_baseline + read-only API + basic screener UI | Screener shows one category end-to-end |
| 5 | Walk-forward backtester + friction + stats | Tests M, N, O, P pass; report on dev + validation periods |
| 6 | **Go / no-go review** on H1–H5 using validation results | Written ADR |
| 7 | Technical features + ablation | Features kept only if they pass the §20 bar |
| 8 | Hold-out evaluation (once) | Frozen report in `docs/results/` |
| 9 | Phase-2 scope: holdings, style drift, hybrids, debt screener | — |

## 31. Open decisions

v1 Appendix C items 1–10 remain open. Added:

11. `MAX_STALENESS` and `MAX_GAP` values
12. Pre-2018 category mapping, or start the peer tests in 2018
13. Whether to TER-adjust the Regular-plan proxy before 2013
14. Minimum AUM and minimum peer count
15. Risk-free series choice (91D T-bill vs TREPS)
16. Whether SHP enters the composite (depends on the H3 result)
17. `EXEC_LAG_DAYS` and `SWITCH_GAP_DAYS`
18. Benchmark-data licensing for any external sharing
19. Legal review before any external distribution (§6.3)

Each decision gets an ADR in `docs/decisions/NNNN-title.md`.

## 32. Git workflow: clone, commit, push

Repository: **https://github.com/sp0303/quest-mf**

### 32.1 Clone
```bash
git clone https://github.com/sp0303/quest-mf.git
```
```bash
cd quest-mf
```

### 32.2 Set identity (once per machine)
```bash
git config user.name "Your Name"
```
```bash
git config user.email "you@example.com"
```

### 32.3 Day-to-day: branch, commit, push
```bash
git checkout -b feat/rolling-engine
```
```bash
git add -A
```
```bash
git commit -m "feat(engine): add CAL_* rolling returns with on-or-before boundary rule"
```
```bash
git push -u origin feat/rolling-engine
```
Then open a pull request into `main` on GitHub.

### 32.4 Keep your branch current
```bash
git fetch origin
```
```bash
git rebase origin/main
```
```bash
git push --force-with-lease
```

### 32.5 Conventions
- `main` is protected. All changes go through PRs with green CI.
- Commit prefixes: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `data`.
- Never commit `data/`, `.env`, or raw downloads. Add them to `.gitignore`.
- Every backtest report in `docs/results/` records the `git_sha` and `data_snapshot_id` that produced it.

---

## Appendix A — Formula reference

```text
Simple return            R = NAV_t / NAV_s − 1
Log return               r = ln(NAV_t / NAV_s)
CAGR                     (1+R)^(365.25/days) − 1
Active return            R_fund − R_bench          (same s, t)
Window count (OBS_N)     M − N + 1
OBS_N start index        end − (N − 1)
Drawdown                 DD_t = NAV_t / max(NAV_≤t) − 1
Max drawdown             MDD = min DD_t
Volatility (ann.)        std(d) · √252
Downside dev (ann.)      √mean(min(d − MAR, 0)²) · √252
Sharpe                   (CAGR − Rf) / vol
Sortino                  (CAGR − Rf) / downside_dev
Beta                     cov(d_f, d_b) / var(d_b)
Tracking error           std(d_f − d_b) · √252
Information ratio        annual active return / TE
Calmar                   CAGR / |MDD|
Momentum acceleration    r_1M − r_3M / 3
Momentum 12-1            r_12M − r_1M
Percentile (mid-rank)    100 · (#<x + 0.5·#=x) / n
SHP(t)                   pct(ret_t, {ret_s : s < t})
Confidence shrink        50 + (pct − 50) · min(1, n_eff / 12)
Rank IC(d)               Spearman(score_d, fwd_ret_d)
```

## Appendix B — Glossary

| Term | Meaning |
|---|---|
| AMFI | Association of Mutual Funds in India |
| TRI / PRI | Total Return Index / Price Return Index |
| TER | Total Expense Ratio (already inside NAV) |
| IDCW | Income Distribution cum Capital Withdrawal (formerly "dividend") option |
| SHP | Self-History Percentile — the current value vs the fund's own past |
| CP / Peer pct | Cross-sectional percentile vs the category on the same date |
| IC | Information Coefficient — rank correlation of score with forward return |
| HAC | Heteroskedasticity- and autocorrelation-consistent (Newey-West) errors |
| ADR | Architecture Decision Record |
| Portfolio ID | Internal ID grouping all plans and options of one scheme |

## Appendix C — Sources

From v1 (kept):
- AMFI — NAV History: https://www.amfiindia.com/sif/latest-nav/nav-history
- AMFI — NAV information: https://www.amfiindia.com/investor/knowledge-center-info?zoneName=NetAssetValueNAV
- AMFI — TER of MF Schemes: https://www.amfiindia.com/ter-of-mf-schemes
- AMFI — Expense Ratio: https://www.amfiindia.com/investor/knowledge-center-info?zoneName=expenseRatio
- SEBI — Mutual Fund filings: https://www.sebi.gov.in/filings/mutual-funds.html
- SEBI — Master Circular for Mutual Funds (March 2026): https://www.sebi.gov.in/sebi_data/attachdocs/mar-2026/1774024028162.pdf
- MFAPI — https://www.mfapi.in/docs/

Added in v2 (verify current URLs and terms before automating):
- AMFI daily NAV file: https://www.amfiindia.com/spages/NAVAll.txt
- NSE Indices (Nifty TRI history): https://www.niftyindices.com
- Asia Index (BSE indices): https://www.asiaindex.co.in
- RBI Database on Indian Economy (T-bill yields): https://data.rbi.org.in
- FBIL benchmark rates: https://www.fbil.org.in
- SEBI circular on categorisation & rationalisation of MF schemes (Oct 2017) — sebi.gov.in
- Income Tax Department — capital gains rates (Finance (No. 2) Act 2024) — incometaxindia.gov.in
- Carhart, M. (1997). *On Persistence in Mutual Fund Performance.* Journal of Finance 52(1).
- Bailey, D. & López de Prado, M. (2014). *The Deflated Sharpe Ratio.* Journal of Portfolio Management.
- Newey, W. & West, K. (1987). *A Simple, Positive Semi-definite, Heteroskedasticity and Autocorrelation Consistent Covariance Matrix.* Econometrica.
