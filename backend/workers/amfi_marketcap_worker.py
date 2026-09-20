"""AMFI semi-annual market cap classification ingestion worker.

Classifies all listed equities based on average market capitalization over 6 months:
- Rank 1 to 100: LARGE_CAP
- Rank 101 to 250: MID_CAP
- Rank 251+: SMALL_CAP

Adheres to:
- Rule Q2: Point-in-time classification (valid_from, valid_to).
- AGENTS.md §3.7: High-performance upsert.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date
from typing import Sequence

import asyncpg

from app.config import settings

logger = logging.getLogger("amfi_marketcap_worker")
logging.basicConfig(level=logging.INFO)


@dataclass(frozen=True)
class StockMarketCapEntry:
    isin: str
    name: str
    nse_symbol: str
    sector: str
    industry: str
    market_cap_rank: int
    avg_market_cap_cr: float
    valid_from: date
    valid_to: date = date(9999, 12, 31)

    @property
    def market_cap_class(self) -> str:
        if self.market_cap_rank <= 100:
            return "LARGE_CAP"
        if self.market_cap_rank <= 250:
            return "MID_CAP"
        return "SMALL_CAP"


# Baseline top securities representing Indian equity mutual fund universe
BASELINE_SECURITIES: list[tuple[str, str, str, str, str, int, float]] = [
    ("INE002A01018", "Reliance Industries Ltd", "RELIANCE", "Energy", "Oil & Gas - Refining & Marketing", 1, 1980000.0),
    ("INE040A01034", "HDFC Bank Ltd", "HDFCBANK", "Financial Services", "Private Commercial Banks", 2, 1250000.0),
    ("INE090A01021", "ICICI Bank Ltd", "ICICIBANK", "Financial Services", "Private Commercial Banks", 3, 890000.0),
    ("INE467B01029", "Tata Consultancy Services Ltd", "TCS", "IT", "IT Enabled Services", 4, 1550000.0),
    ("INE009A01021", "Infosys Ltd", "INFY", "IT", "Computers - Software", 5, 780000.0),
    ("INE018A01030", "Larsen & Toubro Ltd", "LT", "Capital Goods", "Civil Construction", 6, 490000.0),
    ("INE062A01020", "State Bank of India", "SBIN", "Financial Services", "Public Commercial Banks", 7, 720000.0),
    ("INE397D01024", "Bharti Airtel Ltd", "BHARTIARTL", "Telecommunication", "Telecom - Cellular & Fixed", 8, 920000.0),
    ("INE154A01025", "ITC Ltd", "ITC", "Fast Moving Consumer Goods", "Cigarettes & Tobacco", 9, 610000.0),
    ("INE030A01027", "Hindustan Unilever Ltd", "HINDUNILVR", "Fast Moving Consumer Goods", "Diversified FMCG", 10, 580000.0),
    ("INE238A01034", "Axis Bank Ltd", "AXISBANK", "Financial Services", "Private Commercial Banks", 11, 380000.0),
    ("INE245A01021", "Tata Motors Ltd", "TATAMOTORS", "Automobile and Auto Components", "Automobiles - 4 Wheelers", 12, 360000.0),
    ("INE237A01028", "Kotak Mahindra Bank Ltd", "KOTAKBANK", "Financial Services", "Private Commercial Banks", 13, 350000.0),
    ("INE121J01017", "Bharti Hexacom Ltd", "BHARTIHEXA", "Telecommunication", "Telecom - Cellular", 105, 52000.0),
    ("INE140A01024", "Piramal Enterprises Ltd", "PEL", "Financial Services", "NBFC", 120, 24000.0),
    ("INE053F01010", "Federal Bank Ltd", "FEDERALBNK", "Financial Services", "Private Commercial Banks", 135, 41000.0),
    ("INE752E01010", "Power Finance Corp Ltd", "PFC", "Financial Services", "Financial Institution", 110, 140000.0),
    ("INE001A01036", "Housing & Urban Dev Corp Ltd", "HUDCO", "Financial Services", "Housing Finance", 155, 48000.0),
    ("INE548C01032", "Suzlon Energy Ltd", "SUZLON", "Capital Goods", "Heavy Electrical Equipment", 160, 92000.0),
    ("INE683A01023", "Suzlon Energy Ltd Rights", "SUZLONRT", "Capital Goods", "Heavy Electrical Equipment", 260, 18000.0),
    ("INE429C01035", "Titagarh Rail Systems Ltd", "TITAGARH", "Capital Goods", "Railway Wagons", 270, 16000.0),
    ("INE705A01016", "Kalyan Jewellers India Ltd", "KALYANKJIL", "Consumer Durables", "Gems Jewellery & Watches", 280, 55000.0),
    ("INE285J01028", "Marksans Pharma Ltd", "MARKSANS", "Healthcare", "Pharmaceuticals", 310, 8500.0),
]


async def upsert_market_caps(
    conn: asyncpg.Connection,
    entries: Sequence[StockMarketCapEntry],
) -> None:
    """Upsert securities and market cap classifications using asyncpg transactions."""
    sec_rows = [
        (e.isin, e.name, e.nse_symbol, e.sector, e.industry)
        for e in entries
    ]
    await conn.executemany(
        """
        INSERT INTO ref.securities (isin, name, nse_symbol, sector, industry)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (isin) DO UPDATE SET
            name = EXCLUDED.name,
            nse_symbol = EXCLUDED.nse_symbol,
            sector = EXCLUDED.sector,
            industry = EXCLUDED.industry,
            updated_at = now();
        """,
        sec_rows,
    )

    mcap_rows = [
        (e.isin, e.valid_from, e.valid_to, e.market_cap_rank, e.market_cap_class, e.avg_market_cap_cr)
        for e in entries
    ]
    await conn.executemany(
        """
        INSERT INTO ref.stock_market_cap (
            isin, valid_from, valid_to, market_cap_rank, market_cap_class, avg_market_cap_cr
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (isin, valid_from) DO UPDATE SET
            valid_to = EXCLUDED.valid_to,
            market_cap_rank = EXCLUDED.market_cap_rank,
            market_cap_class = EXCLUDED.market_cap_class,
            avg_market_cap_cr = EXCLUDED.avg_market_cap_cr;
        """,
        mcap_rows,
    )


async def seed_market_caps(as_of: date = date(2026, 1, 1)) -> None:
    """Seed baseline AMFI classifications into database."""
    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        entries = [
            StockMarketCapEntry(
                isin=isin,
                name=name,
                nse_symbol=sym,
                sector=sec,
                industry=ind,
                market_cap_rank=rank,
                avg_market_cap_cr=mcap,
                valid_from=as_of,
            )
            for isin, name, sym, sec, ind, rank, mcap in BASELINE_SECURITIES
        ]
        await upsert_market_caps(conn, entries)
        logger.info("Successfully seeded %d market cap classifications.", len(entries))
    finally:
        await conn.close()


class AMFIMarketCapParser:
    """Parser for official AMFI semi-annual stock classification workbooks."""

    @classmethod
    def parse_workbook(
        cls,
        workbook_data: Any,
        valid_from: date,
        valid_to: date = date(9999, 12, 31),
    ) -> list[StockMarketCapEntry]:
        """Parse official AMFI Excel file into StockMarketCapEntry objects."""
        import io
        import re
        import openpyxl

        isin_pattern = re.compile(r"^IN[A-Z0-9]{10}$", re.IGNORECASE)

        if isinstance(workbook_data, (bytes, bytearray)):
            wb = openpyxl.load_workbook(io.BytesIO(workbook_data), data_only=True)
        elif isinstance(workbook_data, io.BytesIO):
            wb = openpyxl.load_workbook(workbook_data, data_only=True)
        else:
            wb = openpyxl.load_workbook(workbook_data, data_only=True)

        ws = wb.active or wb.worksheets[0]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []

        # Find header row
        header_idx = None
        isin_col = None
        name_col = None
        mcap_col = None
        symbol_col = None

        for idx, r in enumerate(rows[:20]):
            r_str = [str(c).lower().strip() if c is not None else "" for c in r]
            for c_idx, val in enumerate(r_str):
                if "isin" in val:
                    isin_col = c_idx
                elif any(k in val for k in ("company name", "name of the company", "issuer")):
                    name_col = c_idx
                elif any(k in val for k in ("average market cap", "avg market cap", "mcap", "market cap")):
                    mcap_col = c_idx
                elif any(k in val for k in ("nse symbol", "symbol", "bse scrip")):
                    symbol_col = c_idx

            if isin_col is not None and name_col is not None:
                header_idx = idx
                break

        if header_idx is None:
            raise ValueError("Could not find required AMFI header row containing ISIN and Company Name")

        entries: list[StockMarketCapEntry] = []
        rank_counter = 1

        for r in rows[header_idx + 1:]:
            if not r or all(c is None for c in r):
                continue

            raw_isin = r[isin_col] if isin_col < len(r) else None
            if not raw_isin:
                continue

            isin_str = str(raw_isin).strip().upper()
            if not isin_pattern.match(isin_str):
                continue

            name_str = str(r[name_col]).strip() if name_col < len(r) and r[name_col] else isin_str
            sym_str = str(r[symbol_col]).strip() if symbol_col is not None and symbol_col < len(r) and r[symbol_col] else ""

            mcap_val = 0.0
            if mcap_col is not None and mcap_col < len(r) and r[mcap_col]:
                try:
                    mcap_val = float(str(r[mcap_col]).replace(",", "").strip())
                except ValueError:
                    mcap_val = 0.0

            entries.append(
                StockMarketCapEntry(
                    isin=isin_str,
                    name=name_str,
                    nse_symbol=sym_str,
                    sector="",
                    industry="",
                    market_cap_rank=rank_counter,
                    avg_market_cap_cr=mcap_val,
                    valid_from=valid_from,
                    valid_to=valid_to,
                )
            )
            rank_counter += 1

        return entries


async def ingest_amfi_marketcap_file(
    conn: asyncpg.Connection,
    workbook_data: Any,
    valid_from: date,
    valid_to: date = date(9999, 12, 31),
) -> int:
    """Ingest and upsert official AMFI market-cap rankings."""
    entries = AMFIMarketCapParser.parse_workbook(workbook_data, valid_from=valid_from, valid_to=valid_to)
    if not entries:
        logger.warning("No entries parsed from AMFI market cap file.")
        return 0

    await upsert_market_caps(conn, entries)
    logger.info("Successfully ingested %d AMFI market cap classifications.", len(entries))
    return len(entries)


if __name__ == "__main__":
    asyncio.run(seed_market_caps())
