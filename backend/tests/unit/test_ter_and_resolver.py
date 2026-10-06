"""AMFI TER parsing and live-portfolio name matching (genuine data only, never guess)."""

from __future__ import annotations

from datetime import date

from workers.portfolio_resolver import names_match
from workers.ter_worker import financial_year, normalize_scheme_name, ter_change_points


def test_normalize_scheme_name_matches_amfi_and_display_forms():
    assert normalize_scheme_name("HSBC India Export Opportunities Fund") == normalize_scheme_name(
        "HSBC INDIA EXPORT OPPORTUNITIES FUND"
    )
    assert normalize_scheme_name("Banking & PSU Fund") == "banking and psu"


def test_erstwhile_name_matches_renamed_fund():
    live = "ICICI Prudential Large Cap Fund (erstwhile Bluechip Fund)"
    assert names_match("ICICI Prudential Bluechip Fund", live)
    assert names_match("Quant Small Cap Fund", "QUANT SMALL CAP FUND")
    assert not names_match("Quant Small Cap Fund", "Quantum Small Cap Fund")
    assert not names_match("HDFC Bluechip Fund", live)  # different AMC


def test_ter_change_points_keep_only_changes_and_skip_invalid():
    rows = [
        {"Scheme_Name": "X Fund", "TER_Date": "2026-09-01T00:00:00.000Z", "D_TER": "0.6200"},
        {"Scheme_Name": "X Fund", "TER_Date": "2026-09-02T00:00:00.000Z", "D_TER": "0.6200"},
        {"Scheme_Name": "X Fund", "TER_Date": "2026-09-10T00:00:00.000Z", "D_TER": "0.5800"},
        {"Scheme_Name": "Y Fund", "TER_Date": "2026-09-01T00:00:00.000Z", "D_TER": "0"},
        {"Scheme_Name": "Z Fund", "TER_Date": "bad", "D_TER": "0.4"},
    ]
    pts = ter_change_points(rows)
    assert pts == {"x": [(date(2026, 9, 1), 0.62), (date(2026, 9, 10), 0.58)]}


def test_financial_year_boundary():
    assert financial_year(date(2026, 10, 6)) == "2026-2027"
    assert financial_year(date(2026, 3, 31)) == "2025-2026"
