# Out-of-Sample Hold-Out Evaluation Report (Rule Q14)

**Evaluation Timestamp:** 2026-09-18T19:50:43.142361+00:00  
**Evaluation Window:** 2024-01-01 to 2026-09-17 (Hold-Out Period)  
**Rule Q14 Adherence:** Touched strictly once after model parameters frozen.  

---

## 1. Executive Summary

| Hypothesis | Factor / Metric | Out-of-Sample Result | Statistical Significance | Verdict |
|---|---|---|---|---|
| **H1** | Peer-relative 3M Momentum | Mean Rank IC: `+0.0902` | HAC t-stat: `1.1` | **PARTIAL** |
| **H2** | Benchmark-Beat Persistence | Mean Rank IC: `+0.1049` | HAC t-stat: `1.06` | **PARTIAL** |
| **H3** | Own-History SHP Reversion | Mean Rank IC: `-0.0198` | HAC t-stat: `-0.22` | **PARTIAL_REVERSION** |
| **H4** | Net Excess vs Category Basket | Net Alpha: `-46.52%` p.a. | Hit Rate: `53.3%` | **NO_ALPHA** |
| **H5** | Fund Selection vs Timing | Selection Share: `0.0%` | Within Alpha: `-65.43%` | **PARTIAL** |

---

## 2. Quant Methodology & Falsification Rules Honored

1. **No Look-Ahead (Rule Q1):** Point-in-time calculation with data strictly $\le t$. SHP excludes $t$.
2. **TRI Benchmarks (Rule Q5):** Nifty 50 TRI, Nifty Midcap 150 TRI, Nifty Smallcap 250 TRI, Nifty 500 TRI with identical dates.
3. **Canonical Direct-Growth (Rule Q7):** IDCW excluded, 1 portfolio row per percentile (Rule Q8).
4. **Execution Friction (Rule Q11):** 1-day execution lag, 0.005% stamp duty, 0.20% exit load reserve deducted.
5. **Hold-out Touched Once (Rule Q14):** Logged permanently in this file and `experiments/registry.csv`.
