"""Fund metadata and reference router."""

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.db import get_db_connection

router = APIRouter(prefix="/funds/v1", tags=["funds"])


@router.get("/categories")
async def get_categories(conn: asyncpg.Connection = Depends(get_db_connection)):
    rows = await conn.fetch(
        "SELECT category_id, code, label, asset_class FROM ref.categories ORDER BY label;"
    )
    return [dict(r) for r in rows]


@router.get("/amcs")
async def get_amcs(conn: asyncpg.Connection = Depends(get_db_connection)):
    rows = await conn.fetch("SELECT amc_id, name FROM ref.amcs ORDER BY name;")
    return [dict(r) for r in rows]


@router.get("/search")
async def search_funds(
    q: str = Query("", min_length=1),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    query = """
        SELECT p.portfolio_id, p.display_name, a.name AS amc_name
        FROM ref.portfolios p
        JOIN ref.amcs a ON p.amc_id = a.amc_id
        WHERE p.display_name ILIKE $1
        ORDER BY p.display_name
        LIMIT 10;
    """
    rows = await conn.fetch(query, f"%{q}%")
    return [dict(r) for r in rows]


@router.get("/funds")
async def list_funds(
    category: str | None = None,
    q: str | None = None,
    limit: int = Query(50, le=100),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    sql = """
        SELECT p.portfolio_id, p.display_name, a.name AS amc_name, p.launch_date
        FROM ref.portfolios p
        JOIN ref.amcs a ON p.amc_id = a.amc_id
        WHERE ($1::text IS NULL OR p.display_name ILIKE $1)
        ORDER BY p.display_name
        LIMIT $2;
    """
    search_pattern = f"%{q}%" if q else None
    rows = await conn.fetch(sql, search_pattern, limit)
    return [dict(r) for r in rows]


@router.get("/funds/{portfolio_id}")
async def get_fund(
    portfolio_id: int,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    fund_row = await conn.fetchrow(
        """
        SELECT p.portfolio_id, p.display_name, a.name AS amc, p.launch_date
        FROM ref.portfolios p
        JOIN ref.amcs a ON p.amc_id = a.amc_id
        WHERE p.portfolio_id = $1;
    """,
        portfolio_id,
    )

    if not fund_row:
        raise HTTPException(status_code=404, detail="Fund not found")

    schemes = await conn.fetch(
        """
        SELECT scheme_code, scheme_name, plan, option, is_canonical, status
        FROM ref.schemes
        WHERE portfolio_id = $1;
    """,
        portfolio_id,
    )

    load_row = await conn.fetchrow(
        """
        SELECT exit_load_rate, exit_load_days, rule_text
        FROM ref.load_rules lr
        JOIN ref.schemes s ON lr.scheme_code = s.scheme_code
        WHERE s.portfolio_id = $1
        LIMIT 1;
    """,
        portfolio_id,
    )

    return {
        "fund": dict(fund_row),
        "schemes": [dict(s) for s in schemes],
        "load_rule": dict(load_row) if load_row else None,
    }
