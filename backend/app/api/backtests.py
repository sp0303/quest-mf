"""Backtest router for walk-forward simulations."""

import json
from datetime import date

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from questmf_quant.backtest.walkforward import BacktestConfig, run_walkforward_backtest

from app.core.db import get_db_connection

router = APIRouter(prefix="/backtests/v1", tags=["backtests"])


class CreateRunRequest(BaseModel):
    model_version: str = "v1_baseline"
    top_k: int = Field(3, ge=1, le=10)
    rebalance_months: int = Field(3, ge=1, le=12)
    exec_lag_days: int = Field(1, ge=1)


@router.post("/runs")
async def create_backtest_run(
    req: CreateRunRequest,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    # Fetch historical NAVs for canonical schemes
    nav_rows = await conn.fetch(
        """
        SELECT s.portfolio_id, h.nav_date, h.nav
        FROM market.nav_history h
        JOIN ref.schemes s ON h.scheme_code = s.scheme_code
        WHERE s.is_canonical = true
        ORDER BY h.nav_date ASC;
        """
    )
    if not nav_rows:
        raise HTTPException(status_code=400, detail="No historical NAVs found for backtest")

    # Group NAVs by portfolio
    nav_by_portfolio: dict[int, dict[date, float]] = {}
    trading_calendar_set: set[date] = set()
    for r in nav_rows:
        pid = r["portfolio_id"]
        d = r["nav_date"]
        nav_val = float(r["nav"])
        if pid not in nav_by_portfolio:
            nav_by_portfolio[pid] = {}
        nav_by_portfolio[pid][d] = nav_val
        trading_calendar_set.add(d)

    trading_calendar = sorted(trading_calendar_set)

    # Fetch snapshot scores or generate scores as of rebalance dates
    score_rows = await conn.fetch(
        """
        SELECT as_of_date, portfolio_id, composite
        FROM scoring.screener_snapshot
        WHERE model_version = $1
        ORDER BY as_of_date ASC;
        """,
        req.model_version,
    )
    scores_by_date: dict[date, dict[int, float]] = {}
    for r in score_rows:
        d = r["as_of_date"]
        if d not in scores_by_date:
            scores_by_date[d] = {}
        scores_by_date[d][r["portfolio_id"]] = float(r["composite"] or 50.0)

    # If scores are only for one date, synthesize historical rebalance scores from trailing 3M return
    if len(scores_by_date) <= 1 and len(trading_calendar) > 60:
        for idx in range(60, len(trading_calendar), req.rebalance_months * 21):
            d = trading_calendar[idx]
            past_d = trading_calendar[idx - 60]
            scores_by_date[d] = {}
            for pid, p_navs in nav_by_portfolio.items():
                if d in p_navs and past_d in p_navs and p_navs[past_d] > 0:
                    ret_3m = (p_navs[d] / p_navs[past_d]) - 1.0
                    scores_by_date[d][pid] = 50.0 + ret_3m * 200.0

    cfg = BacktestConfig(
        top_k=req.top_k,
        rebalance_months=req.rebalance_months,
        exec_lag_days=req.exec_lag_days,
    )

    result = run_walkforward_backtest(
        nav_by_portfolio=nav_by_portfolio,
        scores_by_date=scores_by_date,
        trading_calendar=trading_calendar,
        config=cfg,
    )

    config_json = json.dumps(
        {
            "top_k": req.top_k,
            "rebalance_months": req.rebalance_months,
            "exec_lag_days": req.exec_lag_days,
        }
    )
    summary_json = json.dumps(result.summary)

    row = await conn.fetchrow(
        """
        INSERT INTO backtest.runs (
            created_by, model_version, config, status, progress_pct, summary, finished_at
        ) VALUES (
            'analyst-1', $1, $2::jsonb, 'DONE', 100.0, $3::jsonb, now()
        ) RETURNING run_id, created_at, status;
        """,
        req.model_version,
        config_json,
        summary_json,
    )
    run_id = row["run_id"]

    # Insert series in batches
    series_records = []
    step = max(1, len(result.equity_curve_gross) // 100)
    sampled_gross = result.equity_curve_gross[::step]
    sampled_net = result.equity_curve_net[::step]
    if result.equity_curve_gross and sampled_gross[-1] != result.equity_curve_gross[-1]:
        sampled_gross.append(result.equity_curve_gross[-1])
        sampled_net.append(result.equity_curve_net[-1])

    for d, val in sampled_gross:
        series_records.append((run_id, "EQUITY_GROSS", d, val))
    for d, val in sampled_net:
        series_records.append((run_id, "EQUITY_NET", d, val))

    await conn.executemany(
        """
        INSERT INTO backtest.run_series (run_id, series, d, v)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT DO NOTHING;
        """,
        series_records,
    )

    return {"run_id": run_id, "status": "DONE", "summary": result.summary}


@router.get("/runs")
async def list_runs(conn: asyncpg.Connection = Depends(get_db_connection)):
    rows = await conn.fetch("""
        SELECT run_id, model_version, status, progress_pct, summary, created_at, finished_at
        FROM backtest.runs
        ORDER BY run_id DESC
        LIMIT 20;
    """)
    return [dict(r) for r in rows]


@router.get("/runs/{run_id}")
async def get_run(run_id: int, conn: asyncpg.Connection = Depends(get_db_connection)):
    row = await conn.fetchrow(
        """
        SELECT run_id, model_version, status, progress_pct, summary, created_at, finished_at
        FROM backtest.runs
        WHERE run_id = $1;
    """,
        run_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    return dict(row)


@router.get("/runs/{run_id}/series")
async def get_run_series(run_id: int, conn: asyncpg.Connection = Depends(get_db_connection)):
    rows = await conn.fetch(
        """
        SELECT series, d, v
        FROM backtest.run_series
        WHERE run_id = $1
        ORDER BY d ASC;
    """,
        run_id,
    )

    gross = [(r["d"].isoformat(), float(r["v"])) for r in rows if r["series"] == "EQUITY_GROSS"]
    net = [(r["d"].isoformat(), float(r["v"])) for r in rows if r["series"] == "EQUITY_NET"]

    return {
        "run_id": run_id,
        "gross": gross,
        "net": net,
    }
