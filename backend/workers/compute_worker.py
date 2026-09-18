"""Batch compute worker for mutual fund quant analytics and scoring.

Calculates rolling returns, risk metrics, peer percentiles, SHP, and composite scores,
precomputing them into analytics.fund_summary and scoring.screener_snapshot.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date

import asyncpg
from questmf_quant.drawdown import max_drawdown
from questmf_quant.percentile import mid_rank_percentile, own_history_percentile
from questmf_quant.returns import (
    CanonicalCandidate,
    cagr,
    select_canonical_scheme,
    simple_return,
)
from questmf_quant.risk import (
    annualized_downside_deviation,
    annualized_volatility,
    beta_and_alpha,
    information_ratio,
    sharpe_ratio,
    sortino_ratio,
    tracking_error,
)
from questmf_quant.scoring import (
    DEFAULT_BASELINE_MODEL,
    assign_quadrant,
    compute_composite_score,
)

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("compute_worker")


async def run_compute_job() -> None:
    logger.info("Starting batch compute worker job...")
    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        # 1. Latest NAV date — needed before selection so canonical choice is
        #    staleness-aware (Rule Q4).
        latest_date_row = await conn.fetchrow(
            "SELECT MAX(nav_date) as max_d FROM market.nav_history;"
        )
        as_of_date: date = latest_date_row["max_d"] or date.today()

        # 2. Candidate canonical schemes with per-scheme NAV coverage. A single
        #    portfolio can map to several Direct-Growth scheme_codes (e.g.
        #    segregated side-pockets), and ingestion flags each canonical. Rule
        #    Q7 requires exactly one canonical series per portfolio, so collapse
        #    below with the tested select_canonical_scheme rule rather than
        #    letting an arbitrary (last-processed) scheme win fund_summary.
        candidate_rows = await conn.fetch("""
            SELECT DISTINCT s.scheme_code, s.portfolio_id, s.plan, s.option,
                   s.scheme_name, p.display_name as fund_name,
                   p.amc_id, a.name as amc_name,
                   COALESCE(c.category_id, 1) as category_id,
                   COALESCE(c.code, 'EQ_SMALL_CAP') as category_code,
                   st.last_nav_date, st.nav_points
            FROM ref.schemes s
            JOIN ref.portfolios p ON s.portfolio_id = p.portfolio_id
            JOIN ref.amcs a ON p.amc_id = a.amc_id
            LEFT JOIN ref.category_history ch ON p.portfolio_id = ch.portfolio_id
            LEFT JOIN ref.categories c ON ch.category_id = c.category_id
            LEFT JOIN (
                SELECT scheme_code, MAX(nav_date) AS last_nav_date, COUNT(*) AS nav_points
                FROM market.nav_history
                GROUP BY scheme_code
            ) st ON st.scheme_code = s.scheme_code
            WHERE s.is_canonical = true;
        """)

        if not candidate_rows:
            logger.warning("No canonical schemes found to compute.")
            return

        by_portfolio: dict[int, dict[int, asyncpg.Record]] = {}
        for r in candidate_rows:
            by_portfolio.setdefault(r["portfolio_id"], {})[r["scheme_code"]] = r

        schemes: list[asyncpg.Record] = []
        for rows_by_code in by_portfolio.values():
            chosen = select_canonical_scheme(
                [
                    CanonicalCandidate(
                        scheme_code=rr["scheme_code"],
                        plan=rr["plan"],
                        option=rr["option"],
                        last_nav_date=rr["last_nav_date"],
                        nav_points=rr["nav_points"] or 0,
                    )
                    for rr in rows_by_code.values()
                ],
                as_of=as_of_date,
            )
            if chosen is not None:
                schemes.append(rows_by_code[chosen])

        if not schemes:
            logger.warning("No canonical schemes with NAV data to compute.")
            return

        # 2b. Fetch benchmark history and portfolio benchmark mapping
        bench_rows = await conn.fetch(
            "SELECT benchmark_id, value_date, value FROM market.benchmark_values ORDER BY value_date ASC;"
        )
        bench_data: dict[int, dict[date, float]] = {}
        for br in bench_rows:
            bench_data.setdefault(br["benchmark_id"], {})[br["value_date"]] = float(br["value"])

        bm_mappings = await conn.fetch(
            "SELECT portfolio_id, benchmark_id FROM ref.benchmark_history WHERE tier = 1;"
        )
        portfolio_bench_map = {r["portfolio_id"]: r["benchmark_id"] for r in bm_mappings}

        fund_metrics: dict[int, dict] = {}

        # 3. For each canonical fund, fetch NAV series and compute individual metrics
        for s in schemes:
            pid = s["portfolio_id"]
            code = s["scheme_code"]

            nav_rows = await conn.fetch(
                """
                SELECT nav_date, nav
                FROM market.nav_history
                WHERE scheme_code = $1
                ORDER BY nav_date ASC;
            """,
                code,
            )

            if len(nav_rows) < 30:
                continue

            navs = [float(r["nav"]) for r in nav_rows]
            dates = [r["nav_date"] for r in nav_rows]

            # Daily returns
            daily_returns = [(navs[i] / navs[i - 1]) - 1.0 for i in range(1, len(navs))]

            # Risk metrics
            vol = annualized_volatility(daily_returns)
            downside = annualized_downside_deviation(daily_returns)
            shp = sharpe_ratio(daily_returns, annual_rf=0.065)
            sortino = sortino_ratio(daily_returns, annual_rf=0.065)
            mdd, _, _ = max_drawdown(navs)

            # Rolling returns
            r_1m = simple_return(navs[-22], navs[-1]) if len(navs) >= 22 else 0.0
            r_3m = simple_return(navs[-65], navs[-1]) if len(navs) >= 65 else 0.0
            r_6m = simple_return(navs[-130], navs[-1]) if len(navs) >= 130 else 0.0
            r_1y = simple_return(navs[-252], navs[-1]) if len(navs) >= 252 else 0.0

            days_span = float((dates[-1] - dates[0]).days)
            c_3y = cagr(navs[0], navs[-1], days=days_span) if days_span >= 365.0 else r_1y

            # Trailing 3M rolling distribution for SHP
            # Sample rolling 3M returns over past 2 years (approx 500 days)
            rolling_3m_history: list[float] = []
            if len(navs) >= 65:
                for idx in range(65, len(navs), 10):
                    rolling_3m_history.append((navs[idx] / navs[idx - 65]) - 1.0)

            # Rule Q1: SHP excludes current t
            shp_3m = (
                own_history_percentile(r_3m, rolling_3m_history[:-1])
                if len(rolling_3m_history) > 1
                else 50.0
            )

            # Rule Q5: Real benchmark TRI metrics with identical dates
            bench_id = portfolio_bench_map.get(pid, 2)  # default to NIFTY 500 TRI (2)
            bench_series = bench_data.get(bench_id, {})

            aligned_nav = []
            aligned_bench = []
            for r in nav_rows:
                d = r["nav_date"]
                if d in bench_series:
                    aligned_nav.append(float(r["nav"]))
                    aligned_bench.append(bench_series[d])

            if len(aligned_nav) >= 30:
                f_rets = [
                    (aligned_nav[i] / aligned_nav[i - 1]) - 1.0 for i in range(1, len(aligned_nav))
                ]
                b_rets = [
                    (aligned_bench[i] / aligned_bench[i - 1]) - 1.0
                    for i in range(1, len(aligned_bench))
                ]
                beta, alpha = beta_and_alpha(f_rets, b_rets, periods_per_year=252, annual_rf=0.065)
                te = tracking_error(f_rets, b_rets, periods_per_year=252)

                if len(f_rets) >= 756:
                    ir_3y = information_ratio(f_rets[-756:], b_rets[-756:], periods_per_year=252)
                else:
                    ir_3y = information_ratio(f_rets, b_rets, periods_per_year=252)

                # 3M Alpha: identical start and end dates
                if len(aligned_nav) >= 65:
                    r_f_3m = (aligned_nav[-1] / aligned_nav[-65]) - 1.0
                    r_b_3m = (aligned_bench[-1] / aligned_bench[-65]) - 1.0
                    alpha_3m = r_f_3m - r_b_3m
                else:
                    alpha_3m = 0.0
            else:
                beta, _alpha, te, ir_3y, alpha_3m = 1.0, 0.0, 0.0, 0.0, 0.0

            risk_payload = {
                "volatility_ann": round(vol * 100, 2) if vol is not None else None,
                "downside_dev_ann": round(downside * 100, 2) if downside is not None else None,
                "sharpe_ratio": round(shp, 2) if shp is not None else None,
                "sortino_ratio": round(sortino, 2) if sortino is not None else None,
                "max_drawdown": round(mdd * 100, 2) if mdd is not None else None,
                "cagr_3y": round(c_3y * 100, 2) if c_3y is not None else None,
                "observations": len(daily_returns),
                "alpha_3m": round(alpha_3m * 100, 2) if alpha_3m is not None else None,
                "ir_3y": round(ir_3y, 2) if ir_3y is not None else None,
                "beta": round(beta, 2) if beta is not None else None,
                "tracking_error": round(te * 100, 2) if te is not None else None,
            }

            # Upsert into analytics.fund_summary
            await conn.execute(
                """
                INSERT INTO analytics.fund_summary (portfolio_id, as_of_date, payload, updated_at)
                VALUES ($1, $2, $3::jsonb, now())
                ON CONFLICT (portfolio_id) DO UPDATE
                SET as_of_date = EXCLUDED.as_of_date,
                    payload = EXCLUDED.payload,
                    updated_at = now();
            """,
                pid,
                as_of_date,
                json.dumps(risk_payload),
            )

            fund_metrics[pid] = {
                "scheme": s,
                "r_1m": r_1m,
                "r_3m": r_3m,
                "r_6m": r_6m,
                "r_1y": r_1y,
                "cagr_3y": c_3y,
                "vol": vol,
                "mdd": mdd,
                "shp_3m": shp_3m,
                "alpha_3m": alpha_3m,
                "ir_3y": ir_3y if ir_3y is not None else 0.0,
                "beta": beta,
                "obs_count": len(daily_returns),
            }

        # 4. Peer percentiles per category (Rule Q8: minimum 8 peers or null)
        category_funds: dict[int, list[int]] = {}
        for pid, m in fund_metrics.items():
            cat_id = m["scheme"]["category_id"]
            category_funds.setdefault(cat_id, []).append(pid)

        for cat_id, pids in category_funds.items():
            category_returns = [fund_metrics[p]["r_3m"] for p in pids]

            for pid in pids:
                m = fund_metrics[pid]
                peer_pct = mid_rank_percentile(m["r_3m"], category_returns)
                m["peer_pct_3m"] = peer_pct

                quadrant = assign_quadrant(peer_pct, m["shp_3m"])

                factor_scores = {
                    "momentum": min(100.0, max(0.0, 50.0 + m["r_3m"] * 250.0)),
                    "persistence": m["shp_3m"],
                    "quality": min(100.0, max(0.0, 50.0 + m["ir_3y"] * 25.0)),
                    "risk": min(100.0, max(0.0, 100.0 + (m["mdd"] or 0.0) * 200.0)),
                    "cost": 75.0,
                }
                composite, conf = compute_composite_score(
                    factor_scores, DEFAULT_BASELINE_MODEL, obs_count=m["obs_count"]
                )

                s = m["scheme"]
                await conn.execute(
                    """
                    INSERT INTO scoring.screener_snapshot (
                        as_of_date, model_version, category_id, portfolio_id, fund_name, amc,
                        ret_1m, ret_3m, ret_6m, ret_1y, cagr_3y, shp_3m, peer_pct_3m, alpha_3m,
                        ir_3y, mdd_3y, ter, exit_load_rate, exit_load_days, composite, confidence, quadrant, flags, investable
                    ) VALUES (
                        $1, 'v1_baseline', $2, $3, $4, $5,
                        $6, $7, $8, $9, $10, $11, $12, $13,
                        $14, $15, 0.007, 0.01, 365, $16, $17, $18, 0, true
                    )
                    ON CONFLICT (as_of_date, model_version, category_id, portfolio_id) DO UPDATE
                    SET composite = EXCLUDED.composite,
                        peer_pct_3m = EXCLUDED.peer_pct_3m,
                        shp_3m = EXCLUDED.shp_3m,
                        quadrant = EXCLUDED.quadrant,
                        confidence = EXCLUDED.confidence;
                """,
                    as_of_date,
                    cat_id,
                    pid,
                    s["fund_name"],
                    s["amc_name"],
                    m["r_1m"],
                    m["r_3m"],
                    m["r_6m"],
                    m["r_1y"],
                    m["cagr_3y"],
                    m["shp_3m"],
                    peer_pct,
                    m["alpha_3m"],
                    m["ir_3y"],
                    m["mdd"],
                    composite,
                    conf,
                    quadrant,
                )

        # 5. Update scoring.latest
        await conn.execute(
            """
            INSERT INTO scoring.latest (model_version, as_of_date, published_at)
            VALUES ('v1_baseline', $1, now())
            ON CONFLICT (model_version) DO UPDATE
            SET as_of_date = EXCLUDED.as_of_date, published_at = now();
        """,
            as_of_date,
        )

        logger.info("Batch compute worker completed successfully.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_compute_job())
