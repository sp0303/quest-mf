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


@router.get("/funds/{portfolio_id}/profile")
async def get_fund_profile(
    portfolio_id: int,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Retrieve fund profile and factsheet characteristics."""
    row = await conn.fetchrow(
        """
        SELECT portfolio_id, fund_manager, aum_cr, ter_pct,
               portfolio_turnover_ratio, pe_ratio, pb_ratio, riskometer,
               min_sip_amount, updated_at
        FROM ref.fund_profile
        WHERE portfolio_id = $1;
        """,
        portfolio_id,
    )
    if not row:
        return None
    return dict(row)


@router.get("/funds/{portfolio_id}/holdings")
async def get_fund_holdings(
    portfolio_id: int,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Retrieve precomputed portfolio holdings summary and active holdings list."""
    summary_row = await conn.fetchrow(
        """
        SELECT portfolio_id, as_of_date, stock_count, top_10_concentration_pct,
               large_cap_pct, mid_cap_pct, small_cap_pct, cash_pct,
               sector_allocation, top_10_holdings, disclosed_date
        FROM holdings.portfolio_summary
        WHERE portfolio_id = $1
        ORDER BY as_of_date DESC
        LIMIT 1;
        """,
        portfolio_id,
    )

    if not summary_row:
        return None

    import json
    as_of = summary_row["as_of_date"]

    holdings_rows = await conn.fetch(
        """
        SELECT h.isin, h.security_name, h.asset_type, h.sector, h.pct_nav,
               mc.market_cap_class
        FROM holdings.monthly_portfolio h
        LEFT JOIN ref.stock_market_cap mc
            ON h.isin = mc.isin
            AND mc.valid_from <= h.as_of_date
            AND mc.valid_to >= h.as_of_date
        WHERE h.portfolio_id = $1 AND h.as_of_date = $2
        ORDER BY h.pct_nav DESC;
        """,
        portfolio_id,
        as_of,
    )

    sectors = summary_row["sector_allocation"]
    if isinstance(sectors, str):
        sectors = json.loads(sectors)
    top_10 = summary_row["top_10_holdings"]
    if isinstance(top_10, str):
        top_10 = json.loads(top_10)

    return {
        "portfolio_id": summary_row["portfolio_id"],
        "as_of_date": str(summary_row["as_of_date"]),
        "disclosed_date": str(summary_row["disclosed_date"]) if summary_row["disclosed_date"] else None,
        "stock_count": summary_row["stock_count"],
        "top_10_concentration_pct": summary_row["top_10_concentration_pct"],
        "large_cap_pct": summary_row["large_cap_pct"],
        "mid_cap_pct": summary_row["mid_cap_pct"],
        "small_cap_pct": summary_row["small_cap_pct"],
        "cash_pct": summary_row["cash_pct"],
        "sector_allocation": sectors,
        "top_10_holdings": top_10,
        "holdings": [dict(r) for r in holdings_rows],
    }


@router.get("/funds/{portfolio_id}/overlap")
async def get_fund_overlap(
    portfolio_id: int,
    compare_with: int = Query(..., description="Target portfolio ID to compare with"),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Compute pairwise portfolio overlap between two funds."""
    from questmf_quant.portfolio.overlap import HoldingItem, compute_portfolio_overlap

    fund_names = await conn.fetch(
        "SELECT portfolio_id, display_name FROM ref.portfolios WHERE portfolio_id IN ($1, $2);",
        portfolio_id,
        compare_with,
    )
    name_map = {r["portfolio_id"]: r["display_name"] for r in fund_names}

    async def _get_latest_holdings(pid: int):
        rows = await conn.fetch(
            """
            SELECT isin, security_name, pct_nav, sector, as_of_date
            FROM holdings.monthly_portfolio
            WHERE portfolio_id = $1
            AND as_of_date = (
                SELECT max(as_of_date) FROM holdings.monthly_portfolio WHERE portfolio_id = $1
            );
            """,
            pid,
        )
        return rows

    rows_a = await _get_latest_holdings(portfolio_id)
    rows_b = await _get_latest_holdings(compare_with)

    as_of_a = str(rows_a[0]["as_of_date"]) if rows_a else None
    as_of_b = str(rows_b[0]["as_of_date"]) if rows_b else None

    holdings_a = [
        HoldingItem(
            identifier=r["isin"] or r["security_name"],
            name=r["security_name"],
            weight=float(r["pct_nav"]),
            sector=r["sector"],
        )
        for r in rows_a
    ]
    holdings_b = [
        HoldingItem(
            identifier=r["isin"] or r["security_name"],
            name=r["security_name"],
            weight=float(r["pct_nav"]),
            sector=r["sector"],
        )
        for r in rows_b
    ]

    result = compute_portfolio_overlap(holdings_a, holdings_b)

    return {
        "portfolio_a_id": portfolio_id,
        "portfolio_b_id": compare_with,
        "portfolio_a_name": name_map.get(portfolio_id, f"Fund {portfolio_id}"),
        "portfolio_b_name": name_map.get(compare_with, f"Fund {compare_with}"),
        "as_of_date_a": as_of_a,
        "as_of_date_b": as_of_b,
        "overlap_pct": result.overlap_pct,
        "common_holdings_count": result.common_holdings_count,
        "fund_a_total_weight": result.fund_a_total_weight,
        "fund_b_total_weight": result.fund_b_total_weight,
        "unique_to_a_count": result.unique_to_a_count,
        "unique_to_b_count": result.unique_to_b_count,
        "common_holdings": [
            {
                "identifier": c.identifier,
                "name": c.name,
                "weight_a": c.weight_a,
                "weight_b": c.weight_b,
                "overlap_weight": c.overlap_weight,
                "sector": c.sector,
            }
            for c in result.common_holdings
        ],
    }
