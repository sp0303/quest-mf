"""Unit tests for AMFI market cap classification parser."""

import io
from datetime import date

import openpyxl

from workers.amfi_marketcap_worker import AMFIMarketCapParser


def test_amfi_marketcap_workbook_parsing():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Categorization of Stocks"

    # AMFI standard top metadata
    ws.append(["Association of Mutual Funds in India (AMFI)"])
    ws.append(["Semi-Annual Categorization of Stocks (July - December 2026)"])
    ws.append([])

    # Header
    ws.append(
        [
            "Sr. No.",
            "Company Name",
            "ISIN",
            "BSE Symbol",
            "NSE Symbol",
            "Average Market Capitalization (Rs. In Lakhs)",
        ]
    )

    # Rank 1: Reliance (Large Cap)
    ws.append([1, "Reliance Industries Ltd", "INE002A01018", "500325", "RELIANCE", 198000000.0])
    # Rank 2: TCS (Large Cap)
    ws.append([2, "Tata Consultancy Services Ltd", "INE467B01029", "532540", "TCS", 155000000.0])
    # Rank 3: Federal Bank
    ws.append([3, "Federal Bank Ltd", "INE053F01010", "500469", "FEDERALBNK", 4100000.0])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    valid_from = date(2026, 1, 1)
    valid_to = date(2026, 6, 30)

    entries = AMFIMarketCapParser.parse_workbook(buf, valid_from=valid_from, valid_to=valid_to)

    assert len(entries) == 3

    e1 = entries[0]
    assert e1.isin == "INE002A01018"
    assert e1.name == "Reliance Industries Ltd"
    assert e1.nse_symbol == "RELIANCE"
    assert e1.market_cap_rank == 1
    assert e1.market_cap_class == "LARGE_CAP"
    assert e1.valid_from == valid_from
    assert e1.valid_to == valid_to

    e2 = entries[1]
    assert e2.market_cap_rank == 2
    assert e2.market_cap_class == "LARGE_CAP"

    e3 = entries[2]
    assert e3.market_cap_rank == 3
    assert e3.market_cap_class == "LARGE_CAP"
