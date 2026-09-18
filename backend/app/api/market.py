"""Market data router for NAV series, benchmarks, and freshness.

Strict adherence to Rule 8: Every time-series query has a time predicate and explicit column list.
"""

from datetime import date, timedelta

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from questmf_quant.downsample import lttb

from app.core.db import get_db_connection

router = APIRouter(prefix="/market/v1", tags=["market"])


@router.get("/nav/{portfolio_id}")
async def get_nav_series(
    portfolio_id: int,
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    points: int = Query(2000, le=5000),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Retrieve canonical NAV time series with explicit time range predicate (Rule 8)."""
    end_d = to_date or date.today()
    start_d = from_date or (end_d - timedelta(days=1095))  # Default 3Y

    rows = await conn.fetch(
        """
        SELECT h.nav_date, h.nav
        FROM market.nav_history h
        JOIN ref.schemes s ON h.scheme_code = s.scheme_code
        WHERE s.portfolio_id = $1
          AND s.is_canonical = true
          AND h.nav_date BETWEEN $2 AND $3
        ORDER BY h.nav_date ASC;
        """,
        portfolio_id,
        start_d,
        end_d,
    )

    if not rows:
        raise HTTPException(
            status_code=404, detail="No NAV history found for portfolio in the given range"
        )

    dates = [r["nav_date"].isoformat() for r in rows]
    navs = [float(r["nav"]) for r in rows]

    downsampled = len(navs) > points
    s_dates, s_navs = lttb(dates, navs, target_points=points)

    return {
        "portfolio_id": portfolio_id,
        "from_date": start_d.isoformat(),
        "to_date": end_d.isoformat(),
        "downsampled": downsampled,
        "count": len(s_navs),
        "t": s_dates,
        "nav": s_navs,
    }


@router.get("/funds/{portfolio_id}/nav-history")
async def get_fund_nav_history(
    portfolio_id: int,
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    points: int = Query(2000, le=5000),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Canonical Direct-Growth NAV series for the fund-detail chart.

    A portfolio can map to several canonical Direct-Growth scheme_codes
    (segregated side-pockets), so collapse to a single series (Rule Q7) by
    choosing the scheme with the most recent, longest NAV coverage before
    returning its values within an explicit time window (Rule 8).
    """
    scheme = await conn.fetchrow(
        """
        SELECT s.scheme_code
        FROM ref.schemes s
        JOIN (
            SELECT scheme_code, MAX(nav_date) AS last_nav_date, COUNT(*) AS pts
            FROM market.nav_history
            GROUP BY scheme_code
        ) st ON st.scheme_code = s.scheme_code
        WHERE s.portfolio_id = $1
          AND s.is_canonical = true
        ORDER BY st.last_nav_date DESC, st.pts DESC, s.scheme_code ASC
        LIMIT 1;
        """,
        portfolio_id,
    )
    if scheme is None:
        raise HTTPException(status_code=404, detail="No canonical scheme for portfolio")

    end_d = to_date or date.today()
    start_d = from_date or (end_d - timedelta(days=1825))  # Default 5Y

    rows = await conn.fetch(
        """
        SELECT h.nav_date, h.nav
        FROM market.nav_history h
        WHERE h.scheme_code = $1
          AND h.nav_date BETWEEN $2 AND $3
        ORDER BY h.nav_date ASC;
        """,
        scheme["scheme_code"],
        start_d,
        end_d,
    )
    if not rows:
        raise HTTPException(
            status_code=404, detail="No NAV history found for portfolio in the given range"
        )

    dates = [r["nav_date"].isoformat() for r in rows]
    navs = [float(r["nav"]) for r in rows]
    s_dates, s_navs = lttb(dates, navs, target_points=points)

    return {"dates": s_dates, "navs": s_navs}


@router.get("/nav/{portfolio_id}/overlay")
async def get_nav_overlay(
    portfolio_id: int,
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    points: int = Query(1000, le=3000),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Retrieve NAV series rebased to 100 with time predicates (Rule 8)."""
    end_d = to_date or date.today()
    start_d = from_date or (end_d - timedelta(days=1095))

    rows = await conn.fetch(
        """
        SELECT h.nav_date, h.nav
        FROM market.nav_history h
        JOIN ref.schemes s ON h.scheme_code = s.scheme_code
        WHERE s.portfolio_id = $1
          AND s.is_canonical = true
          AND h.nav_date BETWEEN $2 AND $3
        ORDER BY h.nav_date ASC;
        """,
        portfolio_id,
        start_d,
        end_d,
    )

    if not rows:
        raise HTTPException(status_code=404, detail="Fund series not found in the given range")

    dates = [r["nav_date"].isoformat() for r in rows]
    navs = [float(r["nav"]) for r in rows]

    # Rebase fund NAV to 100
    base = navs[0]
    rebased_nav = [(v / base) * 100.0 for v in navs]

    s_dates, s_rebased = lttb(dates, rebased_nav, target_points=points)

    return {
        "portfolio_id": portfolio_id,
        "from_date": start_d.isoformat(),
        "to_date": end_d.isoformat(),
        "t": s_dates,
        "series": {
            "nav_rebased": s_rebased,
        },
    }


@router.get("/freshness")
async def get_freshness(conn: asyncpg.Connection = Depends(get_db_connection)):
    row = await conn.fetchrow("""
        SELECT max(nav_date) as last_nav_date, count(distinct scheme_code) as total_schemes, count(*) as total_nav_rows
        FROM market.nav_history;
    """)
    return dict(row) if row else {"last_nav_date": None, "total_schemes": 0, "total_nav_rows": 0}
