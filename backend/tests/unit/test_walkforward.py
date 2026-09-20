from datetime import date, timedelta

from questmf_quant.backtest.walkforward import (
    BacktestConfig,
    run_walkforward_backtest,
)


def test_walkforward_simulation():
    # Setup 100 trading days
    base_date = date(2023, 1, 1)
    calendar = [base_date + timedelta(days=i) for i in range(120)]

    # 3 portfolios
    nav_by_portfolio = {
        101: {d: 100.0 * (1.0 + 0.001 * i) for i, d in enumerate(calendar)},
        102: {d: 50.0 * (1.0 + 0.0005 * i) for i, d in enumerate(calendar)},
        103: {d: 20.0 * (1.0 - 0.0002 * i) for i, d in enumerate(calendar)},
    }

    # Scores at day 0 and day 60
    scores_by_date = {
        calendar[0]: {101: 90.0, 102: 80.0, 103: 40.0},
        calendar[60]: {101: 85.0, 102: 95.0, 103: 30.0},
    }

    config = BacktestConfig(
        top_k=2,
        rebalance_months=2,
        exec_lag_days=1,
        min_hold_days=10,
        initial_capital=100000.0,
    )

    result = run_walkforward_backtest(
        nav_by_portfolio=nav_by_portfolio,
        scores_by_date=scores_by_date,
        trading_calendar=calendar,
        config=config,
    )

    assert len(result.equity_curve_gross) == 120
    assert len(result.equity_curve_net) == 120
    assert result.summary["top_k"] == 2
    assert result.summary["cagr_gross"] > 0
    # Net return should be less than or equal to gross return due to friction
    assert result.summary["cagr_net"] <= result.summary["cagr_gross"]
    assert result.summary["max_drawdown"] <= 0.0


def test_walkforward_missing_nav_no_explosion():
    """Verify that a fund missing NAV on fill date does not default to 1.0 and explode equity."""
    base_date = date(2023, 1, 1)
    calendar = [base_date + timedelta(days=i) for i in range(120)]

    # Portfolio 201 has high NAV (e.g., 500.0) but is completely MISSING on day 1 (fill date)
    # If old buggy code defaulted fill NAV to 1.0, 50,000 / 1.0 = 50,000 units.
    # On day 2, 50,000 * 500 = 25,000,000 (2.5 Crore overnight!).
    nav_201 = {
        calendar[i]: 500.0 * (1.0 + 0.0005 * i) for i in range(1, len(calendar))
    }  # missing day 0 and day 1!
    nav_202 = {calendar[i]: 100.0 * (1.0 + 0.0002 * i) for i in range(len(calendar))}

    nav_by_portfolio = {
        201: nav_201,
        202: nav_202,
    }

    # At day 0, 201 is scored #1, 202 is scored #2
    scores_by_date = {
        calendar[0]: {201: 99.0, 202: 80.0},
    }

    config = BacktestConfig(
        top_k=2,
        rebalance_months=3,
        exec_lag_days=1,
        initial_capital=100000.0,
    )

    result = run_walkforward_backtest(
        nav_by_portfolio=nav_by_portfolio,
        scores_by_date=scores_by_date,
        trading_calendar=calendar,
        config=config,
    )

    # Max equity value should remain realistic (never anywhere near 10x or Millions!)
    max_gross = max(v for _, v in result.equity_curve_gross)
    max_net = max(v for _, v in result.equity_curve_net)

    assert max_gross < 200000.0, f"Gross equity exploded: {max_gross}"
    assert max_net < 200000.0, f"Net equity exploded: {max_net}"
    assert result.summary["cagr_gross"] < 1.0, "CAGR exploded"
    assert result.summary["cagr_net"] < 1.0, "Net CAGR exploded"
    assert isinstance(result.summary["cagr_gross"], float)
    assert isinstance(result.summary["cagr_net"], float)
    assert isinstance(result.summary["sharpe_ratio"], float)


def test_walkforward_unpriced_fund_preserves_capital():
    """Verify that if target funds are completely unpriced, cash is preserved safely."""
    base_date = date(2023, 1, 1)
    calendar = [base_date + timedelta(days=i) for i in range(30)]

    nav_by_portfolio = {
        301: {},  # no NAV data at all
    }

    scores_by_date = {
        calendar[0]: {301: 99.0},
    }

    config = BacktestConfig(
        top_k=1,
        rebalance_months=1,
        exec_lag_days=1,
        initial_capital=100000.0,
    )

    result = run_walkforward_backtest(
        nav_by_portfolio=nav_by_portfolio,
        scores_by_date=scores_by_date,
        trading_calendar=calendar,
        config=config,
    )

    # Cash should remain unspent at 100,000.0
    for _, val in result.equity_curve_gross:
        assert val == 100000.0
    for _, val in result.equity_curve_net:
        assert val == 100000.0
