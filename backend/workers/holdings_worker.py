"""Holdings ingestion and portfolio summary precomputation worker.

In accordance with:
- Rule 1: Precompute; don't compute on request.
- Rule Q1 & Q2: Point-in-time holdings and market-cap classification.
- Rule Q16: Evidence-based portfolio breakdown without subjective advice.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import asyncpg

from app.config import settings

logger = logging.getLogger("holdings_worker")
logging.basicConfig(level=logging.INFO)

RAW_HOLDINGS_DIR = Path(__file__).resolve().parent.parent / "var" / "data" / "raw" / "holdings"


@dataclass(frozen=True)
class RawHoldingEntry:
    portfolio_id: int
    as_of_date: date
    isin: str | None
    security_name: str
    asset_type: str
    sector: str | None
    quantity: float | None
    market_value_lakhs: float | None
    pct_nav: float
    disclosed_date: date


@dataclass(frozen=True)
class FundProfileEntry:
    portfolio_id: int
    fund_manager: str
    aum_cr: float
    ter_pct: float
    portfolio_turnover_ratio: float
    pe_ratio: float
    pb_ratio: float
    riskometer: str
    min_sip_amount: int


async def ingest_monthly_holdings(
    conn: asyncpg.Connection,
    holdings: Sequence[RawHoldingEntry],
) -> None:
    """Insert raw holdings into holdings.monthly_portfolio."""
    records = [
        (
            h.portfolio_id,
            h.as_of_date,
            h.isin,
            h.security_name,
            h.asset_type,
            h.sector,
            h.quantity,
            h.market_value_lakhs,
            h.pct_nav,
            h.disclosed_date,
        )
        for h in holdings
    ]
    await conn.executemany(
        """
        INSERT INTO holdings.monthly_portfolio (
            portfolio_id, as_of_date, isin, security_name, asset_type,
            sector, quantity, market_value_lakhs, pct_nav, disclosed_date
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT (portfolio_id, as_of_date, security_name) DO UPDATE SET
            isin = EXCLUDED.isin,
            asset_type = EXCLUDED.asset_type,
            sector = EXCLUDED.sector,
            quantity = EXCLUDED.quantity,
            market_value_lakhs = EXCLUDED.market_value_lakhs,
            pct_nav = EXCLUDED.pct_nav,
            disclosed_date = EXCLUDED.disclosed_date;
        """,
        records,
    )


async def precompute_portfolio_summary(
    conn: asyncpg.Connection,
    portfolio_id: int,
    as_of_date: date,
) -> None:
    """Calculate and save precomputed breakdown into holdings.portfolio_summary."""
    holdings_rows = await conn.fetch(
        """
        SELECT h.isin, h.security_name, h.asset_type, h.sector, h.pct_nav, h.disclosed_date,
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
        as_of_date,
    )

    if not holdings_rows:
        return

    equity_count = 0
    top_10_sum = 0.0
    large_cap_pct = 0.0
    mid_cap_pct = 0.0
    small_cap_pct = 0.0
    cash_pct = 0.0
    sector_sums: dict[str, float] = defaultdict(float)
    top_10_list: list[dict[str, Any]] = []
    disclosed_date = holdings_rows[0]["disclosed_date"]

    for _idx, r in enumerate(holdings_rows):
        pct = float(r["pct_nav"])
        asset_type = r["asset_type"]
        sector = r["sector"] or "Others"
        cap_class = r["market_cap_class"]

        if asset_type == "EQUITY":
            equity_count += 1
            sector_sums[sector] += pct
            if len(top_10_list) < 10:
                top_10_sum += pct
                top_10_list.append(
                    {
                        "isin": r["isin"],
                        "security_name": r["security_name"],
                        "pct_nav": round(pct, 2),
                        "sector": sector,
                        "cap_class": cap_class,
                    }
                )

            if cap_class == "LARGE_CAP":
                large_cap_pct += pct
            elif cap_class == "MID_CAP":
                mid_cap_pct += pct
            elif cap_class == "SMALL_CAP":
                small_cap_pct += pct
            else:
                small_cap_pct += pct  # Default unclassified equities to small/other
        elif asset_type in ("TREPS_CASH", "CASH", "MONEY_MARKET"):
            cash_pct += pct

    sector_allocation = [
        {"sector": sec, "pct": round(pct, 2)}
        for sec, pct in sorted(sector_sums.items(), key=lambda x: x[1], reverse=True)
    ]

    await conn.execute(
        """
        INSERT INTO holdings.portfolio_summary (
            portfolio_id, as_of_date, stock_count, top_10_concentration_pct,
            large_cap_pct, mid_cap_pct, small_cap_pct, cash_pct,
            sector_allocation, top_10_holdings, disclosed_date
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        ON CONFLICT (portfolio_id, as_of_date) DO UPDATE SET
            stock_count = EXCLUDED.stock_count,
            top_10_concentration_pct = EXCLUDED.top_10_concentration_pct,
            large_cap_pct = EXCLUDED.large_cap_pct,
            mid_cap_pct = EXCLUDED.mid_cap_pct,
            small_cap_pct = EXCLUDED.small_cap_pct,
            cash_pct = EXCLUDED.cash_pct,
            sector_allocation = EXCLUDED.sector_allocation,
            top_10_holdings = EXCLUDED.top_10_holdings,
            disclosed_date = EXCLUDED.disclosed_date;
        """,
        portfolio_id,
        as_of_date,
        equity_count,
        round(top_10_sum, 2),
        round(large_cap_pct, 2),
        round(mid_cap_pct, 2),
        round(small_cap_pct, 2),
        round(cash_pct, 2),
        json.dumps(sector_allocation),
        json.dumps(top_10_list),
        disclosed_date,
    )


