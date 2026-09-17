# MF Quant Screener & Rolling-Window Research Specification

**Document status:** Draft v1.0
**Date:** 17 September 2026
**Purpose:** Engineering + quantitative research specification for an Indian mutual-fund screener focused on identifying funds with strong *current* behavior while testing whether that behavior has historically persisted across rolling windows.

---

## 0. Executive summary

The project should **not** try to find a "guaranteed" mutual fund or simply rank schemes by the latest 3-month return. No historical metric can guarantee the next 1–3 months; SEBI's investor disclosures explicitly state that past performance does not guarantee future performance and that mutual-fund investments are subject to market risk. [SEBI](https://www.sebi.gov.in/sebi_data/attachdocs/mar-2026/1774024028162.pdf)

The core research problem is:

> **A fund showing +20% over the latest 3 months tells us only what happened in that particular trailing window. How can we determine whether the current strength is persistent, unusual, benchmark-relative, risk-adjusted, and robust across many historical entry dates?**

The solution proposed here is a **rolling-window, multi-horizon, benchmark-relative, risk- and cost-aware screener**, followed by **walk-forward backtesting**.

The system should combine four layers:

1. **Current state:** 1M, 3M, 6M momentum, RSI, moving averages, momentum acceleration, relative strength.
2. **Historical persistence:** distributions of rolling 3M/6M/1Y/3Y/5Y returns and benchmark-relative results across many past windows.
3. **Risk and friction:** drawdown, downside deviation, volatility, TER, exit load, and estimated transaction/tax effects.
4. **Validation:** walk-forward / out-of-sample testing so that a score is not accepted merely because it looks mathematically attractive.

---

# 1. The problem we are actually solving

A typical mutual-fund page might say:

```text
Fund X
1M return:  +7%
3M return: +20%
1Y return: +9%
```

The naïve conclusion is:

> "3M = +20%, therefore this is a good fund for the next 3 months."

That conclusion is not justified.

The 3M return is a **trailing historical measurement**. As the current date moves forward, the window also moves forward. A strong 3M return can disappear quickly when the older strong/weak starting observation falls out of the window.

This is the central **sliding-window problem**.

---

# 2. First correction to the proposed rolling-window idea

The proposed idea of moving the 3-month window backward through history is **correct in principle**.

However, there are two important technical corrections:

### 2.1 "90 days" is not automatically "3 months"

A fixed 90-calendar-day window and a calendar 3-month window are slightly different concepts.

For example, an inclusive 90-calendar-day window ending on **1 June** starts on **4 March**.

```text
4 Mar ─────────────────────────── 1 Jun
          90 calendar days
```

But a calendar 3-month window is conceptually:

```text
1 Mar ─────────────────────────── 1 Jun
          3 calendar months
```

If a boundary date is a weekend/holiday, there may be no NAV on that date. The implementation should therefore map the target boundary to the appropriate available NAV observation.

### 2.2 Do not use 90 NAV observations to represent 3 months

Mutual funds generally publish NAV on business days. A 90-observation window is roughly 90 trading/business-day observations, which is materially longer than three calendar months.

Therefore we should support **two distinct window definitions**:

**Primary user-facing definition:** calendar-based 1M / 3M / 6M / 1Y etc.

**Research/sensitivity definition:** fixed-N-observation windows such as approximately 21, 63, 126, 252 observations.

This distinction should be explicit in the data model.

