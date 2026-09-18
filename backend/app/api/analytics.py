"""Analytics router for rolling metrics, risk, and net return calculator."""

import json

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from questmf_quant.friction import calculate_net_return

from app.core.db import get_db_connection

router = APIRouter(prefix="/analytics/v1", tags=["analytics"])


class NetReturnRequest(BaseModel):
    initial_amount: float = Field(100000.0, gt=0)
    buy_nav: float = Field(100.0, gt=0)
    sell_nav: float = Field(120.0, gt=0)
    days_held: int = Field(180, ge=1)
    exit_load_rate: float = Field(0.01, ge=0)
    exit_load_days: int = Field(365, ge=0)
    stcg_rate: float = Field(0.20, ge=0)
    ltcg_rate: float = Field(0.125, ge=0)


@router.post("/calculator/net-return")
async def calculate_friction_net_return(req: NetReturnRequest):
    res = calculate_net_return(
        initial_amount=req.initial_amount,
        buy_nav=req.buy_nav,
        sell_nav=req.sell_nav,
        days_held=req.days_held,
        exit_load_rate=req.exit_load_rate,
        exit_load_days=req.exit_load_days,
        stcg_rate=req.stcg_rate,
        ltcg_rate=req.ltcg_rate,
    )
    return {
        "initial_investment": res.initial_investment,
        "stamp_duty": round(res.stamp_duty, 2),
        "net_invested": round(res.net_invested, 2),
        "units": round(res.units, 4),
        "gross_proceeds": round(res.gross_proceeds, 2),
        "exit_load": round(res.exit_load, 2),
        "proceeds_after_load": round(res.proceeds_after_load, 2),
        "stt": round(res.stt, 2),
        "capital_gain": round(res.capital_gain, 2),
        "tax": round(res.tax, 2),
        "net_proceeds": round(res.net_proceeds, 2),
        "net_profit": round(res.net_profit, 2),
        "gross_return_pct": round(res.gross_return_pct * 100, 2),
        "net_return_pct": round(res.net_return_pct * 100, 2),
    }


@router.get("/funds/{portfolio_id}/summary")
async def get_fund_summary(
    portfolio_id: int,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    snapshot_row = await conn.fetchrow(
        """
        SELECT
            as_of_date, model_version, category_id, portfolio_id, fund_name, amc,
            ret_1m, ret_3m, ret_6m, ret_1y, cagr_3y, shp_3m, peer_pct_3m, alpha_3m,
            ir_3y, mdd_3y, ter, exit_load_rate, exit_load_days,
            composite, confidence, quadrant, flags, investable
        FROM scoring.screener_snapshot
        WHERE portfolio_id = $1
        ORDER BY as_of_date DESC
        LIMIT 1;
        """,
        portfolio_id,
    )

    if not snapshot_row:
        raise HTTPException(status_code=404, detail="Summary not found for portfolio")

    return dict(snapshot_row)


@router.get("/funds/{portfolio_id}/risk")
async def get_fund_risk_metrics(
    portfolio_id: int,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    # Rule 1: Precompute; don't compute on request.
    # Retrieve precomputed risk metrics from analytics.fund_summary
    row = await conn.fetchrow(
        """
        SELECT as_of_date, payload
        FROM analytics.fund_summary
        WHERE portfolio_id = $1
        ORDER BY as_of_date DESC
        LIMIT 1;
        """,
        portfolio_id,
    )

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Precomputed risk metrics not found for portfolio",
        )

    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)

    return {
        "portfolio_id": portfolio_id,
        "as_of_date": row["as_of_date"].isoformat() if row["as_of_date"] else None,
        **payload,
    }