async def ingest_amc_workbook(
    conn: asyncpg.Connection,
    amc_parser: Any,
    workbook_data: Any,
    portfolio_id: int,
    as_of_date: date,
    disclosed_date: date,
    scheme_filter: str | None = None,
) -> Any:
    """Parse, ingest, and precompute summary for an AMC workbook adhering to H1-H8."""
    result = amc_parser.parse_workbook(
        workbook_data,
        portfolio_id=portfolio_id,
        as_of_date=as_of_date,
        disclosed_date=disclosed_date,
        scheme_name_filter=scheme_filter,
    )
    if not result.valid:
        logger.error("AMC parse failed for portfolio %d: %s", portfolio_id, result.validation_message)
        return result

    await ingest_monthly_holdings(conn, result.holdings)
    await precompute_portfolio_summary(conn, portfolio_id, as_of_date)
    logger.info("Successfully ingested %d holdings for portfolio %d.", len(result.holdings), portfolio_id)
    return result


async def upsert_fund_profile(
    conn: asyncpg.Connection,
    profile: FundProfileEntry,
) -> None:
    """Upsert fund profile reference metrics."""
    await conn.execute(
        """
        INSERT INTO ref.fund_profile (
            portfolio_id, fund_manager, aum_cr, ter_pct,
            portfolio_turnover_ratio, pe_ratio, pb_ratio, riskometer, min_sip_amount
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (portfolio_id) DO UPDATE SET
            fund_manager = EXCLUDED.fund_manager,
            aum_cr = EXCLUDED.aum_cr,
            ter_pct = EXCLUDED.ter_pct,
            portfolio_turnover_ratio = EXCLUDED.portfolio_turnover_ratio,
            pe_ratio = EXCLUDED.pe_ratio,
            pb_ratio = EXCLUDED.pb_ratio,
            riskometer = EXCLUDED.riskometer,
            min_sip_amount = EXCLUDED.min_sip_amount,
            updated_at = now();
        """,
        profile.portfolio_id,
        profile.fund_manager,
        profile.aum_cr,
        profile.ter_pct,
        profile.portfolio_turnover_ratio,
        profile.pe_ratio,
        profile.pb_ratio,
        profile.riskometer,
        profile.min_sip_amount,
    )


