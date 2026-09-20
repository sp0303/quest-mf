"""Unit tests verifying AMC Portfolio Parser Contract Gates H1–H8."""

import io
from datetime import date

import openpyxl
from workers.parsers.base import BaseAMCParser
from workers.parsers.nippon import NipponIndiaParser


def test_gate_h1_header_sniffing():
    # Scenario 1: Standard layout (headers at row 1)
    rows_std = [
        ["ISIN", "Name of Instrument", "Industry", "Quantity", "Market Value", "% to Net Assets"],
        ["INE002A01018", "Reliance Industries", "Energy", 1000, 25.0, 4.5],
    ]
    mapping_std = BaseAMCParser.sniff_headers(rows_std)
    assert mapping_std.header_row_index == 0
    assert mapping_std.isin_col == 0
    assert mapping_std.name_col == 1
    assert mapping_std.pct_nav_col == 5

    # Scenario 2: Offset layout with banner text and merged disclaimer rows
    rows_offset = [
        ["Nippon India Mutual Fund - Monthly Portfolio Statement"],
        ["Confidential - For Investor Use Only"],
        ["Portfolio as on August 31, 2026"],
        [],
        ["Notes: Past performance is not an indicator of future returns"],
        ["Sr No", "ISIN", "Name of the Instrument", "Rating / Industry", "Quantity", "Market Value (Rs. in Lakhs)", "% to NAV"],
        [1, "INE002A01018", "Reliance Industries", "Energy", 1000, 25.0, 4.5],
    ]
    mapping_offset = BaseAMCParser.sniff_headers(rows_offset)
    assert mapping_offset.header_row_index == 5
    assert mapping_offset.isin_col == 1
    assert mapping_offset.name_col == 2
    assert mapping_offset.pct_nav_col == 6


def test_gate_h2_isin_validation():
    assert BaseAMCParser.clean_isin("INE002A01018") == "INE002A01018"
    assert BaseAMCParser.clean_isin("  ine040a01034  ") == "INE040A01034"
    assert BaseAMCParser.clean_isin("IN0020200154") == "IN0020200154"
    assert BaseAMCParser.clean_isin("INVALID") is None
    assert BaseAMCParser.clean_isin("TREPS_CASH") is None
    assert BaseAMCParser.clean_isin("") is None
    assert BaseAMCParser.clean_isin(None) is None


def test_gate_h3_weight_parsing():
    assert BaseAMCParser.clean_weight("4.25%") == 4.25
    assert BaseAMCParser.clean_weight(" 3.10 ") == 3.10
    assert BaseAMCParser.clean_weight(5.5) == 5.5
    assert BaseAMCParser.clean_weight("--") == 0.0
    assert BaseAMCParser.clean_weight("NIL") == 0.0
    assert BaseAMCParser.clean_weight(None) == 0.0


def test_gate_h4_weight_bounds_validation():
    from workers.holdings_worker import RawHoldingEntry

    d1 = date(2026, 8, 31)
    d2 = date(2026, 9, 10)

    # Valid portfolio ~98.5%
    holdings_valid = [
        RawHoldingEntry(101, d1, "INE002A01018", "Reliance", "EQUITY", "Energy", 100, 10, 50.0, d2),
        RawHoldingEntry(101, d1, "INE040A01034", "HDFC Bank", "EQUITY", "Finance", 100, 10, 48.5, d2),
    ]
    valid, msg = BaseAMCParser.validate_holdings(holdings_valid)
    assert valid is True

    # Incomplete portfolio ~45.0%
    holdings_incomplete = [
        RawHoldingEntry(101, d1, "INE002A01018", "Reliance", "EQUITY", "Energy", 100, 10, 45.0, d2),
    ]
    valid, msg = BaseAMCParser.validate_holdings(holdings_incomplete)
    assert valid is False
    assert "Gate H4 Failed" in msg


def test_gate_h5_asset_classification():
    assert BaseAMCParser.detect_asset_type("Reliance Industries Ltd", "INE002A01018") == "EQUITY"
    assert BaseAMCParser.detect_asset_type("TREPS - Triparty Repo", None) == "TREPS_CASH"
    assert BaseAMCParser.detect_asset_type("Reverse Repo Lending", None) == "TREPS_CASH"
    assert BaseAMCParser.detect_asset_type("7.18% GOI 2033", "IN0020230085", "Government Bond") == "DEBT"


def test_nippon_end_to_end_workbook_parsing():
    # Construct an in-memory mock Excel workbook matching Nippon India layout
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Nippon India Small Cap Fund"

    # Title block
    ws.append(["Nippon India Mutual Fund"])
    ws.append(["Monthly Portfolio Statement as on August 31, 2026"])
    ws.append(["Nippon India Small Cap Fund"])
    ws.append([])

    # Header row (Gate H1)
    ws.append([
        "ISIN",
        "Name of Instrument",
        "Industry / Rating",
        "Quantity",
        "Market Value (Rs. in Lakhs)",
        "% to Net Assets",
    ])

    # Equity holdings
    ws.append(["INE548C01032", "Suzlon Energy Ltd", "Heavy Electrical Equipment", 2500000, 15000.0, 4.25])
    ws.append(["INE429C01035", "Titagarh Rail Systems Ltd", "Railway Wagons", 850000, 12000.0, 3.85])
    ws.append(["INE705A01016", "Kalyan Jewellers India Ltd", "Gems Jewellery & Watches", 1200000, 11000.0, 3.50])
    ws.append(["INE285J01028", "Marksans Pharma Ltd", "Pharmaceuticals", 1500000, 9500.0, 3.10])
    ws.append(["INE053F01010", "Federal Bank Ltd", "Banks", 1400000, 8900.0, 2.90])
    ws.append([None, "TREPS / Reverse Repo Cash", "Cash & Cash Equivalents", None, 25000.0, 78.50])
    ws.append([None, "Grand Total", None, None, 81400.0, 96.10])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    as_of = date(2026, 8, 31)
    disclosed = date(2026, 9, 10)

    parser = NipponIndiaParser()
    res = parser.parse_workbook(buf, portfolio_id=101, as_of_date=as_of, disclosed_date=disclosed)

    assert res.valid is True
    assert res.equity_count == 5
    assert res.total_weight == 96.10
    assert len(res.holdings) == 6  # 5 equity + 1 TREPS cash

    # Check first holding
    h0 = res.holdings[0]
    assert h0.isin == "INE548C01032"
    assert h0.security_name == "Suzlon Energy Ltd"
    assert h0.pct_nav == 4.25
    assert h0.asset_type == "EQUITY"
    assert h0.as_of_date == as_of
    assert h0.disclosed_date == disclosed
