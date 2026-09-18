"""Screener router for fund rankings and 2x2 matrix."""

from datetime import date

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.core.db import get_db_connection

router = APIRouter(prefix="/screener/v1", tags=["screener"])

SORT_COLUMN_WHITELIST = {
    "composite": "composite",
    "ret_1m": "ret_1m",
    "ret_3m": "ret_3m",
    "ret_6m": "ret_6m",
    "ret_1y": "ret_1y",
    "cagr_3y": "cagr_3y",
    "shp_3m": "shp_3m",
    "peer_pct_3m": "peer_pct_3m",
    "alpha_3m": "alpha_3m",
    "mdd_3y": "mdd_3y",
    "ter": "ter",
}


@router.get("/latest")
async def get_latest(conn: asyncpg.Connection = Depends(get_db_connection)):
    row = await conn.fetchrow("""
        SELECT model_version, as_of_date, published_at
        FROM scoring.latest
        ORDER BY published_at DESC
        LIMIT 1;
    """)
    return dict(row) if row else {"model_version": "v1_baseline", "as_of_date": None}


@router.get("/models")
async def get_models(conn: asyncpg.Connection = Depends(get_db_connection)):
    rows = await conn.fetch("""
        SELECT model_version, config, is_default
        FROM scoring.model_versions
        ORDER BY is_default DESC;
    """)
    return [dict(r) for r in rows]


@router.get("/screener")
async def get_screener(
    as_of_date: date | None = Query(None),
    category_id: int | None = Query(None),
    min_confidence: int = Query(0),
    investable_only: bool = Query(False),
    sort: str = Query("composite"),
    direction: str = Query("desc"),
    limit: int = Query(100, le=500),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    sort_col = SORT_COLUMN_WHITELIST.get(sort, "composite")
    dir_sql = "ASC" if direction.lower() == "asc" else "DESC"

    query = f"""
        SELECT
            portfolio_id, fund_name, amc, ret_1m, ret_3m, ret_6m, ret_1y,
            cagr_3y, shp_3m, peer_pct_3m, alpha_3m, ir_3y, mdd_3y, ter,
            exit_load_rate, exit_load_days, composite, confidence, quadrant,
            flags, investable, category_id, as_of_date
        FROM scoring.screener_snapshot
        WHERE as_of_date = COALESCE($1, (SELECT as_of_date FROM scoring.latest WHERE model_version = 'v1_baseline' LIMIT 1))
          AND ($2::smallint IS NULL OR category_id = $2)
          AND confidence >= $3
          AND ($4::boolean IS FALSE OR investable = true)
        ORDER BY {sort_col} {dir_sql} NULLS LAST
        LIMIT $5;
    """
    rows = await conn.fetch(query, as_of_date, category_id, min_confidence, investable_only, limit)
    return [dict(r) for r in rows]


@router.get("/matrix")
async def get_matrix(
    as_of_date: date | None = Query(None),
    category_id: int | None = Query(None),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    query = """
        SELECT portfolio_id, fund_name, peer_pct_3m, shp_3m, quadrant, composite
        FROM scoring.screener_snapshot
        WHERE as_of_date = COALESCE($1, (SELECT as_of_date FROM scoring.latest WHERE model_version = 'v1_baseline' LIMIT 1))
          AND ($2::smallint IS NULL OR category_id = $2)
          AND peer_pct_3m IS NOT NULL
          AND shp_3m IS NOT NULL;
    """
    rows = await conn.fetch(query, as_of_date, category_id)
    return [dict(r) for r in rows]