SAMPLE_PORTFOLIO_HOLDINGS: dict[int, list[tuple[str, str, str, str, float]]] = {
    # 101: Nippon India Small Cap Fund
    101: [
        ("INE548C01032", "Suzlon Energy Ltd", "EQUITY", "Capital Goods", 4.25),
        ("INE429C01035", "Titagarh Rail Systems Ltd", "EQUITY", "Capital Goods", 3.85),
        ("INE705A01016", "Kalyan Jewellers India Ltd", "EQUITY", "Consumer Durables", 3.50),
        ("INE285J01028", "Marksans Pharma Ltd", "EQUITY", "Healthcare", 3.10),
        ("INE053F01010", "Federal Bank Ltd", "EQUITY", "Financial Services", 2.90),
        ("INE140A01024", "Piramal Enterprises Ltd", "EQUITY", "Financial Services", 2.65),
        ("INE001A01036", "Housing & Urban Dev Corp Ltd", "EQUITY", "Financial Services", 2.45),
        ("INE121J01017", "Bharti Hexacom Ltd", "EQUITY", "Telecommunication", 2.20),
        ("INE752E01010", "Power Finance Corp Ltd", "EQUITY", "Financial Services", 2.10),
        ("INE040A01034", "HDFC Bank Ltd", "EQUITY", "Financial Services", 1.95),
        ("INE002A01018", "Reliance Industries Ltd", "EQUITY", "Energy", 1.80),
        ("INE090A01021", "ICICI Bank Ltd", "EQUITY", "Financial Services", 1.65),
        ("TREPS0000001", "TREPS / Reverse Repo Cash", "TREPS_CASH", "Cash & Equivalents", 4.50),
    ],
    # 103: HDFC Small Cap Fund
    103: [
        ("INE053F01010", "Federal Bank Ltd", "EQUITY", "Financial Services", 4.80),
        ("INE705A01016", "Kalyan Jewellers India Ltd", "EQUITY", "Consumer Durables", 4.20),
        ("INE429C01035", "Titagarh Rail Systems Ltd", "EQUITY", "Capital Goods", 3.60),
        ("INE040A01034", "HDFC Bank Ltd", "EQUITY", "Financial Services", 3.40),
        ("INE018A01030", "Larsen & Toubro Ltd", "EQUITY", "Capital Goods", 3.10),
        ("INE285J01028", "Marksans Pharma Ltd", "EQUITY", "Healthcare", 2.80),
        ("INE752E01010", "Power Finance Corp Ltd", "EQUITY", "Financial Services", 2.50),
        ("INE238A01034", "Axis Bank Ltd", "EQUITY", "Financial Services", 2.30),
        ("INE062A01020", "State Bank of India", "EQUITY", "Financial Services", 2.10),
        ("INE154A01025", "ITC Ltd", "EQUITY", "Fast Moving Consumer Goods", 1.90),
        ("TREPS0000001", "TREPS / Reverse Repo Cash", "TREPS_CASH", "Cash & Equivalents", 5.20),
    ],
    # 111: Parag Parikh Flexi Cap Fund
    111: [
        ("INE040A01034", "HDFC Bank Ltd", "EQUITY", "Financial Services", 8.40),
        ("INE090A01021", "ICICI Bank Ltd", "EQUITY", "Financial Services", 7.80),
        ("INE154A01025", "ITC Ltd", "EQUITY", "Fast Moving Consumer Goods", 6.90),
        ("INE467B01029", "Tata Consultancy Services Ltd", "EQUITY", "IT", 6.20),
        ("INE062A01020", "State Bank of India", "EQUITY", "Financial Services", 5.50),
        ("INE002A01018", "Reliance Industries Ltd", "EQUITY", "Energy", 5.10),
        ("INE018A01030", "Larsen & Toubro Ltd", "EQUITY", "Capital Goods", 4.80),
        ("INE009A01021", "Infosys Ltd", "EQUITY", "IT", 4.50),
        ("INE238A01034", "Axis Bank Ltd", "EQUITY", "Financial Services", 4.20),
        ("INE030A01027", "Hindustan Unilever Ltd", "EQUITY", "Fast Moving Consumer Goods", 3.90),
        ("TREPS0000001", "TREPS / Reverse Repo Cash", "TREPS_CASH", "Cash & Equivalents", 7.50),
    ],
    # 113: ICICI Prudential Bluechip Fund
    113: [
        ("INE090A01021", "ICICI Bank Ltd", "EQUITY", "Financial Services", 9.20),
        ("INE002A01018", "Reliance Industries Ltd", "EQUITY", "Energy", 8.90),
        ("INE040A01034", "HDFC Bank Ltd", "EQUITY", "Financial Services", 8.10),
        ("INE009A01021", "Infosys Ltd", "EQUITY", "IT", 7.30),
        ("INE018A01030", "Larsen & Toubro Ltd", "EQUITY", "Capital Goods", 6.50),
        ("INE467B01029", "Tata Consultancy Services Ltd", "EQUITY", "IT", 5.80),
        ("INE397D01024", "Bharti Airtel Ltd", "EQUITY", "Telecommunication", 5.40),
        ("INE154A01025", "ITC Ltd", "EQUITY", "Fast Moving Consumer Goods", 4.70),
        ("INE062A01020", "State Bank of India", "EQUITY", "Financial Services", 4.10),
        ("INE238A01034", "Axis Bank Ltd", "EQUITY", "Financial Services", 3.80),
        ("TREPS0000001", "TREPS / Reverse Repo Cash", "TREPS_CASH", "Cash & Equivalents", 3.20),
    ],
}

