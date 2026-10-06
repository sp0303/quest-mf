"""AMFI NAVAll classification: section headers -> category, plan/option columns -> share class.

Fixes (2026-10-06 QA):
- Option came from keyword search for "idcw"/"dividend" only, so AMFI labels such as
  "Income Distribution cum Capital Withdrawal", "Payout/Reinvestment" and "Monthly Payment
  Plan" were tagged GROWTH and could become the canonical series (Rule Q7 violation), while
  every "Dividend Yield" fund (name contains "dividend") was tagged IDCW and dropped.
- Unmatched section headers kept the previous section's category, so debt and hybrid funds
  inherited equity categories; "Mid Cap" matched "Large & Mid Cap" headers first.
Unknown share classes are never treated as Growth (conservative: not canonical).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from typing import Protocol

import asyncpg

logger = logging.getLogger("amfi_classify")

NON_EQUITY = ("NON_EQUITY", 15, "Non-equity (debt / hybrid / FoF / other)")

# Longest / most specific keys first: "Large & Mid Cap" must win over "Mid Cap".
_EQUITY_KEYS: tuple[tuple[str, tuple[str, int, str]], ...] = (
    ("large & mid cap", ("EQ_LARGE_MID_CAP", 7, "Large & Mid Cap Fund")),
    ("small cap", ("EQ_SMALL_CAP", 1, "Small Cap Fund")),
    ("mid cap", ("EQ_MID_CAP", 2, "Mid Cap Fund")),
    ("large cap", ("EQ_LARGE_CAP", 3, "Large Cap Fund")),
    ("flexi cap", ("EQ_FLEXI_CAP", 4, "Flexi Cap Fund")),
    ("multi cap", ("EQ_MULTI_CAP", 6, "Multi Cap Fund")),
    ("elss", ("EQ_ELSS", 5, "ELSS (Tax Saving)")),
    ("focused", ("EQ_FOCUSED", 8, "Focused Fund")),
    ("dividend yield", ("EQ_DIVIDEND_YIELD", 9, "Dividend Yield Fund")),
    ("value", ("EQ_VALUE", 10, "Value Fund")),
    ("contra", ("EQ_CONTRA", 11, "Contra Fund")),
    ("sectoral", ("EQ_SECTORAL_THEMATIC", 12, "Sectoral / Thematic Fund")),
    ("thematic", ("EQ_SECTORAL_THEMATIC", 12, "Sectoral / Thematic Fund")),
)
INDEX_CATEGORY = ("EQ_INDEX", 13, "Index Fund")
ETF_CATEGORY = ("EQ_ETF", 14, "Equity ETF")
ALL_CATEGORIES = tuple({c for _, c in _EQUITY_KEYS} | {INDEX_CATEGORY, ETF_CATEGORY, NON_EQUITY})

_IDCW_WORDS = ("idcw", "dividend", "income distribution", "payout", "reinvest", "payment plan")


def classify_section_header(line: str) -> tuple[str, int, str]:
    """Category for an AMFI section header such as
    'Open Ended Schemes(Equity Scheme - Large & Mid Cap Fund)'.

    Only open-ended equity sections map to equity categories; everything else (debt,
    hybrid, FoF, close-ended, solution-oriented, gold/debt ETFs) is NON_EQUITY.
    """
    m = re.search(r"\((.*)\)\s*$", line.strip())
    section = (m.group(1) if m else line).lower()
    if not line.strip().lower().startswith("open ended"):
        return NON_EQUITY
    if section.startswith("equity scheme"):
        body = section.split("-", 1)[1] if "-" in section else section
        for key, cat in _EQUITY_KEYS:
            if key in body:
                return cat
        return NON_EQUITY
    if "index fund" in section:
        return INDEX_CATEGORY
    if "equity etf" in section:
        return ETF_CATEGORY
    return NON_EQUITY


def classify_plan_option(plan_str: str, option_str: str) -> tuple[str, str]:
    """(plan, option) from AMFI's Plan and Option columns (not the scheme name)."""
    plan = "DIRECT" if "direct" in plan_str.lower() else "REGULAR"
    opt = option_str.lower()
    if "bonus" in opt:
        return plan, "BONUS"
    if any(w in opt for w in _IDCW_WORDS):
        return plan, "IDCW"
    if "growth" in opt or opt.strip() in ("cumulative", "cumulative option"):
        return plan, "GROWTH"
    return plan, "IDCW"  # unknown share class: never canonical


class _Parsed(Protocol):
    scheme_code: int
    plan: str
    option: str
    category_id: int


async def ensure_categories(conn: asyncpg.Connection) -> None:
    for code, cid, label in ALL_CATEGORIES:
        asset_class = "OTHER" if code == NON_EQUITY[0] else "EQUITY"
        await conn.execute(
            """
            INSERT INTO ref.categories (category_id, code, label, asset_class)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (category_id) DO UPDATE SET label = EXCLUDED.label,
                asset_class = EXCLUDED.asset_class;
            """,
            cid,
            code,
            label,
            asset_class,
        )


async def reconcile_share_classes(conn: asyncpg.Connection, parsed: Iterable[_Parsed]) -> int:
    """Correct plan/option of existing ACTIVE schemes and drop canonical status from any
    series that is not Direct-Growth per AMFI (Rule Q7). CLOSED seed rows are untouched."""
    rows = [(p.scheme_code, p.plan, p.option) for p in parsed]
    res = await conn.execute(
        """
        UPDATE ref.schemes s
        SET plan = v.plan, option = v.option,
            is_canonical = s.is_canonical AND v.plan = 'DIRECT' AND v.option = 'GROWTH'
        FROM unnest($1::int[], $2::text[], $3::text[]) AS v(code, plan, option)
        WHERE s.scheme_code = v.code AND s.status = 'ACTIVE'
          AND (s.plan <> v.plan OR s.option <> v.option
               OR (s.is_canonical AND NOT (v.plan = 'DIRECT' AND v.option = 'GROWTH')));
        """,
        [r[0] for r in rows],
        [r[1] for r in rows],
        [r[2] for r in rows],
    )
    n = int(res.split()[-1])
    logger.info("Share-class reconciliation corrected %d scheme rows.", n)
    return n


async def reconcile_categories(conn: asyncpg.Connection, parsed: Iterable[_Parsed]) -> int:
    """Correct open category_history rows to the AMFI section of each portfolio's ACTIVE
    Direct-Growth scheme. A wrong label is a data error, not a SEBI reclassification, so
    the open row is corrected in place (it is the only history ingestion recorded)."""
    rows = [(p.scheme_code, p.category_id) for p in parsed if p.plan == "DIRECT"]
    res = await conn.execute(
        """
        WITH amfi AS (
            SELECT DISTINCT ON (s.portfolio_id) s.portfolio_id, v.cat AS category_id
            FROM unnest($1::int[], $2::smallint[]) AS v(code, cat)
            JOIN ref.schemes s ON s.scheme_code = v.code AND s.status = 'ACTIVE'
            ORDER BY s.portfolio_id, (s.option = 'GROWTH') DESC, s.is_canonical DESC
        )
        UPDATE ref.category_history ch SET category_id = amfi.category_id
        FROM amfi
        WHERE ch.portfolio_id = amfi.portfolio_id
          AND ch.valid_to = DATE '9999-12-31'
          AND ch.category_id <> amfi.category_id;
        """,
        [r[0] for r in rows],
        [r[1] for r in rows],
    )
    n = int(res.split()[-1])
    logger.info("Category reconciliation corrected %d category_history rows.", n)
    return n
