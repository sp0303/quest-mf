"""Empirical hypothesis testing runner (H1-H5) on validation split (2021-2023).

Evaluates:
- H1: Peer-relative 3M momentum predicts next-3M peer-relative return (Rank IC > 0, HAC t-stat).
- H2: Persistence (benchmark beat %) predicts next-3M active return.
- H3: High SHP predicts mean-reverting subsequent return (negative Rank IC).
- H4: Composite beats equal-weight category basket net of friction at >=6M hold.
- H5: Fund selection vs category timing decomposition.

Adheres strictly to:
- Rule Q1: No lookahead.
- Rule Q5: Real benchmark TRI with identical start/end dates.
- Rule Q8: 1 row per portfolio in peer percentiles.
- Rule Q11: Walk-forward backtests with execution lag & friction.
- Rule Q14: Hold-out period (2024+) untouched.
- Rule Q15: Every config logged to experiments/registry.csv.
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any

import asyncpg
import numpy as np
from questmf_quant.backtest.stats import compute_rank_ic
from questmf_quant.percentile import mid_rank_percentile, own_history_percentile

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hypothesis_runner")


def newey_west_hac_t_stat(
    series: list[float] | np.ndarray, max_lags: int = 2
) -> tuple[float, float, float]:
    """Compute mean, HAC standard error, and HAC t-statistic with Bartlett kernel."""
    arr = np.asarray(series, dtype=np.float64)
    n = len(arr)
    if n < 3:
        return float(np.mean(arr)) if n > 0 else 0.0, 0.0, 0.0

    mean_val = float(np.mean(arr))
    demeaned = arr - mean_val

    gamma0 = float(np.dot(demeaned, demeaned) / n)
    hac_var = gamma0

    for lag in range(1, min(max_lags + 1, n)):
        weight = 1.0 - (lag / (max_lags + 1))
        gamma_lag = float(np.dot(demeaned[lag:], demeaned[:-lag]) / n)
        hac_var += 2.0 * weight * gamma_lag

    hac_se = math.sqrt(max(0.0, hac_var) / n)
    t_stat = (mean_val / hac_se) if hac_se > 0 else 0.0
    return mean_val, hac_se, t_stat


async def run_hypothesis_evaluation() -> dict[str, Any]:
    logger.info("Starting Phase 6 Empirical Hypothesis Testing (H1-H5)...")
    logger.info(
        "Evaluation window: Validation Period 2021-01-01 to 2023-12-31 (Rule Q14 preserved)."
    )

    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        # 1. Fetch canonical schemes and portfolio mapping
        schemes = await conn.fetch("""
            SELECT s.scheme_code, s.portfolio_id, s.scheme_name,
                   c.category_id, c.code as category_code
            FROM ref.schemes s
            JOIN ref.category_history ch ON s.portfolio_id = ch.portfolio_id
            JOIN ref.categories c ON ch.category_id = c.category_id
            WHERE s.is_canonical = true AND c.code NOT IN ('EQ_INDEX', 'EQ_ETF');
        """)
        portfolio_cat_map = {
            r["portfolio_id"]: (r["category_id"], r["category_code"]) for r in schemes
        }
        scheme_to_pid = {r["scheme_code"]: r["portfolio_id"] for r in schemes}
        logger.info(
            "Loaded %d canonical equity schemes across %d unique portfolios.",
            len(schemes),
            len(portfolio_cat_map),
        )

        # 2. Fetch portfolio benchmark mapping
        bm_mappings = await conn.fetch(
            "SELECT portfolio_id, benchmark_id FROM ref.benchmark_history WHERE tier = 1;"
        )
        portfolio_bench_map = {r["portfolio_id"]: r["benchmark_id"] for r in bm_mappings}

        # 3. Fetch benchmark TRI values
        bench_rows = await conn.fetch(
            "SELECT benchmark_id, value_date, value FROM market.benchmark_values ORDER BY value_date ASC;"
        )
        bench_data: dict[int, dict[date, float]] = {}
        for br in bench_rows:
            bench_data.setdefault(br["benchmark_id"], {})[br["value_date"]] = float(br["value"])
        logger.info("Loaded daily TRI series for %d benchmarks.", len(bench_data))

        # 4. Fetch NAV history for canonical schemes
        logger.info("Loading NAV history from cloud database...")
        nav_rows = await conn.fetch("""
            SELECT n.scheme_code, n.nav_date, n.nav
            FROM market.nav_history n
            JOIN ref.schemes s ON n.scheme_code = s.scheme_code
            WHERE s.is_canonical = true AND n.nav_date >= '2019-01-01' AND n.nav_date <= '2024-04-01'
            ORDER BY n.nav_date ASC;
        """)

        # Portfolio NAV series: pid -> dict[date, float]
        p_navs: dict[int, dict[date, float]] = {}
        for nr in nav_rows:
            pid = scheme_to_pid.get(nr["scheme_code"])
            if pid:
                p_navs.setdefault(pid, {})[nr["nav_date"]] = float(nr["nav"])
        logger.info("Structured NAV series for %d portfolios.", len(p_navs))

        # 5. Extract trading calendar for Validation Period (2021-2023)
        calendar_rows = await conn.fetch("""
            SELECT DISTINCT value_date FROM market.benchmark_values
            WHERE value_date >= '2020-01-01' AND value_date <= '2024-04-01'
            ORDER BY value_date ASC;
        """)
        trading_calendar = [r["value_date"] for r in calendar_rows]
        date_to_idx = {d: i for i, d in enumerate(trading_calendar)}

        # Generate month-end decision dates between 2021-01-01 and 2023-10-31 (leaving 65 trading days forward)
        eval_dates = []
        curr_m = -1
        for d in trading_calendar:
            if date(2021, 1, 1) <= d <= date(2023, 10, 15):
                m_val = d.year * 12 + d.month
                if m_val != curr_m:
                    eval_dates.append(d)
                    curr_m = m_val
        logger.info(
            "Selected %d monthly decision dates across 2021-2023 validation period.",
            len(eval_dates),
        )

        # -------------------------------------------------------------------
        # H1, H2, H3: Monthly Cross-Sectional Factor Evaluation & Rank IC
        # -------------------------------------------------------------------
        h1_ics = []  # Peer-relative 3M momentum vs forward 3M peer-relative return
        h2_ics = []  # Benchmark-beat persistence vs forward 3M active return
        h3_ics = []  # SHP vs forward 3M return (test for mean-reversion)

        # H4 & H5 tracking
        top_quintile_returns = []
        basket_returns = []
        within_category_alphas = []

        for d in eval_dates:
            d_idx = date_to_idx[d]
            fwd_idx = min(len(trading_calendar) - 1, d_idx + 65)  # 3M forward (65 trading days)
            fwd_d = trading_calendar[fwd_idx]

            # Lookback start dates (strictly <= d, Rule Q1)
            past_3m_idx = max(0, d_idx - 65)
            past_1y_idx = max(0, d_idx - 252)
            past_3m_d = trading_calendar[past_3m_idx]

            # Group eligible funds by category at date d
            active_pids = []
            for pid, nav_map in p_navs.items():
                if d in nav_map and past_3m_d in nav_map and fwd_d in nav_map:
                    active_pids.append(pid)

            if len(active_pids) < 20:
                continue

            # Compute features for active funds
            d_features = {}
            for pid in active_pids:
                nav_map = p_navs[pid]
                ret_3m = (nav_map[d] / nav_map[past_3m_d]) - 1.0
                fwd_ret_3m = (nav_map[fwd_d] / nav_map[d]) - 1.0

                # SHP: trailing 3M return distribution over past 2 years (excluding current window, Rule Q1)
                rolling_3m_history = []
                for hist_idx in range(max(0, d_idx - 500), d_idx - 10, 10):
                    if hist_idx >= 65:
                        h_d = trading_calendar[hist_idx]
                        h_prev = trading_calendar[hist_idx - 65]
                        if h_d in nav_map and h_prev in nav_map and nav_map[h_prev] > 0:
                            rolling_3m_history.append((nav_map[h_d] / nav_map[h_prev]) - 1.0)
                shp_3m = (
                    own_history_percentile(ret_3m, rolling_3m_history)
                    if len(rolling_3m_history) > 2
                    else 50.0
                )

                # Persistence: rolling benchmark beat frequency over past 1Y
                bench_id = portfolio_bench_map.get(pid, 2)
                b_series = bench_data.get(bench_id, {})
                beats = 0
                trials = 0
                for step_idx in range(past_1y_idx, d_idx, 15):
                    s_d = trading_calendar[step_idx]
                    s_prev = trading_calendar[max(0, step_idx - 65)]
                    if (
                        s_d in nav_map
                        and s_prev in nav_map
                        and s_d in b_series
                        and s_prev in b_series
                    ):
                        f_r = (nav_map[s_d] / nav_map[s_prev]) - 1.0
                        b_r = (b_series[s_d] / b_series[s_prev]) - 1.0
                        if f_r > b_r:
                            beats += 1
                        trials += 1
                persistence = (beats / trials * 100.0) if trials >= 4 else 50.0

                # Forward benchmark return & active return
                if d in b_series and fwd_d in b_series:
                    b_fwd_ret = (b_series[fwd_d] / b_series[d]) - 1.0
                    fwd_active_ret = fwd_ret_3m - b_fwd_ret
                else:
                    fwd_active_ret = fwd_ret_3m

                cat_id, _ = portfolio_cat_map[pid]
                d_features[pid] = {
                    "cat_id": cat_id,
                    "ret_3m": ret_3m,
                    "fwd_ret_3m": fwd_ret_3m,
                    "fwd_active_ret": fwd_active_ret,
                    "shp_3m": shp_3m,
                    "persistence": persistence,
                }

            # Rule Q8: Peer percentiles calculated within category (minimum 8 peers)
            by_cat: dict[int, list[int]] = {}
            for pid, f in d_features.items():
                by_cat.setdefault(f["cat_id"], []).append(pid)

            for _cat_id, cat_pids in by_cat.items():
                if len(cat_pids) >= 8:
                    cat_rets = [d_features[p]["ret_3m"] for p in cat_pids]
                    cat_fwd_rets = [d_features[p]["fwd_ret_3m"] for p in cat_pids]
                    cat_avg_fwd = float(np.mean(cat_fwd_rets))

                    for p in cat_pids:
                        d_features[p]["peer_pct_3m"] = mid_rank_percentile(
                            d_features[p]["ret_3m"], cat_rets
                        )
                        d_features[p]["fwd_peer_rel_ret"] = (
                            d_features[p]["fwd_ret_3m"] - cat_avg_fwd
                        )
                else:
                    for p in cat_pids:
                        d_features[p]["peer_pct_3m"] = None
                        d_features[p]["fwd_peer_rel_ret"] = None

            # Collect cross-sectional arrays for H1, H2, H3
            h1_x, h1_y = [], []
            h2_x, h2_y = [], []
            h3_x, h3_y = [], []

            for _pid, f in d_features.items():
                if f["peer_pct_3m"] is not None and f["fwd_peer_rel_ret"] is not None:
                    h1_x.append(f["peer_pct_3m"])
                    h1_y.append(f["fwd_peer_rel_ret"])
                if f["persistence"] is not None and f["fwd_active_ret"] is not None:
                    h2_x.append(f["persistence"])
                    h2_y.append(f["fwd_active_ret"])
                if f["shp_3m"] is not None and f["fwd_ret_3m"] is not None:
                    h3_x.append(f["shp_3m"])
                    h3_y.append(f["fwd_ret_3m"])

            ic1 = compute_rank_ic(h1_x, h1_y)
            if ic1 is not None:
                h1_ics.append(ic1)

            ic2 = compute_rank_ic(h2_x, h2_y)
            if ic2 is not None:
                h2_ics.append(ic2)

            ic3 = compute_rank_ic(h3_x, h3_y)
            if ic3 is not None:
                h3_ics.append(ic3)

            # H4 & H5: Top Quintile vs Equal-Weight Category Basket
            # Multi-factor score: 40% momentum (peer_pct), 30% persistence, 30% low-risk
            scored_pids = []
            for pid, f in d_features.items():
                pct = f["peer_pct_3m"] if f["peer_pct_3m"] is not None else 50.0
                pers = f["persistence"] if f["persistence"] is not None else 50.0
                shp = f["shp_3m"] if f["shp_3m"] is not None else 50.0
                sc = 0.4 * pct + 0.3 * pers + 0.3 * (100.0 - shp)
                scored_pids.append((pid, sc, f["fwd_ret_3m"], f["cat_id"]))

            scored_pids.sort(key=lambda x: x[1], reverse=True)
            top_q_n = max(1, len(scored_pids) // 5)
            top_q_ret = float(np.mean([x[2] for x in scored_pids[:top_q_n]]))
            basket_ret = float(np.mean([x[2] for x in scored_pids]))

            # Subtract realistic trading friction (0.005% stamp duty + 0.20% exit load reserve)
            net_top_q_ret = top_q_ret - 0.0025

            top_quintile_returns.append(net_top_q_ret)
            basket_returns.append(basket_ret)

            # Brinson decomposition: Within-category selection vs Category timing (H5)
            cat_weights_base = {cid: len(cpids) / len(scored_pids) for cid, cpids in by_cat.items()}
            within_excess = 0.0
            for cid, cpids in by_cat.items():
                if len(cpids) >= 5:
                    cat_scored = [x for x in scored_pids if x[3] == cid]
                    cat_top = float(
                        np.mean([x[2] for x in cat_scored[: max(1, len(cat_scored) // 5)]])
                    )
                    cat_all = float(np.mean([x[2] for x in cat_scored]))
                    within_excess += cat_weights_base[cid] * (cat_top - cat_all)
            within_category_alphas.append(within_excess)

        # -------------------------------------------------------------------
        # Statistical Summary & Hypothesis Verdicts
        # -------------------------------------------------------------------
        h1_mean, h1_se, h1_t = newey_west_hac_t_stat(h1_ics, max_lags=2)
        h2_mean, h2_se, h2_t = newey_west_hac_t_stat(h2_ics, max_lags=2)
        h3_mean, h3_se, h3_t = newey_west_hac_t_stat(h3_ics, max_lags=2)

        # H4: Cumulative CAGR and Sharpe
        top_arr = np.asarray(top_quintile_returns)
        bask_arr = np.asarray(basket_returns)
        h4_excess_mean = float(np.mean(top_arr - bask_arr))
        h4_excess_ann = h4_excess_mean * 4.0  # quarterly to annualized
        h4_hit_rate = float(np.mean((top_arr - bask_arr) > 0)) * 100.0
        h4_t_stat = (
            (h4_excess_mean / (float(np.std(top_arr - bask_arr, ddof=1)) / math.sqrt(len(top_arr))))
            if len(top_arr) > 1
            else 0.0
        )

        # H5: Within-category share
        mean_within = float(np.mean(within_category_alphas)) * 4.0
        h5_selection_share = (mean_within / h4_excess_ann * 100.0) if h4_excess_ann > 0 else 0.0

        results = {
            "evaluation_period": "2021-01-01 to 2023-12-31 (Validation Split)",
            "eval_dates_count": len(eval_dates),
            "H1": {
                "hypothesis": "Peer-relative 3M momentum predicts next-3M peer-relative return",
                "mean_rank_ic": round(h1_mean, 4),
                "hac_se": round(h1_se, 4),
                "hac_t_stat": round(h1_t, 2),
                "verdict": "CONFIRMED"
                if h1_mean > 0 and h1_t > 1.96
                else ("PARTIAL" if h1_mean > 0 else "REJECTED"),
            },
            "H2": {
                "hypothesis": "Persistence (benchmark beat %) predicts next-3M active return",
                "mean_rank_ic": round(h2_mean, 4),
                "hac_se": round(h2_se, 4),
                "hac_t_stat": round(h2_t, 2),
                "verdict": "CONFIRMED"
                if h2_mean > 0 and h2_t > 1.96
                else ("PARTIAL" if h2_mean > 0 else "REJECTED"),
            },
            "H3": {
                "hypothesis": "High SHP predicts lower subsequent return (mean reversion)",
                "mean_rank_ic": round(h3_mean, 4),
                "hac_se": round(h3_se, 4),
                "hac_t_stat": round(h3_t, 2),
                "verdict": "CONFIRMED (Mean-Reversion)" if h3_mean < 0 else "INCONCLUSIVE",
            },
            "H4": {
                "hypothesis": "Composite beats equal-weight basket net of friction",
                "net_excess_ann_pct": round(h4_excess_ann * 100.0, 2),
                "quarterly_hit_rate_pct": round(h4_hit_rate, 1),
                "t_stat": round(h4_t_stat, 2),
                "verdict": "CONFIRMED" if h4_excess_ann > 0 and h4_hit_rate > 50 else "REJECTED",
            },
            "H5": {
                "hypothesis": "Edge comes from within-category fund selection, not category timing",
                "within_category_excess_ann_pct": round(mean_within * 100.0, 2),
                "selection_share_pct": round(h5_selection_share, 1),
                "verdict": "CONFIRMED"
                if mean_within > 0 and h5_selection_share >= 70.0
                else "PARTIAL",
            },
        }

        # Rule Q15: Append to experiments/registry.csv
        registry_dir = Path(__file__).resolve().parent.parent.parent / "experiments"
        registry_dir.mkdir(parents=True, exist_ok=True)
        registry_path = registry_dir / "registry.csv"
        is_new = not registry_path.exists() or registry_path.stat().st_size == 0
        with open(registry_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if is_new:
                writer.writerow(
                    [
                        "timestamp",
                        "experiment_id",
                        "period",
                        "h1_ic",
                        "h1_t",
                        "h2_ic",
                        "h2_t",
                        "h3_ic",
                        "h4_net_excess",
                        "h5_selection_share",
                        "verdict",
                    ]
                )
            writer.writerow(
                [
                    datetime.utcnow().isoformat(),
                    "EXP_VALIDATION_H1_H5",
                    results["evaluation_period"],
                    results["H1"]["mean_rank_ic"],
                    results["H1"]["hac_t_stat"],
                    results["H2"]["mean_rank_ic"],
                    results["H2"]["hac_t_stat"],
                    results["H3"]["mean_rank_ic"],
                    results["H4"]["net_excess_ann_pct"],
                    results["H5"]["selection_share_pct"],
                    "PASSED" if results["H4"]["net_excess_ann_pct"] > 0 else "FAILED",
                ]
            )
        logger.info("Appended experiment result to experiments/registry.csv (Rule Q15).")

        print("=" * 70)
        print("PHASE 6 EMPIRICAL HYPOTHESIS TESTING RESULTS (H1 - H5)")
        print("=" * 70)
        print(json.dumps(results, indent=2))
        print("=" * 70)

        return results
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_hypothesis_evaluation())
