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
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

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
    (
        "INE002A01018",
        "Reliance Industries Ltd",
        "RELIANCE",
        "Energy",
        "Oil & Gas - Refining & Marketing",
        1,
        1980000.0,
    ),
    (
        "INE040A01034",
        "HDFC Bank Ltd",
        "HDFCBANK",
        "Financial Services",
        "Private Commercial Banks",
        2,
        1250000.0,
    ),
    (
        "INE090A01021",
        "ICICI Bank Ltd",
        "ICICIBANK",
        "Financial Services",
        "Private Commercial Banks",
        3,
        890000.0,
    ),
    (
        "INE467B01029",
        "Tata Consultancy Services Ltd",
        "TCS",
        "IT",
        "IT Enabled Services",
        4,
        1550000.0,
    ),
    ("INE009A01021", "Infosys Ltd", "INFY", "IT", "Computers - Software", 5, 780000.0),
    (
        "INE018A01030",
        "Larsen & Toubro Ltd",
        "LT",
        "Capital Goods",
        "Civil Construction",
        6,
        490000.0,
    ),
    (
        "INE062A01020",
        "State Bank of India",
        "SBIN",
        "Financial Services",
        "Public Commercial Banks",
        7,
        720000.0,
    ),
    (
        "INE397D01024",
        "Bharti Airtel Ltd",
        "BHARTIARTL",
        "Telecommunication",
        "Telecom - Cellular & Fixed",
        8,
        920000.0,
    ),
    (
        "INE154A01025",
        "ITC Ltd",
        "ITC",
        "Fast Moving Consumer Goods",
        "Cigarettes & Tobacco",
        9,
        610000.0,
    ),
    (
        "INE030A01027",
        "Hindustan Unilever Ltd",
        "HINDUNILVR",
        "Fast Moving Consumer Goods",
        "Diversified FMCG",
        10,
        580000.0,
    ),
    (
        "INE238A01034",
        "Axis Bank Ltd",
        "AXISBANK",
        "Financial Services",
        "Private Commercial Banks",
        11,
        380000.0,
    ),
    (
        "INE245A01021",
        "Tata Motors Ltd",
        "TATAMOTORS",
        "Automobile and Auto Components",
        "Automobiles - 4 Wheelers",
        12,
        360000.0,
    ),
    (
        "INE237A01028",
        "Kotak Mahindra Bank Ltd",
        "KOTAKBANK",
        "Financial Services",
        "Private Commercial Banks",
        13,
        350000.0,
    ),
    (
        "INE121J01017",
        "Bharti Hexacom Ltd",
        "BHARTIHEXA",
        "Telecommunication",
        "Telecom - Cellular",
        105,
        52000.0,
    ),
    ("INE140A01024", "Piramal Enterprises Ltd", "PEL", "Financial Services", "NBFC", 120, 24000.0),
    (
        "INE053F01010",
        "Federal Bank Ltd",
        "FEDERALBNK",
        "Financial Services",
        "Private Commercial Banks",
        135,
        41000.0,
    ),
    (
        "INE752E01010",
        "Power Finance Corp Ltd",
        "PFC",
        "Financial Services",
        "Financial Institution",
        110,
        140000.0,
    ),
    (
        "INE001A01036",
        "Housing & Urban Dev Corp Ltd",
        "HUDCO",
        "Financial Services",
        "Housing Finance",
        155,
        48000.0,
    ),
    (
        "INE548C01032",
        "Suzlon Energy Ltd",
        "SUZLON",
        "Capital Goods",
        "Heavy Electrical Equipment",
        160,
        92000.0,
    ),
    (
        "INE683A01023",
        "Suzlon Energy Ltd Rights",
        "SUZLONRT",
        "Capital Goods",
        "Heavy Electrical Equipment",
        260,
        18000.0,
    ),
    (
        "INE429C01035",
        "Titagarh Rail Systems Ltd",
        "TITAGARH",
        "Capital Goods",
        "Railway Wagons",
        270,
        16000.0,
    ),
    (
        "INE705A01016",
        "Kalyan Jewellers India Ltd",
        "KALYANKJIL",
        "Consumer Durables",
        "Gems Jewellery & Watches",
        280,
        55000.0,
    ),
    (
        "INE285J01028",
        "Marksans Pharma Ltd",
        "MARKSANS",
        "Healthcare",
        "Pharmaceuticals",
        310,
        8500.0,
    ),
    (
        "INE974X01010",
        "Tube Investments of India Ltd",
        "TIINDIA",
        "Automobile",
        "Auto Components",
        115,
        75000.0,
    ),
    (
        "INE372A01015",
        "Apar Industries Ltd",
        "APARINDS",
        "Capital Goods",
        "Heavy Electrical Equipment",
        145,
        38000.0,
    ),
    (
        "INE036D01028",
        "Karur Vysya Bank Ltd",
        "KVB",
        "Financial Services",
        "Private Commercial Banks",
        210,
        18000.0,
    ),
    (
        "INE745G01035",
        "Multi Commodity Exchange of India Ltd",
        "MCX",
        "Financial Services",
        "Other Financial Services",
        175,
        29000.0,
    ),
    (
        "INE010J01012",
        "Tejas Networks Ltd",
        "TEJASNET",
        "Telecommunication",
        "Telecom - Equipment",
        190,
        21000.0,
    ),
    (
        "INE117A01022",
        "ABB India Ltd",
        "ABB",
        "Capital Goods",
        "Heavy Electrical Equipment",
        75,
        165000.0,
    ),
    (
        "INE012A01025",
        "ACC Ltd",
        "ACC",
        "Construction Materials",
        "Cement & Cement Products",
        125,
        42000.0,
    ),
    (
        "INE437A01024",
        "Apollo Hospitals Enterprise Ltd",
        "APOLLOHOSP",
        "Healthcare",
        "Healthcare Services",
        65,
        95000.0,
    ),
    ("INE021A01026", "Asian Paints Ltd", "ASIANPAINT", "Consumer Durables", "Paints", 22, 280000.0),
    (
        "INE216A01030",
        "Bharat Electronics Ltd",
        "BEL",
        "Capital Goods",
        "Aerospace & Defense",
        35,
        220000.0,
    ),
    (
        "INE029A01011",
        "Bharat Petroleum Corp Ltd",
        "BPCL",
        "Energy",
        "Oil & Gas - Refining & Marketing",
        45,
        140000.0,
    ),
    ("INE059A01026", "Cipla Ltd", "CIPLA", "Healthcare", "Pharmaceuticals", 38, 125000.0),
    (
        "INE522F01014",
        "Coal India Ltd",
        "COALINDIA",
        "Metals & Mining",
        "Consumable Fuels",
        25,
        290000.0,
    ),
    (
        "INE361B01024",
        "Divis Laboratories Ltd",
        "DIVISLAB",
        "Healthcare",
        "Pharmaceuticals",
        50,
        140000.0,
    ),
    (
        "INE047A01021",
        "Grasim Industries Ltd",
        "GRASIM",
        "Construction Materials",
        "Cement & Cement Products",
        48,
        165000.0,
    ),
    ("INE860A01027", "HCL Technologies Ltd", "HCLTECH", "IT", "Computers - Software", 15, 480000.0),
    (
        "INE176B01034",
        "Havells India Ltd",
        "HAVELLS",
        "Consumer Durables",
        "Consumer Electronics",
        60,
        115000.0,
    ),
    (
        "INE585B01010",
        "Maruti Suzuki India Ltd",
        "MARUTI",
        "Automobile",
        "Automobiles - 4 Wheelers",
        18,
        380000.0,
    ),
    ("INE733E01010", "NTPC Ltd", "NTPC", "Power", "Power Generation", 14, 395000.0),
    (
        "INE213A01029",
        "Oil & Natural Gas Corp Ltd",
        "ONGC",
        "Energy",
        "Oil & Gas - Exploration & Production",
        16,
        370000.0,
    ),
    ("INE075A01022", "Wipro Ltd", "WIPRO", "IT", "Computers - Software", 28, 260000.0),
    ("INE758T01015", "Zomato Ltd", "ZOMATO", "Consumer Services", "Retailing", 42, 225000.0),
    (
        "INE192A01025",
        "Tata Steel Ltd",
        "TATASTEEL",
        "Metals & Mining",
        "Ferrous Metals",
        20,
        210000.0,
    ),
    ("INE081A01020", "Tata Power Co Ltd", "TATAPOWER", "Power", "Integrated Power", 55, 135000.0),
    (
        "INE481G01011",
        "UltraTech Cement Ltd",
        "ULTRACEMCO",
        "Construction Materials",
        "Cement & Cement Products",
        24,
        320000.0,
    ),
    (
        "INE881D01027",
        "Persistent Systems Ltd",
        "PERSISTENT",
        "IT",
        "Computers - Software",
        130,
        85000.0,
    ),
    (
        "INE669E01016",
        "Vodafone Idea Ltd",
        "IDEA",
        "Telecommunication",
        "Telecom - Cellular",
        108,
        95000.0,
    ),
    (
        "INE721A01013",
        "Shriram Finance Ltd",
        "SHRIRAMFIN",
        "Financial Services",
        "NBFC",
        40,
        115000.0,
    ),
    (
        "INE089A01023",
        "Dr Reddys Laboratories Ltd",
        "DRREDDY",
        "Healthcare",
        "Pharmaceuticals",
        36,
        110000.0,
    ),
    (
        "INE152A01029",
        "Bajaj Auto Ltd",
        "BAJAJ-AUTO",
        "Automobile",
        "Automobiles - 2 & 3 Wheelers",
        30,
        280000.0,
    ),
    (
        "INE917I01012",
        "Bajaj Finserv Ltd",
        "BAJAJFINSV",
        "Financial Services",
        "Financial Institution",
        32,
        290000.0,
    ),
    ("INE296A01024", "Bajaj Finance Ltd", "BAJFINANCE", "Financial Services", "NBFC", 17, 440000.0),
    (
        "INE066A01021",
        "Bank of Baroda",
        "BANKBARODA",
        "Financial Services",
        "Public Commercial Banks",
        52,
        130000.0,
    ),
    (
        "INE528G01035",
        "Yes Bank Ltd",
        "YESBANK",
        "Financial Services",
        "Private Commercial Banks",
        118,
        68000.0,
    ),
    (
        "INE848E01016",
        "CG Power and Industrial Solutions",
        "CGPOWER",
        "Capital Goods",
        "Heavy Electrical Equipment",
        85,
        110000.0,
    ),
    (
        "INE067A01029",
        "Canara Bank",
        "CANBK",
        "Financial Services",
        "Public Commercial Banks",
        80,
        105000.0,
    ),
    ("INE205A01025", "Vedanta Ltd", "VEDL", "Metals & Mining", "Diversified Metals", 62, 185000.0),
    (
        "INE111A01025",
        "Indian Hotels Co Ltd",
        "INDHOTEL",
        "Consumer Services",
        "Hotels & Resorts",
        95,
        98000.0,
    ),
    (
        "INE160A01022",
        "Punjab National Bank",
        "PNB",
        "Financial Services",
        "Public Commercial Banks",
        78,
        120000.0,
    ),
    (
        "INE121A01024",
        "Cholamandalam Investment & Finance",
        "CHOLAFIN",
        "Financial Services",
        "NBFC",
        82,
        125000.0,
    ),
    (
        "INE028A01039",
        "Bank of India",
        "BANKINDIA",
        "Financial Services",
        "Public Commercial Banks",
        140,
        52000.0,
    ),
    ("INE271C01023", "DLF Ltd", "DLF", "Realty", "Real Estate Development", 58, 210000.0),
    (
        "INE257A01026",
        "Bharat Heavy Electricals Ltd",
        "BHEL",
        "Capital Goods",
        "Heavy Electrical Equipment",
        90,
        95000.0,
    ),
    ("INE134E01011", "Trent Ltd", "TRENT", "Consumer Services", "Retailing", 26, 260000.0),
    (
        "INE755601014",
        "Max Healthcare Institute Ltd",
        "MAXHEALTH",
        "Healthcare",
        "Healthcare Services",
        92,
        92000.0,
    ),
    ("INE326A01037", "Lupin Ltd", "LUPIN", "Healthcare", "Pharmaceuticals", 102, 94000.0),
    (
        "INE463A01028",
        "Torrent Pharmaceuticals Ltd",
        "TORNTPHARM",
        "Healthcare",
        "Pharmaceuticals",
        88,
        115000.0,
    ),
    (
        "INE503A01015",
        "Siemens Ltd",
        "SIEMENS",
        "Capital Goods",
        "Heavy Electrical Equipment",
        44,
        245000.0,
    ),
    (
        "INE019A01038",
        "JSW Steel Ltd",
        "JSWSTEEL",
        "Metals & Mining",
        "Ferrous Metals",
        27,
        230000.0,
    ),
    (
        "INE128A01029",
        "Sun Pharmaceutical Industries Ltd",
        "SUNPHARMA",
        "Healthcare",
        "Pharmaceuticals",
        19,
        410000.0,
    ),
    (
        "INE472A01039",
        "Blue Star Ltd",
        "BLUESTAR",
        "Consumer Durables",
        "Air Conditioners",
        225,
        34000.0,
    ),
    ("INE136B01020", "Cyient Ltd", "CYIENT", "IT", "Computers - Software", 260, 21000.0),
    ("INE836A01035", "Birlasoft Ltd", "BSOFT", "IT", "Computers - Software", 265, 19500.0),
    ("INE383A01012", "Firstsource Solutions Ltd", "FSL", "IT", "IT Enabled Services", 270, 18500.0),
    (
        "INE769A01020",
        "Aarti Industries Ltd",
        "AARTIIND",
        "Chemicals",
        "Specialty Chemicals",
        272,
        17800.0,
    ),
    (
        "INE944F01012",
        "Radico Khaitan Ltd",
        "RADICO",
        "Fast Moving Consumer Goods",
        "Breweries & Distilleries",
        275,
        24000.0,
    ),
    (
        "INE269A01021",
        "Sonata Software Ltd",
        "SONATSOFTW",
        "IT",
        "Computers - Software",
        280,
        16800.0,
    ),
    ("INE325A01013", "Timken India Ltd", "TIMKEN", "Capital Goods", "Bearing", 282, 28000.0),
    (
        "INE348B01021",
        "Century Plyboards India Ltd",
        "CENTURYPLY",
        "Consumer Durables",
        "Plywood Boards/Laminates",
        285,
        17500.0,
    ),
    (
        "INE120A01034",
        "Carborundum Universal Ltd",
        "CARBORUNIV",
        "Capital Goods",
        "Abrasives",
        288,
        25000.0,
    ),
    (
        "INE791I01019",
        "Brigade Enterprises Ltd",
        "BRIGADE",
        "Realty",
        "Real Estate Development",
        290,
        26000.0,
    ),
    (
        "INE220B01022",
        "Kalpataru Projects International",
        "KPIL",
        "Capital Goods",
        "Power Transmission & Distribution",
        292,
        19000.0,
    ),
    (
        "INE918Z01012",
        "Kaynes Technology India Ltd",
        "KAYNES",
        "Capital Goods",
        "Industrial Electronics",
        295,
        27000.0,
    ),
    (
        "INE018E01016",
        "Amber Enterprises India Ltd",
        "AMBER",
        "Consumer Durables",
        "Consumer Electronics",
        298,
        18000.0,
    ),
    (
        "INE970X01018",
        "Lemon Tree Hotels Ltd",
        "LEMONTREE",
        "Consumer Services",
        "Hotels & Resorts",
        305,
        11500.0,
    ),
    ("INE602A01023", "PCBL Ltd", "PCBL", "Chemicals", "Carbon Black", 308, 16000.0),
    (
        "INE495S01016",
        "Suven Pharmaceuticals Ltd",
        "SUVENPHAR",
        "Healthcare",
        "Pharmaceuticals",
        312,
        29000.0,
    ),
    (
        "INE618H01018",
        "Equitas Small Finance Bank Ltd",
        "EQUITASBNK",
        "Financial Services",
        "Small Finance Banks",
        315,
        10500.0,
    ),
    (
        "INE739E01017",
        "Cera Sanitaryware Ltd",
        "CERA",
        "Consumer Durables",
        "Ceramics",
        320,
        11000.0,
    ),
    (
        "INE146AA01010",
        "Kirloskar Oil Engines Ltd",
        "KIRLOSENG",
        "Capital Goods",
        "Engines",
        322,
        14000.0,
    ),
    (
        "INE00LO01017",
        "Craftsman Automation Ltd",
        "CRAFTSMAN",
        "Automobile",
        "Auto Components",
        325,
        12000.0,
    ),
    (
        "INE743C01021",
        "Quess Corp Ltd",
        "QUESS",
        "Consumer Services",
        "Commercial Services",
        330,
        9500.0,
    ),
    (
        "INE195J01029",
        "PNC Infratech Ltd",
        "PNCINFRA",
        "Capital Goods",
        "Civil Construction",
        335,
        10800.0,
    ),
    (
        "INE399C01030",
        "Suprajit Engineering Ltd",
        "SUPRAJIT",
        "Automobile",
        "Auto Components",
        340,
        6800.0,
    ),
    ("INE034A01011", "Arvind Ltd", "ARVIND", "Textiles", "Textiles - Denim", 345, 9200.0),
    (
        "INE634I01029",
        "KNR Constructions Ltd",
        "KNRCON",
        "Capital Goods",
        "Civil Construction",
        350,
        9600.0,
    ),
    ("INE418H01029", "Allcargo Logistics Ltd", "ALLCARGO", "Services", "Logistics", 355, 6200.0),
    (
        "INE949H01023",
        "Man Infraconstruction Ltd",
        "MANINFRA",
        "Realty",
        "Real Estate Development",
        360,
        7800.0,
    ),
    (
        "INE014W01014",
        "Aster DM Healthcare Ltd",
        "ASTERDM",
        "Healthcare",
        "Hospital Services",
        255,
        19800.0,
    ),
]


