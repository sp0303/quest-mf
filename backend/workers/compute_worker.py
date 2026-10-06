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
from questmf_quant.composite import (
    FLAG_INCOMPLETE,
    FLAG_INVESTABILITY_UNVERIFIED,
    FLAG_NO_BENCHMARK,
    FLAG_SHORT_HISTORY,
    FLAG_SMALL_PEER_GROUP,
    SPEC16_MODEL,
    CompositeModel,
    CompositeResult,
    model_from_config,
    score_category,
)
from questmf_quant.percentile import peer_percentiles
from questmf_quant.returns import CanonicalCandidate, select_canonical_scheme
from questmf_quant.scoring import Confidence, assign_quadrant

from app.config import settings
from workers.compute_metrics import OBS_3Y, compute_fund_features

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("compute_worker")

# Rule Q4/Q12: a fund whose latest canonical NAV is older than this as of the run
# date has no current data to score. It must be dropped from the active screener
# (INSUFFICIENT_HISTORY), never scored off stale values.
MAX_SNAPSHOT_STALENESS_DAYS = 30


def _load_model(model_row: asyncpg.Record | None) -> CompositeModel:
    """Build the spec §16 model from the default scoring.model_versions row (Rule Q13)."""
    if model_row and model_row["config"]:
        raw = model_row["config"]
        cfg = json.loads(raw) if isinstance(raw, str) else dict(raw)
        if cfg.get("components"):
            return model_from_config(model_row["model_version"], cfg)
        logger.warning(
            "Default model %s has no spec §16 'components'; using %s.",
            model_row["model_version"],
            SPEC16_MODEL.version,
        )
    return SPEC16_MODEL


def _summary_payload(f: dict) -> dict:
    def pct(v: float | None) -> float | None:
        return round(v * 100, 2) if v is not None else None

    def num(v: float | None) -> float | None:
        return round(v, 2) if v is not None else None

    return {
        "volatility_ann": pct(f["vol"]),
        "downside_dev_ann": pct(f["downside_dev_3y"]),
        "sharpe_ratio": num(f["sharpe"]),
        "sortino_ratio": num(f["sortino"]),
        "max_drawdown": pct(f["mdd_3y"]),
        "cagr_3y": pct(f["cagr_3y"]),
        "cagr_5y": pct(f["cagr_5y"]),
        "observations": f["obs_count"],
        "alpha_3m": pct(f["alpha_3m"]),
        "ir_3y": num(f["ir_3y"]),
        "beta": num(f["beta_1y"]),
        "tracking_error": pct(f["tracking_error"]),
        "beat_pct_3m": num(f["beat_pct_3m"]),
        "beat_pct_1y": num(f["beat_pct_1y"]),
        "median_active_3m": pct(f["median_active_3m"]),
    }


def _flags(m: dict, res: CompositeResult) -> int:
    flags = FLAG_INVESTABILITY_UNVERIFIED
    if res.small_peer_group:
        flags |= FLAG_SMALL_PEER_GROUP
    if res.incomplete:
        flags |= FLAG_INCOMPLETE
    if m["obs_count"] < OBS_3Y:
        flags |= FLAG_SHORT_HISTORY
    if not m["has_bench"] or m["beat_pct_3m"] is None:
        flags |= FLAG_NO_BENCHMARK
    return flags


