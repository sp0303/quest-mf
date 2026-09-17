"""Backtest router for walk-forward simulations."""

from datetime import date

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

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
    # Simulated quick walk-forward backtest run
    summary = {
        "model_version": req.model_version,
        "cagr_gross": 0.224,
        "cagr_net": 0.188,
        "sharpe_ratio": 1.45,
        "max_drawdown": -0.162,
        "rank_ic_mean": 0.082,
        "top_k": req.top_k,
        "rebalance_months": req.rebalance_months,
    }

    row = await conn.fetchrow(
        """
        INSERT INTO backtest.runs (
            created_by, model_version, config, status, progress_pct, summary, finished_at
        ) VALUES (
            'analyst-1', $1, '{"top_k": 3}', 'DONE', 100.0, $2, now()
        ) RETURNING run_id, created_at, status;
    """,
        req.model_version,
        summary,
    )

    run_id = row["run_id"]

    # Seed equity curve series for this run
    equity_gross = 100000.0
    equity_net = 100000.0
    today = date.today()
    for i in range(12, 0, -1):
        d = today.replace(day=1)
        # Shift back by months
        m = (d.month - i) % 12 or 12
        y = d.year - ((i - d.month + 12) // 12)
        curve_date = date(y, m, 1)

        equity_gross *= 1.018
        equity_net *= 1.015

        await conn.execute(
            """
            INSERT INTO backtest.run_series (run_id, series, d, v)
            VALUES ($1, 'EQUITY_GROSS', $2, $3),
                   ($1, 'EQUITY_NET', $2, $4)
            ON CONFLICT DO NOTHING;
        """,
            run_id,
            curve_date,
            round(equity_gross, 2),
            round(equity_net, 2),
        )

    return {"run_id": run_id, "status": "DONE", "summary": summary}


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