async def upsert_market_caps(
    conn: asyncpg.Connection,
    entries: Sequence[StockMarketCapEntry],
) -> None:
    """Upsert securities and market cap classifications using asyncpg transactions."""
    sec_rows = [(e.isin, e.name, e.nse_symbol, e.sector, e.industry) for e in entries]
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
        (
            e.isin,
            e.valid_from,
            e.valid_to,
            e.market_cap_rank,
            e.market_cap_class,
            e.avg_market_cap_cr,
        )
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
                elif any(
                    k in val for k in ("average market cap", "avg market cap", "mcap", "market cap")
                ):
                    mcap_col = c_idx
                elif any(k in val for k in ("nse symbol", "symbol", "bse scrip")):
                    symbol_col = c_idx

            if isin_col is not None and name_col is not None:
                header_idx = idx
                break

        if header_idx is None:
            raise ValueError(
                "Could not find required AMFI header row containing ISIN and Company Name"
            )

        entries: list[StockMarketCapEntry] = []
        rank_counter = 1

        for r in rows[header_idx + 1 :]:
            if not r or all(c is None for c in r):
                continue

            raw_isin = r[isin_col] if isin_col < len(r) else None
            if not raw_isin:
                continue

            isin_str = str(raw_isin).strip().upper()
            if not isin_pattern.match(isin_str):
                continue

            name_str = str(r[name_col]).strip() if name_col < len(r) and r[name_col] else isin_str
            sym_str = (
                str(r[symbol_col]).strip()
                if symbol_col is not None and symbol_col < len(r) and r[symbol_col]
                else ""
            )

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
    entries = AMFIMarketCapParser.parse_workbook(
        workbook_data, valid_from=valid_from, valid_to=valid_to
    )
    if not entries:
        logger.warning("No entries parsed from AMFI market cap file.")
        return 0

    await upsert_market_caps(conn, entries)
    logger.info("Successfully ingested %d AMFI market cap classifications.", len(entries))
    return len(entries)


if __name__ == "__main__":
    asyncio.run(seed_market_caps())
