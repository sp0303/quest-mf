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
from questmf_quant.calendar.windows import (
    find_boundary_nav_date,
    resolve_calendar_start_date,
)
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
    ModelConfig,
    assign_quadrant,
    compute_composite_score,
)

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("compute_worker")

# Rule Q4/Q12: a fund whose latest canonical NAV is older than this as of the run
# date has no current data to score. It must be dropped from the active screener
# (INSUFFICIENT_HISTORY), never scored off stale values.
MAX_SNAPSHOT_STALENESS_DAYS = 30
MAX_WINDOW_STALENESS_DAYS = 7


async def run_compute_job() -> None:
    logger.info("Starting batch compute worker job...")
    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        # 1. Latest NAV date — needed before selection so canonical choice is staleness-aware (Rule Q4).
        latest_date_row = await conn.fetchrow(
            "SELECT MAX(nav_date) as max_d FROM market.nav_history;"
        )
        as_of_date: date = latest_date_row["max_d"] or date.today()

        # 2. Candidate canonical schemes strictly within MVP universe scope (Spec §6.1, §6.2, §7.1).
        #    - Active open-ended equity schemes only
        #    - Exclude ETFs, Index funds, Debt, Liquid, FoFs, and Overseas/Commodity funds
        #    - Point-in-time category resolution (Rule Q2): as_of_date BETWEEN valid_from AND valid_to
        #    - Never default unmapped funds to EQ_SMALL_CAP
        candidate_rows = await conn.fetch(
            """
            SELECT DISTINCT s.scheme_code, s.portfolio_id, s.plan, s.option,
                   s.scheme_name, p.display_name as fund_name,
                   p.amc_id, a.name as amc_name,
                   c.category_id,
                   c.code as category_code,
                   st.last_nav_date, st.nav_points
            FROM ref.schemes s
            JOIN ref.portfolios p ON s.portfolio_id = p.portfolio_id
            JOIN ref.amcs a ON p.amc_id = a.amc_id
            JOIN ref.category_history ch ON p.portfolio_id = ch.portfolio_id
                AND $1 BETWEEN ch.valid_from AND ch.valid_to
            JOIN ref.categories c ON ch.category_id = c.category_id
                AND c.asset_class = 'EQUITY'
                AND c.code NOT IN ('EQ_ETF', 'EQ_INDEX')
            LEFT JOIN (
                SELECT scheme_code, MAX(nav_date) AS last_nav_date, COUNT(*) AS nav_points
                FROM market.nav_history
                GROUP BY scheme_code
            ) st ON st.scheme_code = s.scheme_code
            WHERE s.is_canonical = true
              AND s.status = 'ACTIVE'
              AND p.closed_date IS NULL
              AND p.display_name NOT ILIKE '%Fund of Fund%'
              AND p.display_name NOT ILIKE '%FoF%'
              AND p.display_name NOT ILIKE '%Overseas%'
              AND p.display_name NOT ILIKE '%Taiwan%'
              AND p.display_name NOT ILIKE '%Silver%'
              AND p.display_name NOT ILIKE '%Gold%'
              -- Debt funds miscategorised as equity in category_history (data fix
              -- pending in ingestion); exclude by name so the screener stays equity.
              AND p.display_name NOT ILIKE '%Liquid%'
              AND p.display_name NOT ILIKE '%Debt%'
              AND p.display_name NOT ILIKE '%Gilt%'
              AND p.display_name NOT ILIKE '%Bond%'
              AND p.display_name NOT ILIKE '%Money Market%'
              AND p.display_name NOT ILIKE '%Overnight%'
              AND p.display_name NOT ILIKE '%Banking & PSU%'
              AND p.display_name NOT ILIKE '%Credit Risk%'
              AND p.display_name NOT ILIKE '%Ultra Short%'
              AND p.display_name NOT ILIKE '%Short Duration%'
              AND p.display_name NOT ILIKE '%Low Duration%'
              AND p.display_name NOT ILIKE '%Floater%';
            """,
            as_of_date,
        )

        if not candidate_rows:
            logger.warning("No in-scope canonical equity schemes found to compute.")
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

        # 2c. Load active model configuration from scoring.model_versions (Rule Q13)
        model_row = await conn.fetchrow(
            """
            SELECT model_version, config
            FROM scoring.model_versions
            WHERE is_default = true
            LIMIT 1;
            """
        )
        # compute_composite_score needs a ModelConfig, not a raw dict. Build one
        # from the stored config (Rule Q13), falling back to the baseline model.
        if model_row and model_row["config"]:
            raw_config = model_row["config"]
            cfg_dict = json.loads(raw_config) if isinstance(raw_config, str) else dict(raw_config)
            active_model_version = model_row["model_version"]
            active_model_config = ModelConfig(
                version=active_model_version,
                weights=cfg_dict.get("weights", DEFAULT_BASELINE_MODEL.weights),
                min_obs_required=cfg_dict.get(
                    "min_obs_required", DEFAULT_BASELINE_MODEL.min_obs_required
                ),
            )
        else:
            active_model_version = DEFAULT_BASELINE_MODEL.version
            active_model_config = DEFAULT_BASELINE_MODEL

        fund_metrics: dict[int, dict] = {}
        excluded_stale: list[int] = []

        # 3. For each canonical fund, compute rolling returns & risk metrics
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

            nav_by_date = {r["nav_date"]: float(r["nav"]) for r in nav_rows}
            dates = sorted(nav_by_date.keys())
            end_date = dates[-1]
            end_nav = nav_by_date[end_date]

            # Rule Q4/Q12: skip funds whose latest NAV is stale as of the run date.
            if (as_of_date - end_date).days > MAX_SNAPSHOT_STALENESS_DAYS:
                excluded_stale.append(pid)
                continue

            navs = [nav_by_date[d] for d in dates]

            # Daily returns for volatility and risk
            daily_returns = [(navs[i] / navs[i - 1]) - 1.0 for i in range(1, len(navs))]

            # Risk metrics
            vol = annualized_volatility(daily_returns)
            downside = annualized_downside_deviation(daily_returns)
            shp = sharpe_ratio(daily_returns, annual_rf=0.065)
            sortino = sortino_ratio(daily_returns, annual_rf=0.065)
            mdd, _, _ = max_drawdown(navs)

            # Rule Q3/Q4/Q12: Pure calendar-window returns with EOM clipping and boundary rule
            def get_cal_return(months: int) -> float | None:
                target_start = resolve_calendar_start_date(end_date, months)
                start_d = find_boundary_nav_date(
                    target_start, dates, max_staleness_days=MAX_WINDOW_STALENESS_DAYS
                )
                if start_d is None:
                    return None
                start_n = nav_by_date[start_d]
                if months >= 12:
                    span_days = float((end_date - start_d).days)
                    return cagr(start_n, end_nav, days=span_days) if span_days >= 365.0 else None
                return simple_return(start_n, end_nav)

            r_1m = get_cal_return(1)
            r_3m = get_cal_return(3)
            r_6m = get_cal_return(6)
            r_1y = get_cal_return(12)
            c_3y = get_cal_return(36)

            # Rule Q1: Trailing 3M rolling distribution for SHP, excluding current t
            rolling_3m_history: list[float] = []
            if len(dates) > 65:
                max_step_back = min(len(dates) - 1, 500)
                for step in range(10, max_step_back, 10):
                    hist_end_idx = len(dates) - 1 - step
                    if hist_end_idx < 0:
                        break
                    hist_end_d = dates[hist_end_idx]
                    hist_target_start = resolve_calendar_start_date(hist_end_d, 3)
                    hist_start_d = find_boundary_nav_date(
                        hist_target_start, dates[: hist_end_idx + 1], max_staleness_days=MAX_WINDOW_STALENESS_DAYS
                    )
                    if hist_start_d is not None and hist_start_d in nav_by_date:
                        rolling_3m_history.append(
                            simple_return(nav_by_date[hist_start_d], nav_by_date[hist_end_d])
                        )

            shp_3m = (
                own_history_percentile(r_3m, rolling_3m_history)
                if (r_3m is not None and len(rolling_3m_history) >= 8)
                else None
            )

            # Rule Q5: Real benchmark TRI metrics with identical dates
            bench_id = portfolio_bench_map.get(pid, 2)  # default to NIFTY 500 TRI (2)
            bench_series = bench_data.get(bench_id, {})

            aligned_nav = []
            aligned_bench = []
            aligned_dates = []
            for d in dates:
                if d in bench_series:
                    aligned_dates.append(d)
                    aligned_nav.append(nav_by_date[d])
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

                # 3M Alpha: identical start and end dates via calendar engine
                target_3m_start = resolve_calendar_start_date(end_date, 3)
                start_3m_d = find_boundary_nav_date(
                    target_3m_start, aligned_dates, max_staleness_days=MAX_WINDOW_STALENESS_DAYS
                )
                if (
                    start_3m_d is not None
                    and start_3m_d in bench_series
                    and end_date in bench_series
                    and start_3m_d in nav_by_date
                ):
                    f_ret_3m = (nav_by_date[end_date] / nav_by_date[start_3m_d]) - 1.0
                    b_ret_3m = (bench_series[end_date] / bench_series[start_3m_d]) - 1.0
                    alpha_3m = f_ret_3m - b_ret_3m
                else:
                    alpha_3m = None
            else:
                beta, _alpha, te, ir_3y, alpha_3m = 1.0, None, None, None, None

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
                "ir_3y": ir_3y,
                "beta": beta,
                "obs_count": len(daily_returns),
            }

        # 4. Peer percentiles per category (Rule Q8: minimum 8 peers or null)
        category_funds: dict[int, list[int]] = {}
        for pid, m in fund_metrics.items():
            cat_id = m["scheme"]["category_id"]
            if m["r_3m"] is not None:
                category_funds.setdefault(cat_id, []).append(pid)

        for cat_id, pids in category_funds.items():
            category_returns = [
                fund_metrics[p]["r_3m"] for p in pids if fund_metrics[p]["r_3m"] is not None
            ]

            # Rule Q8: one row per portfolio_id in any peer percentile. Minimum 8 peers, otherwise null.
            has_min_peers = len(category_returns) >= 8

            for pid in pids:
                m = fund_metrics[pid]
                if has_min_peers and m["r_3m"] is not None:
                    peer_pct = mid_rank_percentile(m["r_3m"], category_returns)
                else:
                    peer_pct = None
                m["peer_pct_3m"] = peer_pct

                quadrant = (
                    assign_quadrant(peer_pct, m["shp_3m"])
                    if (peer_pct is not None and m["shp_3m"] is not None)
                    else None
                )

                momentum_score = (
                    min(100.0, max(0.0, 50.0 + m["r_3m"] * 250.0))
                    if m["r_3m"] is not None
                    else None
                )
                quality_score = min(100.0, max(0.0, 50.0 + (m["ir_3y"] or 0.0) * 25.0))
                risk_score = min(100.0, max(0.0, 100.0 + (m["mdd"] or 0.0) * 200.0))

                factor_scores = {
                    "momentum": momentum_score if momentum_score is not None else 50.0,
                    "persistence": m["shp_3m"] if m["shp_3m"] is not None else 50.0,
                    "quality": quality_score,
                    "risk": risk_score,
                    "cost": 75.0,
                }
                composite, conf = compute_composite_score(
                    factor_scores, active_model_config, obs_count=m["obs_count"]
                )

                s = m["scheme"]
                await conn.execute(
                    """
                    INSERT INTO scoring.screener_snapshot (
                        as_of_date, model_version, category_id, portfolio_id, fund_name, amc,
                        ret_1m, ret_3m, ret_6m, ret_1y, cagr_3y, shp_3m, peer_pct_3m, alpha_3m,
                        ir_3y, mdd_3y, ter, exit_load_rate, exit_load_days, composite, confidence, quadrant, flags, investable
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6,
                        $7, $8, $9, $10, $11, $12, $13, $14,
                        $15, $16, 0.007, 0.01, 365, $17, $18, $19, 0, true
                    )
                    ON CONFLICT (as_of_date, model_version, category_id, portfolio_id) DO UPDATE
                    SET fund_name = EXCLUDED.fund_name,
                        amc = EXCLUDED.amc,
                        ret_1m = EXCLUDED.ret_1m,
                        ret_3m = EXCLUDED.ret_3m,
                        ret_6m = EXCLUDED.ret_6m,
                        ret_1y = EXCLUDED.ret_1y,
                        cagr_3y = EXCLUDED.cagr_3y,
                        alpha_3m = EXCLUDED.alpha_3m,
                        ir_3y = EXCLUDED.ir_3y,
                        mdd_3y = EXCLUDED.mdd_3y,
                        composite = EXCLUDED.composite,
                        peer_pct_3m = EXCLUDED.peer_pct_3m,
                        shp_3m = EXCLUDED.shp_3m,
                        quadrant = EXCLUDED.quadrant,
                        confidence = EXCLUDED.confidence;
                    """,
                    as_of_date,
                    active_model_version,
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

        # 4b. Rule Q4/Q12: purge stale funds from the active screener and detail views.
        if excluded_stale:
            await conn.execute(
                "DELETE FROM scoring.screener_snapshot "
                "WHERE as_of_date = $1 AND portfolio_id = ANY($2::int[]);",
                as_of_date,
                excluded_stale,
            )
            await conn.execute(
                "DELETE FROM analytics.fund_summary WHERE portfolio_id = ANY($1::int[]);",
                excluded_stale,
            )
            logger.info(
                "Excluded %d stale funds (last NAV > %d days old) from screener.",
                len(excluded_stale),
                MAX_SNAPSHOT_STALENESS_DAYS,
            )

        # 4c. Purge any fund no longer in the in-scope universe (Spec §6.1/6.2):
        # an upsert leaves rows from previous runs (e.g. ETFs, index, debt funds
        # scored before the universe filter). Delete everything not computed this
        # run so the snapshot equals the current universe.
        computed_pids = list(fund_metrics.keys())
        if computed_pids:
            await conn.execute(
                "DELETE FROM scoring.screener_snapshot "
                "WHERE as_of_date = $1 AND model_version = $2 "
                "AND NOT (portfolio_id = ANY($3::int[]));",
                as_of_date,
                active_model_version,
                computed_pids,
            )
            await conn.execute(
                "DELETE FROM analytics.fund_summary "
                "WHERE NOT (portfolio_id = ANY($1::int[]));",
                computed_pids,
            )

        # 5. Update scoring.latest with active model version
        await conn.execute(
            """
            INSERT INTO scoring.latest (model_version, as_of_date, published_at)
            VALUES ($1, $2, now())
            ON CONFLICT (model_version) DO UPDATE
            SET as_of_date = EXCLUDED.as_of_date, published_at = now();
            """,
            active_model_version,
            as_of_date,
        )

        logger.info(
            "Batch compute worker completed successfully for model %s with %d funds.",
            active_model_version,
            len(fund_metrics),
        )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_compute_job())