AMFI states that open-ended mutual-fund NAVs are published daily and provides historical NAV facilities, so historical NAV observations are the correct base dataset for this research. [AMFI NAV History](https://www.amfiindia.com/sif/latest-nav/nav-history) [AMFI NAV](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=NetAssetValueNAV)

---

# 3. Correct definition of a rolling window

Let:

- `t` = the end date of the window
- `H` = horizon
- `NAV(t)` = NAV at the end date
- `NAV(t-H)` = NAV at the beginning boundary, mapped to the nearest valid historical NAV according to our date convention

For a simple growth return:

```text
Return_H(t) = NAV(t) / NAV(t-H) - 1
```

For every historical NAV date `t`, calculate a trailing return.

Example:

```text
Historical NAV dates:

Jan 02
Jan 03
Jan 04
...
Mar 01
...
Jun 01
...
Sep 17
```

For a 3-month window ending on June 1:

```text
start ≈ March 1
end   = June 1

3M return = NAV(June 1) / NAV(March 1) - 1
```

Then move the **end date** backward by one available NAV observation (or by one calendar day, depending on the research convention):

```text
Window A: Mar 1  → Jun 1
Window B: Feb end → May end / previous NAV observation
Window C: Feb end → May previous NAV observation
...
```

The exact implementation should use a clearly specified boundary rule rather than informal "minus 89 to 1" indexing.

---

# 4. The key idea: every historical date gets its own trailing window

Suppose the latest date is `T`.

The current 3M return is only one point:

```text
T-3M ───────────────── T
```

We should instead calculate:

```text
T-4M ───────────── T-1M
T-5M ───────────── T-2M
T-6M ───────────── T-3M
...
```

More precisely, for every eligible historical end date `t_i`:

```text
Window_i = [t_i - 3M, t_i]
```

Then calculate:

```text
R_3M(i) = NAV(t_i) / NAV(start_i) - 1
```

This creates a **distribution** of historical rolling 3M returns rather than one number.

---

# 5. Important correction: there will NOT be only 90 rolling windows

If we have one NAV observation per business day and calculate one rolling window ending at every valid NAV date, the number of rolling windows depends on the amount of history.

For example, with about 252 business-day observations per year:

```text
1 year of history + 63-observation window
≈ 190 eligible rolling windows
```

For five years:

```text
≈ 1260 observations
- 63-window warm-up
+ 1
≈ 1198 rolling windows
```

The exact number depends on holidays, missing NAVs, scheme inception date, mergers, and the window definition.

Thus the correct mental model is:

> **A 90-day window is the width of each window; it is not the number of windows.**

If we use daily NAVs and roll one observation at a time, thousands of historical windows can be produced from long-lived funds.

---

# 6. Overlapping windows are useful — but they are not independent samples

For descriptive analysis, overlapping windows are exactly what we want because they show how the fund behaved across many possible entry dates.

However, the windows overlap heavily:

```text
Window 1:  |-------------------|
Window 2:     |-------------------|
Window 3:        |-------------------|
Window 4:           |-------------------|
```

Therefore:

- Use them to calculate rolling-return distributions and consistency statistics.
- **Do not** treat every rolling window as an independent statistical experiment.
- When evaluating the performance of an actual trading/investment strategy, use a walk-forward procedure with a specified decision/rebalance frequency.

This distinction is important to avoid overstating statistical confidence.

---

# 7. What the rolling distribution should tell us

For every fund and every horizon, calculate more than the latest return.

For rolling 3M returns, store:

```text
current_3m_return
mean_rolling_3m
median_rolling_3m
std_rolling_3m
min_rolling_3m
max_rolling_3m
p10_rolling_3m
p25_rolling_3m
p50_rolling_3m
p75_rolling_3m
p90_rolling_3m
positive_window_pct
```

The same structure should be available for 1M, 6M and 1Y. Longer horizons require annualized/CAGR treatment where appropriate.

Example:

```text
                    Fund A     Fund B
Current 3M return       20%        17%
Median rolling 3M       12%        14%
Mean rolling 3M         13%        14%
10th percentile         -9%         2%
90th percentile          27%        24%
Positive windows         69%        92%
```

Fund A has stronger current momentum, but Fund B has historically been more consistent over this horizon.

The screener should expose both facts rather than collapsing them into a single "best fund" label.

---

# 8. The most important new metric: current position within its own history

This is a simple common-sense idea that should be part of Version 1.

Suppose Fund X has:

```text
Historical rolling 3M return distribution

10th percentile    -8%
25th percentile     3%
50th percentile    11%
75th percentile    17%
90th percentile    23%
```

Current 3M return:

```text
+20%
```

Then today's return is historically high for that fund.

Define:

```text
Current_Horizon_Percentile
= percentile rank of today's trailing H return
  within the historical rolling-H return distribution
```

This is different from comparing Fund X against other funds.

It answers:

> **"How unusual/strong is the fund's current state compared with its own historical behavior?"**

This should be called something like:

```text
Self-History Percentile (SHP)
```

---

# 9. Cross-sectional percentile: compare the fund against its peers

We also need a second percentile.

For all funds in the same peer/category universe on today's date:

```text
Fund A 3M return = 20% → 96th percentile
Fund B 3M return = 17% → 88th percentile
Fund C 3M return = 15% → 81st percentile
```

This answers:

> **"How strong is this fund relative to other funds today?"**

Therefore we should have two distinct concepts:

```text
SHP = strength relative to the fund's own history
CP  = strength relative to its peer group today
```

These should never be confused.

---

# 10. Benchmark-relative performance

A fund should not be judged only against other funds.

The appropriate benchmark must correspond to the scheme's investment objective, asset allocation and strategy. SEBI's 2026 Mutual Fund Master Circular requires scheme performance to be benchmarked to the **Total Return (TRI) variant** of the chosen benchmark. [SEBI Master Circular, March 2026](https://www.sebi.gov.in/sebi_data/attachdocs/mar-2026/1774024028162.pdf)

For each scheme we therefore need:

```text
scheme_benchmark_id
benchmark_TRI_series
```

For each horizon:

```text
fund_return_H
benchmark_return_H
active_return_H = fund_return_H - benchmark_return_H
```

And for rolling windows:

```text
rolling_active_return_H(t)
```

Then calculate:

```text
median_rolling_alpha
positive_alpha_pct
benchmark_beat_pct
current_alpha_percentile
```

Example:

```text
Fund A       +20%
Benchmark    +19%
Active        +1%

Fund B       +17%
Benchmark     +7%
Active       +10%
```

The raw return alone would hide this difference.

---

# 11. Multi-horizon analysis

The screener should not simply mix 1M + 3M + 1Y + 3Y + 5Y as raw percentages.

Different horizons measure different things.

## Short-term state

```text
1M
3M
6M
```

These are useful for identifying current momentum/regime.

## Medium-term persistence

```text
1Y
```

Useful for checking whether recent strength is part of a longer pattern.

## Long-term structural history

```text
3Y
5Y
```

Useful as a quality/history prior, not as a prediction of the next 3 months.

A 5-year CAGR of 15% should not be interpreted as "therefore the next 3 months will return 3.75%."

---

# 12. A better score architecture

The score should have separate components.

```text
CURRENT MOMENTUM
        │
        ├── 1M relative percentile
        ├── 3M relative percentile
        ├── 6M relative percentile
        ├── RSI/state
        ├── price/NAV vs SMA20
        ├── NAV vs SMA50
        └── momentum acceleration

HISTORICAL PERSISTENCE
        │
        ├── rolling 3M positive-window %
        ├── rolling 3M benchmark-beat %
        ├── rolling 3M median alpha
        ├── rolling 6M consistency
        ├── rolling 1Y consistency
        └── long-term consistency

RISK
        │
        ├── max drawdown
        ├── volatility
        ├── downside deviation
        ├── Sortino
        └── recovery behavior

FRICTION / COST
        │
        ├── TER
        ├── exit load
        ├── exit-load holding period
        └── estimated transaction/tax impact
```

Do not finalize the numerical weights before backtesting them.

A sensible initial research hypothesis is:

```text
Current momentum       30%
Historical persistence 35%
Risk                   25%
Cost/friction          10%
```

These are **research starting weights**, not a proven optimal model.

---

# 13. The "current strength vs historical normality" matrix

One of the most useful dashboard views should be a 2x2 matrix.

```text
                         CURRENT vs OWN HISTORY

                    Low / normal       High / unusual

Peer weak           Watch              Special situation

Peer strong         Strong candidate   Very strong but extended
```

More concretely:

### Case A: peer-strong + own-history-normal

Current performance is strong versus peers but not unusually strong versus the fund's own history.

### Case B: peer-strong + own-history-extreme

Current performance is strong and unusual. This may be excellent momentum, but can also mean the fund is extended. Do not interpret it automatically as a buy signal.

### Case C: peer-weak + own-history-strong

Fund is doing well versus its own history but the whole category may be stronger.

### Case D: peer-weak + own-history-weak

Broad weakness and fund-specific weakness.

This avoids reducing all information into one number too early.

---

# 14. Momentum indicators

The system can calculate technical indicators on daily NAV observations.

## RSI(14)

Use as a state/diagnostic variable, not a standalone decision rule.

```text
RSI(14)
```

Avoid automatically assuming:

```text
RSI > 70 = sell
RSI < 30 = buy
```

Those are simplified heuristics and should be empirically tested on the particular MF universe.

## Moving averages

```text
SMA5
SMA10
SMA20
SMA50
SMA100
SMA200
```

Derived state variables:

```text
NAV > SMA20
NAV > SMA50
SMA20 > SMA50
SMA50 > SMA200
distance_from_SMA20
distance_from_SMA50
```

## Rate of change

```text
ROC_H = NAV(t) / NAV(t-H) - 1
```

## Momentum acceleration

A simple initial feature:

```text
MomentumAcceleration
= Return_1M - Return_3M / 3
```

This should be treated as an exploratory feature. A later version may use regression slope or a normalized change in momentum.

---

# 15. One more common-sense signal: path, not just endpoint

Two funds can both produce +20% over three months while taking completely different paths.

Example:

```text
Fund A:
+2% → +4% → +6% → +8% ...

Fund B:
-15% → -10% → -5% → +20%
```

The endpoint return is similar, but the investor experience and risk are very different.

Therefore calculate path statistics inside every rolling window:

```text
maximum drawdown within window
volatility
worst daily return
best daily return
negative-day percentage
average negative day
recovery time
```

This should be part of the rolling-window engine.

---

# 16. Maximum drawdown

For each rolling window:

```text
running_peak(t) = max(NAV up to t)

Drawdown(t) = NAV(t) / running_peak(t) - 1

MaxDrawdown(window) = minimum Drawdown(t)
```

Then across all rolling 3M windows:

```text
median_3M_max_drawdown
worst_3M_max_drawdown
90th_percentile_drawdown
```

This helps answer:

> "When this fund delivers short-term returns, how much pain has historically occurred inside those same windows?"

---

# 17. Expense ratio: important, but do not subtract it twice

AMFI states that TER represents scheme operating expenses and that the daily NAV is disclosed **after deducting expenses**. Therefore historical NAV-based returns already incorporate the expenses charged to the scheme during the relevant period. [AMFI Expense Ratio](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=expenseRatio)

Therefore do **not** do this:

```text
Historical return - current TER = "true historical return"
```

That double-counts expenses.

Instead:

```text
Historical NAV return
        ↓
already reflects historical scheme expenses

Current TER
        ↓
is a current/future cost and comparison variable
```

Compare TER primarily **within comparable categories**.

AMFI publishes TER data for schemes. [AMFI TER](https://www.amfiindia.com/ter-of-mf-schemes)

---

# 18. Exit load

The exit load must be treated as a separate investment friction.

Example:

```text
Investment NAV value at redemption = ₹100,000
Exit load rate = 1%

Estimated exit-load deduction = ₹1,000
```

The exact scheme rules must be read because the rate, holding-period rule, applicability to units, and prospective changes are scheme-specific.

AMFI notes that redemption may include exit load where applicable, and SEBI scheme documents disclose load structures. [AMFI](https://www.amfiindia.com/investor/become-mf-distributor?zoneName=InvestorService) [SEBI Scheme Documents](https://www.sebi.gov.in/filings/mutual-funds.html)

For this project store:

```text
exit_load_rate
exit_load_days
exit_load_rule_text
exit_load_source_url
```

And calculate:

```text
days_held
exit_load_applicable
estimated_exit_load_amount
```

---

# 19. Net-result calculator

The dashboard should separate **fund scoring** from **investor-specific realized return**.

Conceptually:

```text
NAV-based gain
      - exit load
      - applicable transaction charges
      - applicable taxes
      = estimated investor net result
```

Taxes should not be embedded inside the universal fund-quality score because tax depends on the investor, transaction structure, holding period and applicable tax rules.

The tax engine should therefore be a separate module.

---

# 20. Data sources

## 20.1 Official / primary sources

### AMFI NAV history

Use for historical scheme NAV data.

- Historical NAV: https://www.amfiindia.com/sif/latest-nav/nav-history
- AMFI NAV information: https://www.amfiindia.com/investor/knowledge-center-info?zoneName=NetAssetValueNAV

AMFI provides historical NAV facilities and daily NAV information. [AMFI](https://www.amfiindia.com/sif/latest-nav/nav-history)

### AMFI TER

Use for current/historical expense-ratio data.

- https://www.amfiindia.com/ter-of-mf-schemes

AMFI's TER page provides scheme-level TER information. [AMFI](https://www.amfiindia.com/ter-of-mf-schemes)

### SEBI mutual-fund filings

Use for scheme documents, load structure, benchmark disclosures, risk disclosures, and other authoritative documents.

- https://www.sebi.gov.in/filings/mutual-funds.html

### Benchmark TRI data

Use the relevant benchmark's Total Return Index series. The scheme's benchmark must be mapped according to the scheme objective and official disclosure.

SEBI's March 2026 Master Circular states that scheme performance is benchmarked to the Total Return variant of the chosen benchmark. [SEBI](https://www.sebi.gov.in/sebi_data/attachdocs/mar-2026/1774024028162.pdf)

---

## 20.2 Convenient third-party API layer

A practical development option is **MFAPI.in**, which exposes scheme search/latest NAV/historical NAV through JSON endpoints without requiring an API key for its basic public API.

- https://www.mfapi.in/docs/

Treat this as a **convenience/cache layer**, not the authoritative legal/source-of-truth layer.

Recommended architecture:

```text
AMFI / SEBI / official benchmark data
              ↓
        source-of-truth ingestion
              ↓
       validation + normalization
              ↓
             storage
              ↑
         MFAPI (optional)
       convenience / recovery
```

---

# 21. Proposed database model

## `funds`

```text
scheme_code
isin_growth
fund_name
amc
category
sub_category
plan                 -- Direct / Regular
option               -- Growth / IDCW
inception_date
status
benchmark_id
riskometer
```

## `nav_history`

```text
scheme_code
nav_date
nav
source
source_timestamp
```

Unique key:

```text
(scheme_code, nav_date)
```

## `ter_history`

```text
scheme_code
period
ter
base_expense_ratio
brokerage_cost
transaction_cost
source
```

## `load_rules`

```text
scheme_code
effective_from
effective_to
exit_load_rate
exit_load_days
rule_text
source_url
```

## `benchmark_history`

```text
benchmark_id
benchmark_date
tri_value
source
```

## `rolling_metrics`

```text
scheme_code
end_date
horizon
return
benchmark_return
active_return
max_drawdown
volatility
downside_deviation
positive_day_pct
```

## `daily_features`

```text
scheme_code
feature_date
return_1m
return_3m
return_6m
return_1y
rsi14
sma20
sma50
sma200
roc20
momentum_acceleration
```

## `rolling_distribution_features`

```text
scheme_code
as_of_date
horizon
mean_return
median_return
std_return
p10_return
p25_return
p50_return
p75_return
p90_return
min_return
max_return
positive_window_pct
benchmark_beat_pct
median_active_return
```

## `scores`

```text
scheme_code
as_of_date
momentum_score
persistence_score
risk_score
cost_score
composite_score
model_version
```

---

# 22. Rolling engine pseudocode

```python
for fund in eligible_funds:
    nav = load_nav_history(fund)
    nav = clean_and_sort(nav)

    for end_date in nav.dates:
        for horizon in ["1M", "3M", "6M", "1Y"]:
            start_date = resolve_start_date(end_date, horizon)

            if start_date is None:
                continue

            window = nav.loc[start_date:end_date]

            if not enough_observations(window):
                continue

            total_return = nav[end_date] / nav[start_date] - 1

            max_dd = calculate_max_drawdown(window)
            vol = calculate_volatility(window)
            downside = calculate_downside_deviation(window)

            benchmark = load_matching_benchmark(fund, end_date, horizon)
            benchmark_return = benchmark.return_value
            active_return = total_return - benchmark_return

            store_rolling_metric(
                fund=fund,
                end_date=end_date,
                horizon=horizon,
                total_return=total_return,
                benchmark_return=benchmark_return,
                active_return=active_return,
                max_drawdown=max_dd,
                volatility=vol,
                downside_deviation=downside,
            )
```

---

# 23. How the backward rolling process should work

Suppose `T` is the latest NAV date.

### Current window

```text
T-3M ----------------------------- T
```

Calculate:

```text
R_3M(T)
```

### Previous window

Use the previous valid NAV date as the window's end date:

```text
T-1NAV
```

and calculate:

```text
R_3M(T-1NAV)
```

### Continue

```text
R_3M(T)
R_3M(T-1NAV)
R_3M(T-2NAV)
R_3M(T-3NAV)
...
```

This is the preferred implementation for NAV-based rolling analysis because it uses observations that actually exist in the historical series.

We can also maintain a calendar-date version where the end dates are every calendar day and the latest available NAV is mapped to each target date. That can be useful for presentation, but the storage layer should preserve the actual NAV observation date.

---

# 24. Example using the user's June 1 concept

Assume:

```text
Current date = June 1
```

### Calendar 3-month window

Conceptual period:

```text
March 1 → June 1
```

If March 1 or June 1 has no NAV, use the project-defined valid-NAV boundary rule.

### Fixed 90-calendar-day window

For an inclusive 90-day period ending June 1:

```text
March 4 → June 1
```

### Fixed 90-observation window

If there are 90 valid NAV observations including the endpoint:

```text
NAV observation #1 ... NAV observation #90
```

The starting observation is:

```text
end_index - 89
```

This is probably what the proposed "minus 89 to 1" indexing was trying to express.

**Recommendation:** call these three methods different things in code. Do not use `90D` for all of them.

Suggested identifiers:

```text
CAL_3M
CAL_90D
OBS_90
```

---

# 25. Avoiding an off-by-one error

For an N-observation window:

```text
window_size = N
start_index = end_index - (N - 1)
```

Therefore:

```text
N = 90
start = end - 89
```

not:

```text
start = end - 90
```

unless the implementation intentionally defines the interval as 91 observations.

Unit tests must explicitly verify this.

---

# 26. The number of rolling windows

If a series contains `M` valid observations and the window contains `N` observations:

```text
number_of_windows = M - N + 1
```

Example:

```text
M = 250 observations
N = 90 observations

windows = 250 - 90 + 1
        = 161
```

This is another reason the statement "90-day window = 90 windows" is incorrect.

---

# 27. What should be shown on the fund detail page

```text
FUND: XYZ Direct Growth

CURRENT STATE
────────────────────────────────
1M return                   +7.2%
3M return                  +19.8%
6M return                  +21.5%
1Y return                  +13.1%

Peer percentile (3M)       94
Own-history percentile     91
Benchmark alpha (3M)       +7.4%

RSI(14)                    64.2
NAV vs SMA20               +3.8%
NAV vs SMA50               +7.1%

HISTORICAL PERSISTENCE
────────────────────────────────
Rolling 3M median           11.7%
Rolling 3M positive %       78%
Rolling 3M beat benchmark % 66%
Rolling 3M worst            -14.2%
Rolling 3M best              +31.5%

RISK
────────────────────────────────
Median 3M drawdown          -5.4%
Worst rolling 3M drawdown   -18.7%
Downside deviation           ...

COST
────────────────────────────────
TER                           ...
Exit load                     1% / 90 days
```

The system should present the **evidence**, not merely output a magic number.

---

# 28. The most useful charts

## Chart 1 — NAV + moving averages

```text
NAV
SMA20
SMA50
SMA200
```

## Chart 2 — Rolling 3M return

Plot the entire historical rolling 3M return series.

This directly visualizes the sliding-window problem.

## Chart 3 — Rolling 3M active return

```text
Fund 3M return - Benchmark 3M return
```

## Chart 4 — Rolling 3M drawdown

Shows how much pain existed inside each historical window.

## Chart 5 — Return distribution

Histogram / percentile bands:

```text
P10  P25  P50  P75  P90
```

Highlight today's value.

## Chart 6 — Current-vs-history matrix

```text
X = peer percentile
Y = own-history percentile
```

## Chart 7 — Regime timeline

Color/state-label the historical periods:

```text
weak → neutral → strong → extreme
```

This helps detect whether the current state resembles previous episodes.

---

# 29. Walk-forward backtesting: the most important validation layer

After creating the score, do **not** immediately use it for real money.

We need to test:

> If the system ranked funds using only information known on date `t`, what happened after date `t`?

Example:

```text
Training / information available:
          through 31 Jan 2024
                    ↓
              calculate score
                    ↓
              select/rank funds
                    ↓
             observe next 1M
             observe next 3M

Move forward:

Information through 29 Feb 2024
                    ↓
             calculate score again
                    ↓
             observe next 1M / 3M
```

Repeat for many historical dates.

This is a **walk-forward evaluation**.

---

# 30. What to measure in the backtest

Do not only measure average return.

Track:

```text
Next-1M return
Next-3M return
Median next-3M return
Hit rate
Downside hit rate
Maximum drawdown
Benchmark-relative return
Worst historical outcome
Best historical outcome
Turnover
Exit-load impact
```

Also compare:

```text
Top 1 ranked fund
Top 5
Top 10%
Top quartile
Random/category benchmark
```

The purpose is to determine whether the model adds information beyond simply holding a category benchmark.

---

# 31. Critical anti-overfitting rules

The system must obey these rules.

### Rule 1 — No future information

When scoring date `t`, use only information available by date `t`.

### Rule 2 — No current metadata leaking into historical tests

If a scheme's TER, benchmark, exit load or classification changed later, the backtest must use the historical value applicable at the test date where possible.

### Rule 3 — No survivorship bias

Do not build historical universes only from funds that exist today if the test is supposed to represent the universe that an investor could actually have selected at the time.

### Rule 4 — Do not over-tune weights

If 17 indicators and 24 thresholds are optimized over the same history, the model can simply memorize the past.

### Rule 5 — Keep a true out-of-sample period

A later period must be held back and not used to tune the model.

---

# 32. A simpler Version 1 model

Before adding RSI/MACD/etc., build a clean baseline.

### Features

```text
1M return percentile vs peers
3M return percentile vs peers
6M return percentile vs peers

3M own-history percentile
3M positive-window percentage
3M benchmark-beat percentage

1Y CAGR percentile
3Y CAGR percentile
5Y CAGR percentile

3M median active return
3M worst drawdown

TER percentile
Exit-load friction
```

### Initial composite

```text
Momentum                 25%
Persistence              35%
Long-term quality        15%
Risk                     15%
Cost/friction             10%
```

Again: these are **initial research weights** and must be validated.

This intentionally keeps Version 1 simple enough that we can understand why the rank changes.

---

# 33. Version 2

Add:

```text
RSI14
SMA20/SMA50 state
SMA crossover
ROC20
momentum acceleration
relative-strength trend
rolling volatility regime
rolling alpha trend
```

Then perform **feature ablation testing**:

```text
Baseline
Baseline + RSI
Baseline + moving averages
Baseline + momentum acceleration
Baseline + all technical features
```

If RSI does nothing in out-of-sample testing, remove it.

If a feature improves results robustly across different periods/categories, keep it.

---

# 34. Category-aware comparison is mandatory

Do not rank:

```text
Small Cap
Large Cap
Debt
Gold
Sector/Thematic
International
```

as if they were interchangeable investments.

The primary peer comparison should be within a coherent category/universe.

Examples:

```text
Small Cap fund ↔ Small Cap peers + appropriate benchmark
Large Cap fund ↔ Large Cap peers + appropriate benchmark
Flexi Cap ↔ Flexi Cap peers + appropriate benchmark
```

Cross-category comparison can be shown as a separate research screen, but it should not replace category-aware analysis.

---

# 35. New-fund problem

A young fund cannot have 3Y/5Y historical distributions.

Therefore the engine must have a minimum-history rule.

Example:

```text
3M model → minimum 1 year history
1Y model → minimum 3 years history
3Y model → minimum 5 years history
5Y model → minimum 7 years history
```

These are implementation suggestions, not universal financial rules.

A fund that lacks enough history should be marked:

```text
INSUFFICIENT_HISTORY
```

rather than receiving an artificial zero.

---

# 36. Scheme mergers / changes

Historical identity needs careful treatment when schemes merge, rename, or change structure.

The backtester should maintain:

```text
scheme_id
legacy_scheme_id
parent_scheme_id
merger_date
name_history
benchmark_history
category_history
```

SEBI's current Master Circular contains specific disclosure treatment for post-merger performance, reinforcing that scheme-history continuity cannot simply be assumed. [SEBI Master Circular](https://www.sebi.gov.in/sebi_data/attachdocs/mar-2026/1774024028162.pdf)

---

# 37. Data-quality rules

Every ingestion run should check:

```text
No duplicate (scheme, date)
No negative NAV
No impossible zero NAV
Dates sorted
Unexpected gaps flagged
Large one-day NAV moves flagged
Scheme plan/option consistent
Benchmark mapping exists
Exit-load rule exists or explicitly marked unknown
TER date exists
```

A missing NAV should not automatically be forward-filled for return calculations without an explicit rule.

---

# 38. API/data-ingestion strategy

Recommended priority:

```text
1. AMFI NAV history
2. AMFI TER
3. Official scheme documents / SEBI filings
4. Official benchmark TRI data
5. AMC pages for verification
6. MFAPI for convenient programmatic access / recovery
```

The system should retain:

```text
source
source_url
retrieved_at
raw_payload_hash
parser_version
```

so that calculations are reproducible.

---

# 39. Suggested project architecture

```text
                        DATA SOURCES
               ┌─────────┬──────────┬─────────┐
               │         │          │         │
             AMFI      SEBI      Benchmark   MFAPI
               │         │          │         │
               └─────────┴──────────┴─────────┘
                              │
                       DATA INGESTION
                              │
                       VALIDATION LAYER
                              │
                   ┌──────────┴──────────┐
                   │                     │
                PostgreSQL              DuckDB
                   │                     │
                   └──────────┬──────────┘
                              │
                     FEATURE ENGINE
                              │
              ┌───────────────┼────────────────┐
              │               │                │
          Rolling returns   Risk engine    Technical engine
              │               │                │
              └───────────────┼────────────────┘
                              │
                    SCORING / RANKING
                              │
                       WALK-FORWARD
                         BACKTESTER
                              │
                           FastAPI
                              │
                    React + TypeScript
                              │
                         Dashboard
```

For an MVP, **DuckDB + Parquet + Python/FastAPI + React** is sufficient. PostgreSQL can be introduced when live multi-user serving, metadata relationships, or higher operational complexity justifies it.

---

# 40. Minimal API design

```text
GET /funds
GET /funds/{scheme_code}
GET /funds/{scheme_code}/nav
GET /funds/{scheme_code}/metrics
GET /funds/{scheme_code}/rolling
GET /funds/{scheme_code}/benchmark
GET /funds/{scheme_code}/costs

GET /screener?category=small-cap&horizon=3M
GET /screener?category=small-cap&sort=composite_score

GET /backtest/model/v1
GET /backtest/model/v1/results
```

---

# 41. Suggested screener UI

```text
┌─────────────────────────────────────────────────────────────┐
│ MF QUANT SCREENER                                           │
├─────────────────────────────────────────────────────────────┤
│ Category [Small Cap]   Plan [Direct]   Option [Growth]     │
│                                                             │
│ Horizon [3M]  Min History [3Y]  Exit Load [Any]            │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Fund        1M  3M  1Y  SHP  Peer  Alpha  DD  Score   │ │
│ │ Fund A      7% 20% 11%  91   96    +7%   -8%  82.4    │ │
│ │ Fund B      6% 17% 15%  74   88   +10%   -5%  80.1    │ │
│ │ Fund C     10% 15%  9%  97   81    +4%  -14%  71.7    │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

Clicking a fund opens the detail charts.

---

# 42. The exact core question our model should answer

The system is NOT trying to answer:

> "Which mutual fund is guaranteed to make money next quarter?"

It should answer:

> **"Among the eligible funds today, which ones combine strong current momentum with historically persistent behavior, benchmark-relative strength, acceptable risk, and manageable friction — and does this methodology demonstrate useful out-of-sample behavior in historical walk-forward tests?"**

That is a testable research problem.

---

# 43. Recommended Version 1 implementation order

### Phase 1 — Data

```text
AMFI scheme metadata
AMFI daily NAV
AMFI TER
benchmark TRI
exit-load metadata
```

### Phase 2 — Rolling engine

Implement:

```text
CAL_1M
CAL_3M
CAL_6M
CAL_1Y
OBS_21
OBS_63
OBS_126
OBS_252
```

### Phase 3 — Distribution engine

Calculate:

```text
mean
median
P10/P25/P50/P75/P90
positive-window %
benchmark-beat %
median active return
max drawdown
```

### Phase 4 — Percentile engine

Calculate:

```text
peer percentile
own-history percentile
benchmark-relative percentile
```

### Phase 5 — Screener

Expose filters and charts.

### Phase 6 — Backtester

Run historical walk-forward tests.

### Phase 7 — Technical indicators

Only after the baseline model is validated:

```text
RSI
SMA
MACD
ROC
momentum acceleration
```

### Phase 8 — Advanced model

Potentially test machine learning later.

Do not start with ML.

---

# 44. Acceptance criteria for the rolling-window engine

A correct implementation must pass these tests.

### Test A — window size

For an N-observation window:

```text
N = 90
```

must contain exactly 90 valid observations.

### Test B — off-by-one

Start index must equal:

```text
end_index - 89
```

for a 90-observation inclusive window.

### Test C — window count

For M observations:

```text
M - N + 1
```

eligible windows should be generated, absent missing-data exclusions.

### Test D — no future leakage

Metrics as of date `t` must not depend on NAV values after `t`.

### Test E — benchmark alignment

Fund and benchmark return periods must use identical boundaries.

### Test F — missing dates

Weekends/holidays must not create fake zero-return observations.

### Test G — reproducibility

Same input data + same model version = same score.

---

# 45. Important research conclusion

The new rolling-window idea is **correct and should become one of the central components of the project**.

But it becomes powerful only after making these distinctions:

```text
              ONE CURRENT 3M RETURN
                       │
                       ↓
              NOT ENOUGH INFORMATION
                       │
                       ↓
            MANY ROLLING 3M WINDOWS
                       │
          ┌────────────┼────────────┐
          ↓            ↓            ↓
      DISTRIBUTION  CONSISTENCY  DRAWDOWN
          │            │            │
          └────────────┼────────────┘
                       ↓
              BENCHMARK RELATIVE
                       ↓
               CURRENT VS HISTORY
                       ↓
                 CURRENT VS PEERS
                       ↓
                 COST / FRICTION
                       ↓
               WALK-FORWARD TEST
                       ↓
              OUT-OF-SAMPLE RESULT
```

This is the core architecture.

---

# 46. Final recommendation for the team

Build the first version as a **research platform**, not a buy/sell engine.

The MVP should answer these questions for every fund:

1. **How is it performing now?**
2. **How does that compare with its own historical rolling behavior?**
3. **How does it compare with its peers?**
4. **How does it compare with its correct benchmark?**
5. **How often has it historically produced positive/benchmark-beating rolling returns?**
6. **What drawdowns occurred during those windows?**
7. **What is the current cost/friction?**
8. **When this same score was observed in the past, what happened over the following 1M and 3M?**

Only after answering those questions should we allow the system to produce a composite score.

The objective is therefore not:

```text
Find the highest 3M return.
```

It is:

```text
Find funds whose current strength is supported by
historical persistence + peer-relative strength +
benchmark-relative strength + acceptable risk +
reasonable friction, and validate the whole process
through walk-forward out-of-sample testing.
```

---

# Appendix A — Formula reference

### Simple return

```text
R_H(t) = NAV(t) / NAV(t-H) - 1
```

### Active return

```text
Active_H(t) = FundReturn_H(t) - BenchmarkReturn_H(t)
```

### N-observation rolling-window count

```text
Windows = M - N + 1
```

### N-observation window start

```text
StartIndex = EndIndex - (N - 1)
```

### Drawdown

```text
DD(t) = NAV(t) / max(NAV up to t) - 1
```

### Maximum drawdown

```text
MDD = min(DD(t))
```

### Current self-history percentile

```text
SHP = percentile_rank(current_return,
                      historical_rolling_returns)
```

### Peer percentile

```text
PeerPct = percentile_rank(fund_return,
                          peer_fund_returns_on_same_date)
```

---

# Appendix B — Source list

- AMFI — NAV History: https://www.amfiindia.com/sif/latest-nav/nav-history
- AMFI — NAV information: https://www.amfiindia.com/investor/knowledge-center-info?zoneName=NetAssetValueNAV
- AMFI — TER of MF Schemes: https://www.amfiindia.com/ter-of-mf-schemes
- AMFI — Expense Ratio: https://www.amfiindia.com/investor/knowledge-center-info?zoneName=expenseRatio
- SEBI — Mutual Fund filings: https://www.sebi.gov.in/filings/mutual-funds.html
- SEBI — Master Circular for Mutual Funds, 20 March 2026: https://www.sebi.gov.in/sebi_data/attachdocs/mar-2026/1774024028162.pdf
- MFAPI — API documentation: https://www.mfapi.in/docs/

---

# Appendix C — Status / decisions still requiring validation

These items should remain configurable until backtesting establishes what is useful:

```text
1. Calendar 3M vs fixed 90D as the primary short-term horizon
2. Exact peer-group taxonomy
3. Minimum fund-history requirements
4. Composite-score weights
5. RSI/SMA/MACD inclusion
6. Rebalancing frequency for the live strategy simulation
7. Treatment of overlapping evaluation windows
8. Historical availability of TER / exit-load metadata
9. Scheme merger/name-change continuity rules
10. Tax assumptions for the investor-specific net-return calculator
```

**Do not hardcode these as financial truths. Treat them as research parameters and validate them with out-of-sample testing.**
