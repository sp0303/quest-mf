"""Resolve registered (seed) portfolio IDs to the live portfolio the screener shows.

Seed portfolio IDs (101, 102, ...) can be superseded by the AMFI-ingested portfolio
for the same fund. Holdings must attach to the live portfolio (Rule Q7: one series
per fund), otherwise the fund page shows no holdings. Never guesses: an ambiguous
or missing match returns None.
"""

from __future__ import annotations

import logging
import re

import asyncpg

from workers.ter_worker import normalize_scheme_name

logger = logging.getLogger("portfolio_resolver")
LIVE_NAV_WINDOW_DAYS = 30


def _name_parts(display_name: str) -> tuple[str, list[str]]:
    """(main key, alias keys) — aliases come from "(erstwhile X)" / "(formerly X)"."""
    aliases = re.findall(r"\((?:erstwhile|formerly)\s+([^)]*)\)", display_name, flags=re.I)
    return normalize_scheme_name(display_name), [normalize_scheme_name(a) for a in aliases if a]


def names_match(a: str, b: str) -> bool:
    """Same fund? Exact normalized name, or one side's former name ("erstwhile Bluechip
    Fund") is the tail of the other's name with the same AMC first word."""
    main_a, alias_a = _name_parts(a)
    main_b, alias_b = _name_parts(b)
    if main_a and main_a == main_b:
        return True
    return _former_name_tail(main_a, main_b, alias_b) or _former_name_tail(main_b, main_a, alias_a)


def _former_name_tail(main: str, other_main: str, other_aliases: list[str]) -> bool:
    if not main or not other_main:
        return False
    same_amc = main.split()[0] == other_main.split()[0]
    return same_amc and any(a and main.endswith(" " + a) for a in other_aliases)


async def live_portfolio_ids(conn: asyncpg.Connection) -> dict[int, str]:
    """Portfolios whose canonical series has a NAV in the last LIVE_NAV_WINDOW_DAYS."""
    rows = await conn.fetch(
        """
        SELECT DISTINCT p.portfolio_id, p.display_name
        FROM ref.portfolios p
        JOIN ref.schemes s ON s.portfolio_id = p.portfolio_id AND s.is_canonical = true
        JOIN market.nav_history n ON n.scheme_code = s.scheme_code
        WHERE n.nav_date >= (SELECT MAX(nav_date) FROM market.nav_history) - $1::int;
        """,
        LIVE_NAV_WINDOW_DAYS,
    )
    return {r["portfolio_id"]: r["display_name"] for r in rows}


async def resolve_live_portfolio_id(
    conn: asyncpg.Connection, pid: int, live: dict[int, str] | None = None
) -> int | None:
    """Map a registered portfolio_id to the live portfolio the screener shows.

    Seed portfolio IDs can be superseded by the AMFI-ingested portfolio for the same
    fund (Rule Q7: one series per fund). Holdings must attach to the live one.
    Returns None when no single live portfolio matches (never guesses).
    """
    live = live if live is not None else await live_portfolio_ids(conn)
    if pid in live:
        return pid
    name = await conn.fetchval("SELECT display_name FROM ref.portfolios WHERE portfolio_id=$1", pid)
    if not name:
        return None
    matches = [lp for lp, ln in live.items() if names_match(name, ln)]
    return matches[0] if len(matches) == 1 else None


async def relink_holdings_to_live(conn: asyncpg.Connection) -> dict[int, int | None]:
    """One-off/idempotent: move holdings stored on non-live portfolio IDs to the live ID."""
    live = await live_portfolio_ids(conn)
    pids = [
        r["portfolio_id"]
        for r in await conn.fetch("SELECT DISTINCT portfolio_id FROM holdings.monthly_portfolio")
    ]
    moved: dict[int, int | None] = {}
    for pid in pids:
        target = await resolve_live_portfolio_id(conn, pid, live)
        if target == pid:
            continue
        moved[pid] = target
        if target is None:
            logger.warning("Holdings on portfolio %d: no unique live portfolio match.", pid)
            continue
        async with conn.transaction():
            for table in ("holdings.monthly_portfolio", "holdings.portfolio_summary"):
                await conn.execute(
                    f"UPDATE {table} SET portfolio_id = $2 WHERE portfolio_id = $1", pid, target
                )
        logger.info("Relinked holdings %d -> live portfolio %d (%s).", pid, target, live[target])
    return moved
