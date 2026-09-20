"""Unit tests for portfolio overlap engine."""

from questmf_quant.portfolio.overlap import (
    HoldingItem,
    compute_portfolio_overlap,
    compute_weights_overlap,
)


def test_empty_portfolios():
    assert compute_weights_overlap({}, {}) == 0.0
    result = compute_portfolio_overlap([], [])
    assert result.overlap_pct == 0.0
    assert result.common_holdings_count == 0
    assert result.unique_to_a_count == 0
    assert result.unique_to_b_count == 0


def test_disjoint_portfolios():
    holdings_a = [
        HoldingItem(identifier="INE002A01018", name="Reliance Industries", weight=9.5),
        HoldingItem(identifier="INE040A01034", name="HDFC Bank", weight=8.2),
    ]
    holdings_b = [
        HoldingItem(identifier="INE009A01021", name="Infosys", weight=7.0),
        HoldingItem(identifier="INE467B01029", name="TCS", weight=6.0),
    ]

    result = compute_portfolio_overlap(holdings_a, holdings_b)
    assert result.overlap_pct == 0.0
    assert result.common_holdings_count == 0
    assert result.unique_to_a_count == 2
    assert result.unique_to_b_count == 2


def test_identical_portfolios():
    holdings = [
        HoldingItem(identifier="INE002A01018", name="Reliance Industries", weight=10.0),
        HoldingItem(identifier="INE040A01034", name="HDFC Bank", weight=8.0),
        HoldingItem(identifier="INE090A01021", name="ICICI Bank", weight=7.0),
    ]

    result = compute_portfolio_overlap(holdings, holdings)
    assert result.overlap_pct == 25.0
    assert result.common_holdings_count == 3
    assert result.unique_to_a_count == 0
    assert result.unique_to_b_count == 0


def test_partial_overlap_and_ordering():
    holdings_a = [
        HoldingItem(identifier="INE002A01018", name="Reliance", weight=10.0, sector="Energy"),
        HoldingItem(
            identifier="INE040A01034", name="HDFC Bank", weight=8.0, sector="Financial Services"
        ),
        HoldingItem(identifier="INE009A01021", name="Infosys", weight=6.0, sector="IT"),
        HoldingItem(
            identifier="INE238A01034", name="Axis Bank", weight=4.0, sector="Financial Services"
        ),
    ]
    holdings_b = [
        HoldingItem(identifier="INE002A01018", name="Reliance", weight=6.0, sector="Energy"),
        HoldingItem(
            identifier="INE040A01034", name="HDFC Bank", weight=9.0, sector="Financial Services"
        ),
        HoldingItem(
            identifier="INE090A01021", name="ICICI Bank", weight=7.0, sector="Financial Services"
        ),
        HoldingItem(identifier="INE009A01021", name="Infosys", weight=2.0, sector="IT"),
    ]

    result = compute_portfolio_overlap(holdings_a, holdings_b)
    # Common:
    # Reliance: min(10, 6) = 6.0
    # HDFC Bank: min(8, 9) = 8.0
    # Infosys: min(6, 2) = 2.0
    # Total overlap = 8.0 + 6.0 + 2.0 = 16.0
    assert result.overlap_pct == 16.0
    assert result.common_holdings_count == 3
    assert result.unique_to_a_count == 1  # Axis Bank
    assert result.unique_to_b_count == 1  # ICICI Bank

    # Check ordering: highest overlap weight first (HDFC Bank: 8.0, Reliance: 6.0, Infosys: 2.0)
    assert result.common_holdings[0].identifier == "INE040A01034"
    assert result.common_holdings[0].overlap_weight == 8.0
    assert result.common_holdings[1].identifier == "INE002A01018"
    assert result.common_holdings[1].overlap_weight == 6.0
    assert result.common_holdings[2].identifier == "INE009A01021"
    assert result.common_holdings[2].overlap_weight == 2.0


def test_case_insensitivity():
    holdings_a = [HoldingItem(identifier="ine002a01018", name="Reliance", weight=5.0)]
    holdings_b = [HoldingItem(identifier="INE002A01018", name="Reliance", weight=7.0)]
    result = compute_portfolio_overlap(holdings_a, holdings_b)
    assert result.overlap_pct == 5.0
    assert result.common_holdings_count == 1