SAMPLE_FUND_PROFILES: list[FundProfileEntry] = [
    FundProfileEntry(
        portfolio_id=101,
        fund_manager="Samir Rachh & Kinjal Desai",
        aum_cr=58400.0,
        ter_pct=0.71,
        portfolio_turnover_ratio=22.0,
        pe_ratio=24.8,
        pb_ratio=3.8,
        riskometer="Very High",
        min_sip_amount=100,
    ),
    FundProfileEntry(
        portfolio_id=102,
        fund_manager="Sandeep Tandon & Ankit Pande",
        aum_cr=26800.0,
        ter_pct=0.77,
        portfolio_turnover_ratio=84.0,
        pe_ratio=21.2,
        pb_ratio=3.4,
        riskometer="Very High",
        min_sip_amount=1000,
    ),
    FundProfileEntry(
        portfolio_id=103,
        fund_manager="Chirag Setalvad",
        aum_cr=34100.0,
        ter_pct=0.69,
        portfolio_turnover_ratio=18.0,
        pe_ratio=23.2,
        pb_ratio=3.5,
        riskometer="Very High",
        min_sip_amount=500,
    ),
    FundProfileEntry(
        portfolio_id=104,
        fund_manager="R. Srinivasan",
        aum_cr=31200.0,
        ter_pct=0.72,
        portfolio_turnover_ratio=21.0,
        pe_ratio=25.1,
        pb_ratio=3.9,
        riskometer="Very High",
        min_sip_amount=500,
    ),
    FundProfileEntry(
        portfolio_id=105,
        fund_manager="Pankaj Tibrewal",
        aum_cr=17500.0,
        ter_pct=0.65,
        portfolio_turnover_ratio=26.0,
        pe_ratio=24.0,
        pb_ratio=3.7,
        riskometer="Very High",
        min_sip_amount=500,
    ),
    FundProfileEntry(
        portfolio_id=106,
        fund_manager="Shreyash Devalkar",
        aum_cr=22400.0,
        ter_pct=0.58,
        portfolio_turnover_ratio=19.0,
        pe_ratio=26.2,
        pb_ratio=4.1,
        riskometer="Very High",
        min_sip_amount=100,
    ),
    FundProfileEntry(
        portfolio_id=107,
        fund_manager="Chandraprakash Padiyar",
        aum_cr=8200.0,
        ter_pct=0.62,
        portfolio_turnover_ratio=24.0,
        pe_ratio=22.8,
        pb_ratio=3.3,
        riskometer="Very High",
        min_sip_amount=100,
    ),
    FundProfileEntry(
        portfolio_id=108,
        fund_manager="Manish Gunwani",
        aum_cr=5400.0,
        ter_pct=0.55,
        portfolio_turnover_ratio=38.0,
        pe_ratio=20.9,
        pb_ratio=3.1,
        riskometer="Very High",
        min_sip_amount=100,
    ),
    FundProfileEntry(
        portfolio_id=109,
        fund_manager="Taher Badshah",
        aum_cr=4900.0,
        ter_pct=0.64,
        portfolio_turnover_ratio=29.0,
        pe_ratio=23.5,
        pb_ratio=3.6,
        riskometer="Very High",
        min_sip_amount=500,
    ),
    FundProfileEntry(
        portfolio_id=110,
        fund_manager="Resham Jain & Vinit Sambre",
        aum_cr=15800.0,
        ter_pct=0.74,
        portfolio_turnover_ratio=23.0,
        pe_ratio=24.5,
        pb_ratio=3.8,
        riskometer="Very High",
        min_sip_amount=500,
    ),
    FundProfileEntry(
        portfolio_id=201,
        fund_manager="Rajeev Thakkar & Raunak Onkar",
        aum_cr=68500.0,
        ter_pct=0.62,
        portfolio_turnover_ratio=14.0,
        pe_ratio=22.4,
        pb_ratio=3.2,
        riskometer="Very High",
        min_sip_amount=1000,
    ),
    FundProfileEntry(
        portfolio_id=202,
        fund_manager="Roshi Jain",
        aum_cr=59200.0,
        ter_pct=0.75,
        portfolio_turnover_ratio=34.0,
        pe_ratio=21.8,
        pb_ratio=3.1,
        riskometer="Very High",
        min_sip_amount=100,
    ),
    FundProfileEntry(
        portfolio_id=113,
        fund_manager="Anish Tawakley & Vaibhav Dusad",
        aum_cr=55200.0,
        ter_pct=0.88,
        portfolio_turnover_ratio=31.0,
        pe_ratio=21.5,
        pb_ratio=2.9,
        riskometer="Very High",
        min_sip_amount=100,
    ),
]


