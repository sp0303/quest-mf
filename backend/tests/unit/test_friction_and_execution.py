from datetime import date

import pytest
from questmf_quant.backtest.execution import ExecutionEngine
from questmf_quant.friction import calculate_net_return


def test_o_friction_golden_calculation():
    """Test O: Friction: a 1% load + 20% STCG example matches a hand-computed golden value.

    Scenario:
    - Investment: Rs. 100,000
    - Stamp duty: 0.005% = Rs. 5 -> Net invested = Rs. 99,995
    - Buy NAV = 100.0 -> Units = 999.95
    - Sell NAV = 120.0 (Gross +20%) -> Gross proceeds = 999.95 * 120 = Rs. 119,994
    - Exit load: 1% = 119,994 * 0.01 = Rs. 1,199.94
    - Proceeds after load = 119,994 - 1,199.94 = Rs. 118,794.06
    - STT: 0.1% of gross = 119,994 * 0.001 = Rs. 119.994
    - Capital gain = Proceeds after load (118,794.06) - Net invested (99,995) = Rs. 18,799.06
    - STCG Tax: 20% of 18,799.06 = Rs. 3,759.812
    - Net proceeds = 118,794.06 - 119.994 - 3,759.812 = Rs. 114,914.254
    - Net profit = 114,914.254 - 100,000 = Rs. 14,914.254 (+14.914%)
    """
    res = calculate_net_return(
        initial_amount=100000.0,
        buy_nav=100.0,
        sell_nav=120.0,
        days_held=180,  # Short term (< 365 days)
        exit_load_rate=0.01,
        exit_load_days=365,
        stcg_rate=0.20,
        stamp_duty_rate=0.00005,
        stt_rate=0.001,
    )

    assert res.stamp_duty == pytest.approx(5.0)
    assert res.net_invested == pytest.approx(99995.0)
    assert res.units == pytest.approx(999.95)
    assert res.gross_proceeds == pytest.approx(119994.0)
    assert res.exit_load == pytest.approx(1199.94)
    assert res.proceeds_after_load == pytest.approx(118794.06)
    assert res.stt == pytest.approx(119.994)
    assert res.capital_gain == pytest.approx(18799.06)
    assert res.tax == pytest.approx(3759.812)
    assert res.net_proceeds == pytest.approx(114914.254, rel=1e-5)
    assert res.net_return_pct == pytest.approx(0.14914254, rel=1e-5)


def test_m_backtest_execution_lag():
    """Test M: Backtest cannot buy at NAV(d); first possible fill is NAV(d + EXEC_LAG)."""
    engine = ExecutionEngine(exec_lag_days=1)
    calendar = [
        date(2024, 1, 15),  # Decision date
        date(2024, 1, 16),  # T+1 fill date
        date(2024, 1, 17),
    ]

    fill_d = engine.calculate_fill_date(date(2024, 1, 15), calendar)
    assert fill_d is not None
    # Cannot fill at decision date
    assert fill_d != date(2024, 1, 15)
    # First possible fill is T + EXEC_LAG (2024-01-16)
    assert fill_d == date(2024, 1, 16)


def test_n_restricted_fund_not_bought():
    """Test N: Restricted fund at d is never bought at d."""
    engine = ExecutionEngine()
    restricted = {101, 102}  # Restricted portfolios

    assert engine.can_invest(101, date(2024, 1, 15), restricted) is False
    assert engine.can_invest(103, date(2024, 1, 15), restricted) is True
