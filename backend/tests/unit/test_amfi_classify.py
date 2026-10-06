"""AMFI share-class and category classification (Rule Q7, spec §6.2 universe)."""

from __future__ import annotations

import pytest

from workers.amfi_classify import NON_EQUITY, classify_plan_option, classify_section_header
from workers.ingestion_worker import parse_amfi_feed

# Lines copied from AMFI NAVAll.txt (05-Oct-2026).
FEED = """Open Ended Schemes(Equity Scheme - Small Cap Fund)
Tata Mutual Fund
145206;INF277K011O1;-;Tata Small Cap Fund;Direct Plan;Growth Option;44.8082;05-Oct-2026
145209;-;INF277K012O9;Tata Small Cap Fund;Direct Plan;Reinvestment of Income Distribution cum capital withdrawal option;43.2904;05-Oct-2026
145207;INF277K013O7;-;Tata Small Cap Fund;Direct Plan;Payout of Income Distribution cum capital withdrawal option;43.2904;05-Oct-2026
Open Ended Schemes(Debt Scheme - Short Duration Fund)
HDFC Mutual Fund
119016;INF179K01XX1;-;HDFC Short Term Fund;Direct Plan;Growth Option;33.10;05-Oct-2026
Open Ended Schemes(Equity Schemes - Large & Mid Cap Fund)
Motilal Oswal Mutual Fund
152694;INF247L01XX1;-;Motilal Oswal Large and Midcap Fund;Direct Plan;Growth;31.50;05-Oct-2026
152695;INF247L01XX2;-;Motilal Oswal Large and Midcap Fund;Direct Plan;Reinvestment/Payout;30.10;05-Oct-2026
Open Ended Schemes(Equity Scheme - Dividend Yield Fund)
ICICI Prudential Mutual Fund
143874;INF109KXX01;-;ICICI Prudential Dividend Yield Equity Fund;Direct Plan;Cumulative;55.00;05-Oct-2026
"""


@pytest.fixture(scope="module")
def parsed():
    schemes, rejected = parse_amfi_feed(FEED)
    assert rejected == 0
    return {s.scheme_code: s for s in schemes}


def test_only_true_direct_growth_is_canonical(parsed):
    assert parsed[145206].option == "GROWTH" and parsed[145206].is_canonical
    for code in (145209, 145207, 152695):  # IDCW reinvestment / payout variants
        assert parsed[code].option == "IDCW"
        assert not parsed[code].is_canonical


def test_cumulative_is_growth_and_dividend_yield_name_is_not_idcw(parsed):
    s = parsed[143874]
    assert (s.option, s.is_canonical, s.category_code) == ("GROWTH", True, "EQ_DIVIDEND_YIELD")


def test_debt_section_does_not_inherit_previous_equity_category(parsed):
    assert parsed[119016].category_code == NON_EQUITY[0]


def test_large_and_mid_cap_is_not_mid_cap(parsed):
    assert parsed[152694].category_code == "EQ_LARGE_MID_CAP"


@pytest.mark.parametrize(
    ("header", "code"),
    [
        ("Open Ended Schemes(Equity Scheme - Sectoral/ Thematic)", "EQ_SECTORAL_THEMATIC"),
        ("Open Ended Schemes(Equity Schemes - ELSS- Tax Saver Fund)", "EQ_ELSS"),
        ("Open Ended Schemes(Hybrid Scheme - Equity Savings)", NON_EQUITY[0]),
        ("Open Ended Schemes(Hybrid Scheme - Arbitrage Fund)", NON_EQUITY[0]),
        ("Close Ended Schemes(ELSS)", NON_EQUITY[0]),
        ("Open Ended Schemes(Other Scheme - Index Funds)", "EQ_INDEX"),
        ("Open Ended Schemes(Exchange Traded Funds (ETFs) - Gold ETF)", NON_EQUITY[0]),
        ("Open Ended Schemes(Exchange Traded Funds (ETFs) - Equity ETF)", "EQ_ETF"),
    ],
)
def test_section_headers(header, code):
    assert classify_section_header(header)[0] == code


def test_unknown_option_is_never_growth():
    assert classify_plan_option("Direct Plan", "Monthly Payment Plan") == ("DIRECT", "IDCW")
    assert classify_plan_option("Direct Plan", "") == ("DIRECT", "IDCW")
    assert classify_plan_option("Regular Plan", "Growth") == ("REGULAR", "GROWTH")