async def ingest_all_amc_disclosures(as_of: date = date(2026, 8, 31)) -> dict[str, Any]:
    """Ingest authentic downloaded monthly portfolio workbooks for registered AMCs."""
    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        disclosed = date(as_of.year, as_of.month + 1 if as_of.month < 12 else 1, 10)
        from workers.parsers.generic_amc import HDFCParser, PPFASParser, QuantParser, SBIParser
        from workers.parsers.nippon import NipponIndiaParser

        plans = [
            ("PPFAS Flexi Cap", PPFASParser(), RAW_HOLDINGS_DIR / "ppfas" / f"{as_of.isoformat()}_portfolio.xlsx", 201, "Flexi Cap"),
            ("Nippon Small Cap", NipponIndiaParser(), RAW_HOLDINGS_DIR / "nippon" / f"{as_of.isoformat()}_portfolio.xlsx", 101, "Small Cap"),
            ("HDFC Small Cap", HDFCParser(), RAW_HOLDINGS_DIR / "hdfc" / f"{as_of.isoformat()}_hdfc_small_cap.xlsx", 103, "Small Cap"),
            ("HDFC Flexi Cap", HDFCParser(), RAW_HOLDINGS_DIR / "hdfc" / f"{as_of.isoformat()}_hdfc_flexi_cap.xlsx", 202, "Flexi Cap"),
            ("SBI Small Cap", SBIParser(), RAW_HOLDINGS_DIR / "sbi" / f"{as_of.isoformat()}_portfolio.xlsx", 104, "Small Cap"),
            ("Quant Small Cap", QuantParser(), RAW_HOLDINGS_DIR / "quant" / f"{as_of.isoformat()}_portfolio.xlsx", 102, "Small Cap"),
        ]

        results = {}
        for label, parser, file_path, pid, filter_name in plans:
            if not file_path.exists():
                logger.warning("Disclosure file not found for %s at %s", label, file_path)
                continue
            logger.info("Ingesting authentic disclosure for %s (PID %d)...", label, pid)
            with open(file_path, "rb") as f:
                data = f.read()
            res = await ingest_amc_workbook(
                conn,
                amc_parser=parser,
                workbook_data=io.BytesIO(data),
                portfolio_id=pid,
                as_of_date=as_of,
                disclosed_date=disclosed,
                scheme_filter=filter_name,
            )
            results[label] = {
                "portfolio_id": pid,
                "valid": res.valid,
                "holdings_count": len(res.holdings),
                "total_weight": res.total_weight,
                "equities_count": res.equity_count,
            }

        for prof in SAMPLE_FUND_PROFILES:
            await upsert_fund_profile(conn, prof)

        logger.info("Ingestion completed for %d portfolios.", len(results))
        return results
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(ingest_all_amc_disclosures())