async def _upsert_snapshot(
    conn: asyncpg.Connection,
    as_of_date: date,
    model_version: str,
    cat_id: int,
    pid: int,
    m: dict,
    peer_pct: float | None,
    res: CompositeResult,
    min_obs: int,
) -> None:
    """Write one screener row. Q12: < min_obs history -> INSUFFICIENT, composite null."""
    obs = m["obs_count"]
    if obs < min_obs:
        composite, conf = None, Confidence.INSUFFICIENT
    else:
        composite = res.composite
        conf = Confidence.OK if obs >= OBS_3Y else Confidence.LOW
    quadrant = assign_quadrant(peer_pct, m["shp_3m"])
    s = m["scheme"]
    await conn.execute(
        """
        INSERT INTO scoring.screener_snapshot (
            as_of_date, model_version, category_id, portfolio_id, fund_name, amc,
            ret_1m, ret_3m, ret_6m, ret_1y, cagr_3y, shp_3m, peer_pct_3m, alpha_3m,
            ir_3y, mdd_3y, ter, exit_load_rate, exit_load_days, composite, confidence,
            quadrant, flags, investable
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,
                  NULL, NULL, $18, $19, $20, $21, true)
        ON CONFLICT (as_of_date, model_version, category_id, portfolio_id) DO UPDATE
        SET fund_name = EXCLUDED.fund_name, amc = EXCLUDED.amc,
            ret_1m = EXCLUDED.ret_1m, ret_3m = EXCLUDED.ret_3m, ret_6m = EXCLUDED.ret_6m,
            ret_1y = EXCLUDED.ret_1y, cagr_3y = EXCLUDED.cagr_3y, shp_3m = EXCLUDED.shp_3m,
            peer_pct_3m = EXCLUDED.peer_pct_3m, alpha_3m = EXCLUDED.alpha_3m,
            ir_3y = EXCLUDED.ir_3y, mdd_3y = EXCLUDED.mdd_3y, ter = EXCLUDED.ter,
            exit_load_rate = NULL, exit_load_days = NULL, composite = EXCLUDED.composite,
            confidence = EXCLUDED.confidence, quadrant = EXCLUDED.quadrant,
            flags = EXCLUDED.flags, investable = EXCLUDED.investable;
        """,
        as_of_date,
        model_version,
        cat_id,
        pid,
        s["fund_name"],
        s["amc_name"],
        m["ret_1m"],
        m["ret_3m"],
        m["ret_6m"],
        m["ret_1y"],
        m["cagr_3y"],
        m["shp_3m"],
        peer_pct,
        m["alpha_3m"],
        m["ir_3y"],
        m["mdd_3y"],
        m["ter"],
        composite,
        conf,
        quadrant,
        _flags(m, res),
    )


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
              AND p.display_name NOT ILIKE '%Floater%'
              -- Overseas / international funds are out of MVP scope (spec §6.2).
              AND p.display_name !~* '(\\mUS\\M|international|japan|asian|global|nasdaq|world|emerging|china|europe|feeder)';
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

        # 2c. Active model (Rule Q13): components/weights come from scoring.model_versions.
        model_row = await conn.fetchrow(
            "SELECT model_version, config FROM scoring.model_versions WHERE is_default = true LIMIT 1;"
        )
        model = _load_model(model_row)
        active_model_version = model.version

        # 2d. Point-in-time TER (Rule Q2): latest Direct-plan TER on or before as_of_date.
        ter_rows = await conn.fetch(
            """
            SELECT DISTINCT ON (scheme_code) scheme_code, ter
            FROM ref.ter_history
            WHERE effective_date <= $1
            ORDER BY scheme_code, effective_date DESC;
            """,
            as_of_date,
        )
        ter_by_scheme = {r["scheme_code"]: float(r["ter"]) / 100.0 for r in ter_rows}

        fund_metrics: dict[int, dict] = {}
        excluded_stale: list[int] = []

        # 3. Per-fund features (returns, risk, benchmark-relative persistence)
        for s in schemes:
            pid = s["portfolio_id"]
            nav_rows = await conn.fetch(
                "SELECT nav_date, nav FROM market.nav_history WHERE scheme_code = $1 "
                "AND nav_date <= $2 ORDER BY nav_date ASC;",
                s["scheme_code"],
                as_of_date,
            )
            if len(nav_rows) < 30:
                continue
            nav_by_date = {r["nav_date"]: float(r["nav"]) for r in nav_rows}
            # Rule Q4/Q12: skip funds whose latest NAV is stale as of the run date.
            if (as_of_date - max(nav_by_date)).days > MAX_SNAPSHOT_STALENESS_DAYS:
                excluded_stale.append(pid)
                continue

            bench_series = bench_data.get(portfolio_bench_map.get(pid, 2), {})
            f = compute_fund_features(
                nav_by_date, bench_series, ter_by_scheme.get(s["scheme_code"])
            )
            f["scheme"] = s
            f["has_bench"] = bool(bench_series)
            fund_metrics[pid] = f

            await conn.execute(
                """
                INSERT INTO analytics.fund_summary (portfolio_id, as_of_date, payload, updated_at)
                VALUES ($1, $2, $3::jsonb, now())
                ON CONFLICT (portfolio_id) DO UPDATE
                SET as_of_date = EXCLUDED.as_of_date, payload = EXCLUDED.payload, updated_at = now();
                """,
                pid,
                as_of_date,
                json.dumps(_summary_payload(f)),
            )

        # 4. Within-category scoring (spec §16.1, Rule Q8: one row per portfolio_id)
        by_category: dict[int, list[int]] = {}
        for pid, m in fund_metrics.items():
            by_category.setdefault(m["scheme"]["category_id"], []).append(pid)

        for cat_id, pids in by_category.items():
            peer_pct = peer_percentiles(
                {p: fund_metrics[p]["ret_3m"] for p in pids}, min_peers=model.min_peers
            )
            scored = score_category({p: fund_metrics[p] for p in pids}, model)
            for pid in pids:
                await _upsert_snapshot(
                    conn,
                    as_of_date,
                    active_model_version,
                    cat_id,
                    pid,
                    fund_metrics[pid],
                    peer_pct[pid],
                    scored[pid],
                    model.min_obs_required,
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
                "DELETE FROM analytics.fund_summary WHERE NOT (portfolio_id = ANY($1::int[]));",
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
