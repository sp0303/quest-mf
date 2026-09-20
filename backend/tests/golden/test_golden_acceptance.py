"""Golden test suite per Spec v2 §28 (Tests O, R, S)."""

import pytest
from questmf_quant.friction import calculate_net_return
from questmf_quant.percentile import mid_rank_percentile
from questmf_quant.returns import cagr
from questmf_quant.scoring import DEFAULT_BASELINE_MODEL, compute_composite_score


def test_o_friction_golden_calculation():
    """Test O: Friction: 1% load + 20% STCG matches hand-computed golden spreadsheet value."""
    res = calculate_net_return(
        initial_amount=100000.0,
        buy_nav=100.0,
        sell_nav=120.0,
        days_held=180,
        exit_load_rate=0.01,
        exit_load_days=365,
        stcg_rate=0.20,
        stamp_duty_rate=0.00005,
        stt_rate=0.001,
    )

    # Hand-calculated golden values:
    assert res.stamp_duty == pytest.approx(5.0, abs=1e-6)
    assert res.net_invested == pytest.approx(99995.0, abs=1e-6)
    assert res.units == pytest.approx(999.95, abs=1e-6)
    assert res.gross_proceeds == pytest.approx(119994.0, abs=1e-6)
    assert res.exit_load == pytest.approx(1199.94, abs=1e-6)
    assert res.proceeds_after_load == pytest.approx(118794.06, abs=1e-6)
    assert res.stt == pytest.approx(119.994, abs=1e-6)
    assert res.capital_gain == pytest.approx(18799.06, abs=1e-6)
    assert res.tax == pytest.approx(3759.812, abs=1e-6)
    assert res.net_proceeds == pytest.approx(114914.254, abs=1e-6)
    assert res.net_return_pct == pytest.approx(0.14914254, abs=1e-6)


def test_r_golden_three_fund_two_year_fixture():
    """Test R: Golden fixture: 3 funds x 2 years matching hand-calculated spreadsheet to 1e-9."""
    # Day 0: 2022-01-03, Day 504: 2024-01-03 (~2 years, 730 days)
    # Fund 1: Steady Large Cap (100.0 -> 144.0)
    # Fund 2: High Vol Mid Cap  (100.0 -> 169.0)
    # Fund 3: Conservative Debt/Hybrid proxy (100.0 -> 116.0)
    days = 730.0

    cagr_1 = cagr(100.0, 144.0, days=days)
    cagr_2 = cagr(100.0, 169.0, days=days)
    cagr_3 = cagr(100.0, 116.0, days=days)

    # Expected: (144/100)^(365.25/730) - 1 = 1.44^0.50034223 - 1 = 0.20014603
    expected_cagr_1 = (1.44 ** (365.25 / 730.0)) - 1.0
    expected_cagr_2 = (1.69 ** (365.25 / 730.0)) - 1.0
    expected_cagr_3 = (1.16 ** (365.25 / 730.0)) - 1.0

    assert cagr_1 == pytest.approx(expected_cagr_1, abs=1e-9)
    assert cagr_2 == pytest.approx(expected_cagr_2, abs=1e-9)
    assert cagr_3 == pytest.approx(expected_cagr_3, abs=1e-9)

    # Peer percentiles mid-rank
    returns = [cagr_1, cagr_2, cagr_3]
    assert mid_rank_percentile(cagr_1, returns) == pytest.approx(50.0)
    assert mid_rank_percentile(cagr_2, returns) == pytest.approx(83.333333333)
    assert mid_rank_percentile(cagr_3, returns) == pytest.approx(16.666666667)


def test_s_deterministic_pipeline_reproducibility():
    """Test S: Full scoring pipeline on a fixed snapshot produces byte-identical deterministic results."""
    factor_scores = {
        "momentum": 72.5,
        "persistence": 68.0,
        "quality": 81.2,
        "risk": 55.4,
        "cost": 75.0,
    }

    # Run scoring 10 times consecutively
    results = [
        compute_composite_score(factor_scores, DEFAULT_BASELINE_MODEL, obs_count=500)
        for _ in range(10)
    ]

    first_score, first_conf = results[0]
    for score, conf in results[1:]:
        assert score == first_score
        assert conf == first_conf
